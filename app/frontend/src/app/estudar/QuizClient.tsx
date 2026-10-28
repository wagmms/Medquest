"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { QuestionMeta, QuestionListItem, QuestionDetail, AttemptResult, FlashcardGenerateResponse } from "@/types/api";
import { api, OfflineQueuedError } from "@/lib/api";
import { Clock, CheckCircle2, XCircle, BookOpen, ArrowRight, Sparkles, ArrowLeft, ImageOff, Maximize, AlertTriangle, CloudOff, RotateCcw, Pencil, Eye, EyeOff, Target } from "lucide-react";
import clsx from "clsx";
import toast from "react-hot-toast";
import { useRouter } from "next/navigation";
import { isLocalIdentityReady } from "@/lib/db";
import { prefetchQuestionsByIds } from "@/lib/syncQueue";
import { useUser } from "@clerk/nextjs";
import { normalizeFlashcard } from "@/lib/normalizeFlashcard";

import dynamic from "next/dynamic";
import { ImageViewer } from "@/components/ImageViewer";
import { ExplanationViewer } from "@/components/ExplanationViewer";
import { FormattedContent, normalizeImageSrc, filterExtraImages } from "@/components/FormattedContent";

const QuestionClassificationModal = dynamic(
  () => import("@/components/QuestionClassificationModal").then((mod) => mod.QuestionClassificationModal),
  { ssr: false }
);
import { useZenMode } from "@/hooks/useZenMode";
import { useWakeLock } from "@/hooks/useWakeLock";
import { useCurator } from "@/hooks/useCurator";
import type { QuizTimerHandle } from "@/components/QuizTimer";
import Image from "next/image";
import { QuizFilters } from "./components/QuizFilters";
import { AlternativeList } from "./components/AlternativeList";
import { PreceptorSection, ChatMessage } from "./components/PreceptorSection";
import { QuizHeader } from "./components/QuizHeader";
import { QuizFlashcardSection } from "./components/QuizFlashcardSection";
const QuizSessionReportModal = dynamic(
  () => import("./components/QuizSessionReportModal").then((mod) => mod.QuizSessionReportModal),
  { ssr: false }
);
import { DiscursiveAssessmentSection } from "./components/DiscursiveAssessmentSection";
import {
  LEARNING_SESSION_VERSION,
  readLearningSession,
  removeLearningSession,
  writeLearningSession,
} from "@/lib/sessionState";
import { useQuizKeyboard } from "./hooks/useQuizKeyboard";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";

export type SessionAnswer = { 
  letter: string; 
  result?: AttemptResult | null; 
  isOffline?: boolean; 
  writtenAnswer?: string; 
  isDiscursive?: boolean; 
};

type QuizState = "FILTERS" | "LOADING_QUEUE" | "PLAYING" | "FINISHED";

function resolveImageUrl(img: string | null | undefined): string {
  return normalizeImageSrc(img);
}

export interface SavedQuizState {
  version: number;
  state: "PLAYING" | "FINISHED";
  queue: QuestionListItem[];
  currentIndex: number;
  filters: Record<string, string | string[]>;
  currentDetail: QuestionDetail | null;
  sessionAnswers: Record<number, SessionAnswer>;
  selectedLetter: string | null;
  userWrittenAnswer?: string;
  timeSpent: number;
  savedAt: number;
  eliminatedAlternatives?: Record<number, string[]>;
}

function isSavedQuizState(value: unknown): value is SavedQuizState {
  if (typeof value !== "object" || value === null) return false;
  const saved = value as Partial<SavedQuizState>;
  return saved.version === LEARNING_SESSION_VERSION &&
    (saved.state === "PLAYING" || saved.state === "FINISHED") &&
    Array.isArray(saved.queue) && saved.queue.length > 0 &&
    typeof saved.currentIndex === "number" && saved.currentIndex >= 0 &&
    saved.currentIndex < saved.queue.length &&
    typeof saved.filters === "object" && saved.filters !== null &&
    typeof saved.sessionAnswers === "object" && saved.sessionAnswers !== null;
}

function areFiltersEquivalent(
  initial: Record<string, string | string[]>,
  saved: Record<string, string | string[]>
): boolean {
  const normalize = (f: Record<string, string | string[]>) => {
    const res: Record<string, string> = {};
    for (const [k, v] of Object.entries(f)) {
      if (k === "resume") continue;
      if (Array.isArray(v)) {
        if (v.length > 0) {
          res[k] = [...v].sort().join(",");
        }
      } else if (v !== undefined && v !== "") {
        res[k] = String(v);
      }
    }
    return res;
  };

  const normInitial = normalize(initial);
  const normSaved = normalize(saved);

  // Compare core topic/scope discriminators
  const coreKeys = ["subtema", "area", "topic", "institution", "mode", "status", "year", "specialty"];
  for (const k of coreKeys) {
    if (normInitial[k] && normSaved[k] && normInitial[k] !== normSaved[k]) {
      return false;
    }
  }

  // If a specific limit was requested in initialFilters, compare it only if both specify limit
  if (normInitial.limit && normSaved.limit && normInitial.limit !== normSaved.limit) {
    return false;
  }

  return true;
}

const DEFAULT_META: QuestionMeta = {
  total_questions: 0,
  answered_questions: 0,
  institutions: [],
  years: [],
  areas: [],
  subtemas: [],
  sources: [],
  specialties: []
};

export function QuizClient({
  meta = DEFAULT_META,
  initialFilters = {}
}: {
  meta?: QuestionMeta;
  initialFilters?: Record<string, string | string[]>;
}) {
  const router = useRouter();
  const { isLoaded: authLoaded } = useUser();
  const { isCurator } = useCurator();
  const [isClassificationModalOpen, setIsClassificationModalOpen] = useState(false);
  const hasExplicitFilters = Object.keys(initialFilters).filter(k => k !== "resume").length > 0;
  const [state, setState] = useState<QuizState>(hasExplicitFilters ? "LOADING_QUEUE" : "FILTERS");
  const [filters, setFilters] = useState<Record<string, string | string[]>>({ limit: "50", status: "unanswered", unanswered_only: "true", ...initialFilters });
  const [localLimit, setLocalLimit] = useState<string>(
    typeof filters.limit === "string" ? filters.limit : "50"
  );
  const { isZenMode: zenMode, toggleZenMode } = useZenMode();
  const [subtemaSearch, setSubtemaSearch] = useState("");
  const [showCustomSession, setShowCustomSession] = useState(false);
  const [showTopicTree, setShowTopicTree] = useState(false);
  const [hasSavedState, setHasSavedState] = useState(false);
  const [savedSessionData, setSavedSessionData] = useState<SavedQuizState | null>(null);

  const [studyMode, setStudyMode] = useState<"TUTOR" | "SIMULADO">("TUTOR");
  const [showTopic, setShowTopic] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("medquest_show_topic");
      if (saved !== null) {
        return saved === "true";
      }
    }
    return true;
  });

  const toggleTopic = () => {
    setShowTopic(prev => {
      const next = !prev;
      localStorage.setItem("medquest_show_topic", String(next));
      return next;
    });
  };
  const [dynamicMeta, setDynamicMeta] = useState<QuestionMeta>(meta || DEFAULT_META);
  const [isUpdatingMeta, setIsUpdatingMeta] = useState(false);
  
  const [queue, setQueue] = useState<QuestionListItem[]>([]);
  const queueRef = useRef<QuestionListItem[]>([]);
  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentDetail, setCurrentDetail] = useState<QuestionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  
  const [sessionAnswers, setSessionAnswers] = useState<Record<number, SessionAnswer>>({});
  useWakeLock(!!currentDetail && !loadingDetail);
  
  // Quiz State
  const [selectedLetter, setSelectedLetter] = useState<string | null>(null);
  const [eliminatedAlternatives, setEliminatedAlternatives] = useState<Record<number, string[]>>({});
  const [userWrittenAnswer, setUserWrittenAnswer] = useState<string>("");
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null);
  const [isOfflineSaved, setIsOfflineSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [autoFsrsOnWrong, setAutoFsrsOnWrong] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("medquest_auto_fsrs");
      return saved === null ? true : saved === "true";
    }
    return true;
  });
  const [autoGeneratingFlashcard, setAutoGeneratingFlashcard] = useState(false);
  const [generatingFlashcard, setGeneratingFlashcard] = useState(false);
  const [savingFlashcard, setSavingFlashcard] = useState(false);
  const [flashcardResult, setFlashcardResult] = useState<FlashcardGenerateResponse | null>(null);
  const [draftFlashcard, setDraftFlashcard] = useState<{front: string; back: string; context: string} | null>(null);
  const [generatingBatchFlashcards, setGeneratingBatchFlashcards] = useState(false);
  const [batchFlashcardsResult, setBatchFlashcardsResult] = useState<{ count: number } | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [askingPreceptor, setAskingPreceptor] = useState(false);
  const [preceptorInput, setPreceptorInput] = useState("");
  
  // Timer State
  const quizTimerRef = useRef<QuizTimerHandle>(null);
  const [initialTime, setInitialTime] = useState(0);

  // Expose current time without causing re-renders
  const getCurrentTime = useCallback(() => quizTimerRef.current?.getTime() ?? initialTime, [initialTime]);
  const [enlargedImage, setEnlargedImage] = useState<string | null>(null);

  const detailsCacheRef = useRef<Record<number, QuestionDetail>>({});
  const prefetchingRef = useRef<Set<number>>(new Set());

  const [togglingFavorite, setTogglingFavorite] = useState(false);
  const detailRequestRef = useRef(0);
  const attemptLockRef = useRef(false);
  const reviewLockRef = useRef(false);
  const favoriteLockRef = useRef(false);
  const reviewedQuestionsRef = useRef<Set<number>>(new Set());

  const loadQuestionDetail = useCallback(async (id: number) => {
    const requestId = ++detailRequestRef.current;
    setDetailError(null);
    setAttemptResult(null);
    setSelectedLetter(null);
    setUserWrittenAnswer("");
    setIsOfflineSaved(false);
    setFlashcardResult(null);
    setDraftFlashcard(null);
    setAutoGeneratingFlashcard(false);
    setChatMessages([]);
    setPreceptorInput("");
    setInitialTime(0);

    // Se já estiver no cache, carrega instantaneamente sem tela de loading
    const cached = detailsCacheRef.current[id];
    if (cached) {
      const queueItem = queueRef.current.find(q => q.id === id);
      const mergedCached = queueItem ? { ...queueItem, ...cached } : cached;
      setCurrentDetail(mergedCached);
      setLoadingDetail(false);
      return;
    }

    setLoadingDetail(true);
    setCurrentDetail(null);
    try {
      const detail = await api.questions.getDetail(id);
      const queueItem = queueRef.current.find(q => q.id === id);
      const mergedDetail = queueItem ? { ...queueItem, ...detail } : detail;
      detailsCacheRef.current[id] = mergedDetail;
      if (detailRequestRef.current === requestId) {
        setCurrentDetail(mergedDetail);
      }
    } catch (err) {
      console.error(`[QUIZ] Erro ao carregar questão ${id}:`, err);
      if (detailRequestRef.current === requestId) {
        const msg = err instanceof Error ? err.message : "Verifique sua conexão";
        setDetailError(`Não foi possível carregar esta questão (${msg}). Clique abaixo para tentar novamente.`);
      }
    } finally {
      if (detailRequestRef.current === requestId) setLoadingDetail(false);
    }
  }, []);

  // Pré-carregamento em segundo plano das próximas questões (Dexie + Cache em Memória)
  useEffect(() => {
    if (state !== "PLAYING" || queue.length === 0) return;

    const nextIds = [
      queue[currentIndex + 1]?.id,
      queue[currentIndex + 2]?.id,
      queue[currentIndex + 3]?.id,
    ].filter((id): id is number => typeof id === "number" && !detailsCacheRef.current[id] && !prefetchingRef.current.has(id));

    if (nextIds.length === 0) return;

    for (const nextId of nextIds) {
      prefetchingRef.current.add(nextId);
    }

    // Persiste no Dexie em lote via syncQueue e popula cache em memória para 0ms
    prefetchQuestionsByIds(nextIds)
      .then(async () => {
        for (const nextId of nextIds) {
          try {
            const detail = await api.questions.getDetail(nextId);
            detailsCacheRef.current[nextId] = detail;
          } catch {
            // Ignora falhas de prefetch em segundo plano
          }
        }
      })
      .catch(() => {
        // Ignora falhas de prefetch em segundo plano
      })
      .finally(() => {
        for (const nextId of nextIds) {
          prefetchingRef.current.delete(nextId);
        }
      });
  }, [state, queue, currentIndex]);

  const loadQueue = useCallback(async (activeFilters: Record<string, string | string[]>) => {
    removeLearningSession("quiz");
    setHasSavedState(false);
    setSavedSessionData(null);
    setFilters(activeFilters);
    if (typeof activeFilters.limit === "string") setLocalLimit(activeFilters.limit);
    if (typeof window !== "undefined") {
      sessionStorage.setItem("medquest_active_quiz", "1");
    }
    setState("LOADING_QUEUE");
    try {
      const qList = await api.questions.getList(activeFilters);
      if (qList.length > 0) {
        setQueue(qList);
        setCurrentIndex(0);
        setSessionAnswers({});
        setSelectedLetter(null);
        setAttemptResult(null);
        setState("PLAYING");
        loadQuestionDetail(qList[0].id);

        // Pré-carrega transacionalmente no Dexie as 10 próximas questões da fila
        const upcomingIds = qList.slice(1, 11).map((q) => q.id);
        if (upcomingIds.length > 0) {
          prefetchQuestionsByIds(upcomingIds).catch(() => {});
        }
      } else {
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("medquest_active_quiz");
        }
        toast.error("Nenhuma questão encontrada com esses filtros.");
        setState("FILTERS");
      }
    } catch (e) {
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("medquest_active_quiz");
      }
      const message = e instanceof Error ? e.message : "Erro desconhecido";
      toast.error(`Erro ao buscar questões: ${message}`);
      setState("FILTERS");
    }
  }, [loadQuestionDetail]);

  // Salvaguarda: garante que, se estiver no estado PLAYING sem questão carregada ou em erro, carrega a questão atual
  useEffect(() => {
    if (state === "PLAYING" && !currentDetail && !loadingDetail && !detailError && queue[currentIndex]) {
      const timer = setTimeout(() => {
        loadQuestionDetail(queue[currentIndex].id);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [state, currentDetail, loadingDetail, detailError, queue, currentIndex, loadQuestionDetail]);

  useEffect(() => {
    if (currentDetail && sessionAnswers[currentDetail.id]) {
      const ans = sessionAnswers[currentDetail.id];
      const timer = setTimeout(() => {
        setSelectedLetter(ans.letter);
        setAttemptResult(ans.result || null);
        setIsOfflineSaved(!!ans.isOffline);
        setUserWrittenAnswer(ans.writtenAnswer || "");
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [currentDetail, sessionAnswers]);

  useEffect(() => {
    const handleSyncSuccess = (e: Event) => {
      const customEvent = e as CustomEvent<{
        id: string;
        endpoint: string;
        method: string;
        data: unknown;
      }>;
      const detail = customEvent.detail;
      if (detail && detail.endpoint.includes("/api/questions/") && detail.endpoint.includes("/attempt")) {
        const attemptRes = detail.data as AttemptResult | null;
        if (attemptRes && typeof attemptRes.is_correct === "boolean") {
          const match = detail.endpoint.match(/\/api\/questions\/(\d+)\/attempt/);
          if (match && currentDetail && Number(match[1]) === currentDetail.id) {
            setAttemptResult(attemptRes);
            setIsOfflineSaved(false);
            setSessionAnswers(prev => ({
              ...prev,
              [currentDetail.id]: { letter: selectedLetter || attemptRes.correct_letter || "", result: attemptRes, writtenAnswer: userWrittenAnswer }
            }));
            toast.success("Resposta sincronizada com sucesso!");
          }
        }
      }
    };

    window.addEventListener("sync-item-success", handleSyncSuccess);
    return () => {
      window.removeEventListener("sync-item-success", handleSyncSuccess);
    };
  }, [currentDetail, selectedLetter, userWrittenAnswer]);

  const hasRestored = useRef(false);
  const [storageReady, setStorageReady] = useState(false);

  useEffect(() => {
    if (!isLocalIdentityReady(authLoaded) || hasRestored.current) return;
    hasRestored.current = true;

    const saved = readLearningSession("quiz", isSavedQuizState);
    const isExplicitResume = initialFilters.resume === "true" || initialFilters.resume === "1";
    const filterKeys = Object.keys(initialFilters).filter(k => k !== "resume");
    const isSameFilters = saved ? areFiltersEquivalent(initialFilters, saved.filters) : false;

    // Retomada explícita (?resume=true) OU sessão ativa em andamento com filtros compatíveis
    const shouldAutoResume = Boolean(
      saved &&
      (isExplicitResume ||
        (filterKeys.length > 0 && saved.state === "PLAYING" && isSameFilters))
    );

    if (saved && shouldAutoResume) {
      setTimeout(() => {
        setQueue(saved.queue);
        setCurrentIndex(saved.currentIndex);
        setFilters(saved.filters);
        setSessionAnswers(saved.sessionAnswers);
        setSelectedLetter(saved.selectedLetter);
        setUserWrittenAnswer(saved.userWrittenAnswer || "");
        if (saved.eliminatedAlternatives) {
          setEliminatedAlternatives(saved.eliminatedAlternatives);
        }
        setInitialTime(saved.timeSpent || 0);
        setState(saved.state);
        if (typeof window !== "undefined") {
          sessionStorage.setItem("medquest_active_quiz", "1");
        }
        const targetQ = saved.queue[saved.currentIndex];
        if (targetQ && saved.currentDetail && saved.currentDetail.id === targetQ.id) {
          setCurrentDetail(saved.currentDetail);
          detailsCacheRef.current[saved.currentDetail.id] = saved.currentDetail;
        } else if (targetQ) {
          setCurrentDetail(null);
          loadQuestionDetail(targetQ.id);
        }
        toast.success("Sessão de estudo retomada.");
        setStorageReady(true);
      }, 0);
    } else if (saved && filterKeys.length === 0) {
      // Acesso direto a /estudar (sem filtros): exibe tela de filtros com banner para retomar ou descartar
      setTimeout(() => {
        setHasSavedState(true);
        setSavedSessionData(saved);
        setState("FILTERS");
        setStorageReady(true);
      }, 0);
    } else if (filterKeys.length > 0) {
      // Nova sessão com filtros fornecidos: descarta e fecha automaticamente a anterior
      setTimeout(() => {
        loadQueue({ limit: "50", ...initialFilters });
        setStorageReady(true);
      }, 0);
    } else {
      setTimeout(() => {
        setState("FILTERS");
        setStorageReady(true);
      }, 0);
    }
  }, [authLoaded, initialFilters, loadQueue, loadQuestionDetail]);

  const resumeSavedQuiz = useCallback(() => {
    const saved = savedSessionData || readLearningSession("quiz", isSavedQuizState);
    if (saved) {
      setQueue(saved.queue);
      setCurrentIndex(saved.currentIndex);
      setFilters(saved.filters);
      setSessionAnswers(saved.sessionAnswers);
      setSelectedLetter(saved.selectedLetter);
      setUserWrittenAnswer(saved.userWrittenAnswer || "");
      if (saved.eliminatedAlternatives) {
        setEliminatedAlternatives(saved.eliminatedAlternatives);
      }
      setInitialTime(saved.timeSpent || 0);
      setState(saved.state);
      if (typeof window !== "undefined") {
        sessionStorage.setItem("medquest_active_quiz", "1");
      }
      const targetQ = saved.queue[saved.currentIndex];
      if (targetQ && saved.currentDetail && saved.currentDetail.id === targetQ.id) {
        setCurrentDetail(saved.currentDetail);
        detailsCacheRef.current[saved.currentDetail.id] = saved.currentDetail;
      } else if (targetQ) {
        setCurrentDetail(null);
        loadQuestionDetail(targetQ.id);
      }
      setHasSavedState(false);
      toast.success("Sessão de estudo retomada.");
    }
  }, [savedSessionData, loadQuestionDetail]);

  const discardSavedQuiz = useCallback(() => {
    removeLearningSession("quiz");
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("medquest_active_quiz");
    }
    setHasSavedState(false);
    setSavedSessionData(null);
    toast("Sessão anterior descartada.", { icon: "🗑️" });
  }, []);

  const currentDetailRef = useRef(currentDetail);
  const attemptResultRef = useRef(attemptResult);
  useEffect(() => {
    currentDetailRef.current = currentDetail;
    attemptResultRef.current = attemptResult;
  }, [currentDetail, attemptResult]);

  const ensureCurrentQuestionReviewed = useCallback(() => {
    const cur = currentDetailRef.current;
    const att = attemptResultRef.current;
    if (cur && att && !att.next_review_date && !reviewedQuestionsRef.current.has(cur.id)) {
      const qid = cur.id;
      const explicitCorr = att.is_correct;
      if (explicitCorr !== null && explicitCorr !== undefined) {
        reviewedQuestionsRef.current.add(qid);
        api.questions
          .reviewFSRS(qid, "duvida", explicitCorr, cur.twin_for_question_id, att.attempt_id)
          .then(res => {
            setSessionAnswers(prev => {
              const current = prev[qid];
              if (!current) return prev;
              return {
                ...prev,
                [qid]: {
                  ...current,
                  result: current.result ? { ...current.result, next_review_date: res.next_review_date } : undefined
                }
              };
            });
          })
          .catch(() => {
            reviewedQuestionsRef.current.delete(qid);
          });
      }
    }
  }, []);

  useEffect(() => {
    const reviewedSet = reviewedQuestionsRef.current;
    return () => {
      const cur = currentDetailRef.current;
      const att = attemptResultRef.current;
      if (
        cur &&
        att &&
        !att.next_review_date &&
        !reviewedSet.has(cur.id) &&
        att.is_correct !== null &&
        att.is_correct !== undefined
      ) {
        reviewedSet.add(cur.id);
        api.questions
          .reviewFSRS(cur.id, "duvida", att.is_correct, cur.twin_for_question_id, att.attempt_id)
          .catch(() => {});
      }
    };
  }, []);

  const [showFinishModal, setShowFinishModal] = useState(false);

  const confirmFinish = useCallback(() => {
    ensureCurrentQuestionReviewed();
    setShowFinishModal(false);
    setState("FINISHED");
  }, [ensureCurrentQuestionReviewed]);

  const handleRequestFinish = useCallback(() => {
    const answeredInSession = Object.values(sessionAnswers).filter(a => a.result || a.isOffline).length;
    const currentHasResult = attemptResult !== null;
    const effectiveAnswered = currentHasResult && currentDetail && !sessionAnswers[currentDetail.id]?.result 
      ? answeredInSession + 1 
      : answeredInSession;

    if (effectiveAnswered === 0) {
      toast("Você ainda não respondeu nenhuma questão. Use '← Voltar' para retornar aos filtros.", { icon: "ℹ️" });
      return;
    }

    if (effectiveAnswered >= queue.length) {
      confirmFinish();
      return;
    }

    setShowFinishModal(true);
  }, [sessionAnswers, attemptResult, currentDetail, queue.length, confirmFinish]);

  useEffect(() => {
    if (!showFinishModal) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowFinishModal(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showFinishModal]);

  const handleBackToFilters = useCallback(() => {
    setShowFinishModal(false);
    ensureCurrentQuestionReviewed();
    removeLearningSession("quiz");
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("medquest_active_quiz");
      window.history.replaceState(null, "", window.location.pathname);
    }
    setQueue([]);
    setCurrentIndex(0);
    setCurrentDetail(null);
    setSelectedLetter(null);
    setUserWrittenAnswer("");
    setAttemptResult(null);
    setSessionAnswers({});
    setInitialTime(0);
    setFilters({ limit: "50", status: "unanswered", unanswered_only: "true" });
    setLocalLimit("50");
    setHasSavedState(false);
    setSavedSessionData(null);
    setState("FILTERS");
  }, [ensureCurrentQuestionReviewed]);

  // Se os filtros mudarem posteriormente via navegação de rota cliente (ex: CommandPalette / Sidebar)
  const prevFiltersJson = useRef(JSON.stringify(initialFilters));
  useEffect(() => {
    const newJson = JSON.stringify(initialFilters);
    if (!hasRestored.current) return;
    if (prevFiltersJson.current === newJson) return;
    prevFiltersJson.current = newJson;

    const filterKeys = Object.keys(initialFilters).filter(k => k !== "resume");
    const isExplicitResume = initialFilters.resume === "true" || initialFilters.resume === "1";

    const timer = setTimeout(() => {
      if (isExplicitResume) {
        resumeSavedQuiz();
      } else if (filterKeys.length > 0) {
        // Se já estiver jogando e os filtros da rota forem equivalentes à sessão atual, preserva a sessão
        if (state === "PLAYING" && areFiltersEquivalent(initialFilters, filters)) {
          return;
        }
        loadQueue({ limit: "50", ...initialFilters });
      } else {
        handleBackToFilters();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [initialFilters, state, filters, loadQueue, resumeSavedQuiz, handleBackToFilters]);

  const handleNewSession = useCallback(() => {
    setBatchFlashcardsResult(null);
    handleBackToFilters();
  }, [handleBackToFilters]);

  const persistSession = useCallback((nextSelectedLetter = selectedLetter) => {
    if (!storageReady) return;
    if (state === "PLAYING" || state === "FINISHED") {
      writeLearningSession("quiz", {
        version: LEARNING_SESSION_VERSION,
        state,
        queue,
        currentIndex,
        filters,
        currentDetail,
        sessionAnswers,
        selectedLetter: nextSelectedLetter,
        userWrittenAnswer,
        timeSpent: getCurrentTime(),
        savedAt: Date.now(),
        eliminatedAlternatives,
      } satisfies SavedQuizState);
    } else if (state === "FILTERS" && !hasSavedState) {
      removeLearningSession("quiz");
    }
  }, [storageReady, state, queue, currentIndex, filters, currentDetail, sessionAnswers, selectedLetter, userWrittenAnswer, eliminatedAlternatives, hasSavedState, getCurrentTime]);

  useEffect(() => {
    persistSession();
  }, [persistSession]);

  // Persist session before unmounting to prevent losing progress if user navigates away
  const stateRef = useRef({ state, queue, currentIndex, filters, currentDetail, sessionAnswers, selectedLetter, userWrittenAnswer, eliminatedAlternatives, storageReady });
  useEffect(() => {
    stateRef.current = { state, queue, currentIndex, filters, currentDetail, sessionAnswers, selectedLetter, userWrittenAnswer, eliminatedAlternatives, storageReady };
  }, [state, queue, currentIndex, filters, currentDetail, sessionAnswers, selectedLetter, userWrittenAnswer, eliminatedAlternatives, storageReady]);

  useEffect(() => {
    return () => {
      const s = stateRef.current;
      if (s.storageReady && (s.state === "PLAYING" || s.state === "FINISHED")) {
        writeLearningSession("quiz", {
          version: LEARNING_SESSION_VERSION,
          state: s.state,
          queue: s.queue,
          currentIndex: s.currentIndex,
          filters: s.filters,
          currentDetail: s.currentDetail,
          sessionAnswers: s.sessionAnswers,
          selectedLetter: s.selectedLetter,
          userWrittenAnswer: s.userWrittenAnswer,
          timeSpent: getCurrentTime(),
          savedAt: Date.now(),
          eliminatedAlternatives: s.eliminatedAlternatives,
        } satisfies SavedQuizState);
      }
    };
  }, [getCurrentTime]);

  const toggleEliminateAlternative = useCallback((letter: string) => {
    if (!currentDetail || attemptResult || submitting) return;
    const qid = currentDetail.id;
    setEliminatedAlternatives((prev) => {
      const currentList = prev[qid] || [];
      const isEliminated = currentList.includes(letter);
      const nextList = isEliminated
        ? currentList.filter((l) => l !== letter)
        : [...currentList, letter];
      return { ...prev, [qid]: nextList };
    });
    if (selectedLetter === letter) {
      setSelectedLetter(null);
    }
  }, [currentDetail, attemptResult, submitting, selectedLetter]);

  const selectAlternative = useCallback((letter: string) => {
    if (attemptResult || submitting) return;
    if (currentDetail) {
      const qid = currentDetail.id;
      setEliminatedAlternatives((prev) => {
        if (!prev[qid]?.includes(letter)) return prev;
        return {
          ...prev,
          [qid]: prev[qid].filter((l) => l !== letter),
        };
      });
    }
    // Persist synchronously so a reload immediately after selecting an answer
    // can still restore the in-progress session.
    persistSession(letter);
    setSelectedLetter(letter);
  }, [attemptResult, submitting, persistSession, currentDetail]);

  // Effect to fetch dynamic meta when filters change
  useEffect(() => {
    if (state !== "FILTERS") return;
    
    let isMounted = true;
    const fetchDynamicMeta = async () => {
      setIsUpdatingMeta(true);
      try {
        // Keep topic options stable while the user selects several of them.
        // Otherwise each selected subtema narrows the metadata response and
        // makes the remaining specialties disappear from the tree.
        const metaFilters = { ...filters };
        delete metaFilters.subtema;
        delete metaFilters.topic;
        const newMeta = await api.questions.getMeta(metaFilters);
        if (isMounted) setDynamicMeta(newMeta);
      } catch {
        console.error("Failed to load dynamic meta");
      } finally {
        if (isMounted) setIsUpdatingMeta(false);
      }
    };
    
    // Debounce to prevent spamming
    const timeout = setTimeout(fetchDynamicMeta, 300);
    return () => {
      isMounted = false;
      clearTimeout(timeout);
    };
  }, [filters, state]);



  const updateUrlWithFilters = (finalFilters: Record<string, string | string[]>) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(finalFilters)) {
      if (Array.isArray(value)) {
        value.forEach(v => params.append(key, v));
      } else if (value !== undefined && value !== "") {
        params.append(key, value as string);
      }
    }
    window.history.replaceState(null, "", `/estudar?${params.toString()}`);
  };

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Sanitize limit before submitting
    let finalLimit = "50";
    if (typeof filters.limit === "string" && filters.limit.trim() !== "") {
      const parsed = parseInt(filters.limit, 10);
      if (!isNaN(parsed)) {
        if (parsed < 1) finalLimit = "1";
        else if (parsed > 200) finalLimit = "200";
        else finalLimit = parsed.toString();
      }
    }
    const finalFilters = { ...filters, limit: finalLimit };

    if (studyMode === "SIMULADO") {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(finalFilters)) {
        if (Array.isArray(value)) {
          value.forEach(v => params.append(key, v));
        } else if (value !== undefined && value !== "") {
          params.append(key, value as string);
        }
      }
      router.push(`/simulado?${params.toString()}`);
    } else {
      updateUrlWithFilters(finalFilters);
      loadQueue(finalFilters);
    }
  };

  const startRecommendedSession = useCallback((kind: "adaptive" | "review" | "wrong", focus?: "coverage" | "balanced" | "retention") => {
    const limit = kind === "review" || kind === "wrong" ? "20" : "30";
    setStudyMode("TUTOR");
    const activeFilters = {
      limit,
      ...(kind === "adaptive"
        ? { mode: "adaptive", adaptive_focus: focus || "balanced" }
        : kind === "wrong"
        ? { status: "wrong" }
        : { status: "srs_due" }),
    };
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(activeFilters)) {
      params.append(key, value as string);
    }
    window.history.replaceState(null, "", `/estudar?${params.toString()}`);
    loadQueue(activeFilters);
  }, [loadQueue]);

  const triggerAutoFlashcard = useCallback(async (detail: QuestionDetail, letter: string | null) => {
    setAutoGeneratingFlashcard(true);
    try {
      const res = await api.flashcards.generate(detail.id, letter || "A");
      const normalized = normalizeFlashcard({ ...res, stem: detail.stem });
      setFlashcardResult(normalized);
      toast.success("⚡ Flashcard FSRS gerado e salvo para a Revisão Ativa!", { id: `auto-fc-${detail.id}` });
    } catch (e) {
      if (e instanceof OfflineQueuedError) {
        toast("Flashcard FSRS agendado localmente para sincronização.", { icon: "💾", id: `auto-fc-${detail.id}` });
      } else {
        console.warn("Auto-FSRS flashcard silencioso falhou:", e);
      }
    } finally {
      setAutoGeneratingFlashcard(false);
    }
  }, []);

  const handleToggleAutoFsrs = useCallback(() => {
    setAutoFsrsOnWrong(prev => {
      const nextVal = !prev;
      if (typeof window !== "undefined") {
        localStorage.setItem("medquest_auto_fsrs", String(nextVal));
      }
      toast(nextVal ? "Auto-FSRS ativado: flashcards gerados automaticamente ao errar." : "Auto-FSRS pausado: geração manual mantida.", {
        icon: nextVal ? "⚡" : "⚙️"
      });
      return nextVal;
    });
  }, []);

  const handleAttempt = useCallback(async () => {
    if (attemptLockRef.current || attemptResult || isOfflineSaved || submitting || !currentDetail || !selectedLetter) return;
    attemptLockRef.current = true;
    
    setSubmitting(true);

    try {
      const res = await api.questions.submitAttempt(
        currentDetail.id,
        selectedLetter,
        getCurrentTime() * 1000,
        "defer",
        undefined,
        undefined,
        currentDetail.twin_for_question_id
      );
      setAttemptResult(res);
      setIsOfflineSaved(false);
      setSessionAnswers(prev => ({
        ...prev,
        [currentDetail.id]: { letter: selectedLetter, result: res, writtenAnswer: userWrittenAnswer }
      }));

      if (res.is_correct === false && autoFsrsOnWrong) {
        triggerAutoFlashcard(currentDetail, selectedLetter);
      }

    } catch (err) {
      if (err instanceof OfflineQueuedError) {
        toast("Resposta salva neste dispositivo; será sincronizada quando a conexão voltar.", { icon: "💾" });
        setIsOfflineSaved(true);
        setSessionAnswers(prev => ({
          ...prev,
          [currentDetail.id]: { letter: selectedLetter, isOffline: true, writtenAnswer: userWrittenAnswer }
        }));
      } else {
        toast.error("Erro ao enviar resposta.");
      }
    } finally {
      attemptLockRef.current = false;
      setSubmitting(false);
    }
  }, [attemptResult, isOfflineSaved, submitting, currentDetail, selectedLetter, userWrittenAnswer, getCurrentTime, autoFsrsOnWrong, triggerAutoFlashcard]);

  const handleDiscursiveReveal = useCallback(async () => {
    if (attemptLockRef.current || attemptResult || isOfflineSaved || submitting || !currentDetail) return;
    attemptLockRef.current = true;
    
    setSubmitting(true);

    try {
      const res = await api.questions.submitAttempt(
        currentDetail.id, 
        "A", 
        getCurrentTime() * 1000, 
        "defer", 
        null,
        userWrittenAnswer,
        currentDetail.twin_for_question_id
      );
      setAttemptResult(res);
      setIsOfflineSaved(false);
      setSessionAnswers(prev => ({
        ...prev,
        [currentDetail.id]: { letter: "A", result: res, writtenAnswer: userWrittenAnswer, isDiscursive: true }
      }));
    } catch (e: unknown) {
      if (e instanceof OfflineQueuedError) {
        setIsOfflineSaved(true);
        setSessionAnswers(prev => ({
          ...prev,
          [currentDetail.id]: { letter: "A", isOffline: true, writtenAnswer: userWrittenAnswer, isDiscursive: true }
        }));
        toast("Resposta salva neste dispositivo; será sincronizada quando a conexão voltar.", { icon: "💾" });
      } else {
        toast.error("Erro ao enviar resposta.");
      }
    } finally {
      attemptLockRef.current = false;
      setSubmitting(false);
    }
  }, [attemptResult, isOfflineSaved, submitting, currentDetail, userWrittenAnswer, getCurrentTime]);

  const handleQuickSaveFlashcard = async () => {
    if (!currentDetail) return;
    setSavingFlashcard(true);
    try {
      const res = await api.flashcards.generate(currentDetail.id, selectedLetter || "A");
      const normalized = normalizeFlashcard({ ...res, stem: currentDetail.stem });
      setFlashcardResult(normalized);
      setDraftFlashcard(null);
      toast.success("Flashcard adicionado à Revisão Ativa de amanhã!");
    } catch (error) {
      if (error instanceof OfflineQueuedError) {
        toast("Flashcard aguardando sincronização. Ficará disponível para revisão após o envio.", { icon: "💾" });
      } else {
        toast.error("Erro ao criar flashcard instantâneo.");
      }
    } finally {
      setSavingFlashcard(false);
    }
  };

  const handleGenerateFlashcard = async () => {
    if (!currentDetail) return;
    setGeneratingFlashcard(true);
    setDraftFlashcard(null);
    try {
      const res = await api.flashcards.preview(currentDetail.id, selectedLetter || undefined);
      setDraftFlashcard({
        front: res.front,
        back: res.back,
        context: res.context
      });
    } catch {
      toast.error("Erro ao gerar prévia do flashcard.");
    } finally {
      setGeneratingFlashcard(false);
    }
  };

  const handleSaveFlashcard = async () => {
    if (!currentDetail || !draftFlashcard) return;
    setSavingFlashcard(true);
    try {
      const res = await api.flashcards.save(
        currentDetail.id, 
        draftFlashcard.front, 
        draftFlashcard.back, 
        draftFlashcard.context
      );
      const normalized = normalizeFlashcard({ ...res, stem: currentDetail.stem });
      setFlashcardResult(normalized);
      setDraftFlashcard(null);
      toast.success("Flashcard criado e inserido na sua Revisão Ativa!");
    } catch (error) {
      if (error instanceof OfflineQueuedError) {
        toast("Flashcard aguardando sincronização. Ficará disponível para revisão após o envio.", { icon: "💾" });
      } else {
        toast.error("Erro ao salvar flashcard.");
      }
    } finally {
      setSavingFlashcard(false);
    }
  };

  const handleGenerateAllWrongFlashcards = async () => {
    const seen = new Set<number>();
    const wrongItems: Array<{ question_id: number; wrong_letter: string }> = [];
    for (const [qidStr, ans] of Object.entries(sessionAnswers)) {
      const qid = Number(qidStr);
      if (ans.result && !ans.result.is_correct && !seen.has(qid)) {
        seen.add(qid);
        const rawLetter = (ans.letter || "A").trim().slice(0, 1).toUpperCase();
        const wrong_letter = /^[A-E]$/.test(rawLetter) ? rawLetter : "A";
        wrongItems.push({ question_id: qid, wrong_letter });
      }
    }

    if (wrongItems.length === 0) {
      toast("Nenhuma questão errada encontrada nesta sessão.", { icon: "ℹ️" });
      return;
    }

    setGeneratingBatchFlashcards(true);
    try {
      const res = await api.flashcards.generateBatch(wrongItems);
      setBatchFlashcardsResult({ count: res.count });
      if (res.count > 0) {
        toast.success(`${res.count} flashcard(s) criado(s) e adicionado(s) à Revisão Ativa!`);
      } else {
        toast("Nenhum novo flashcard criado (já cadastrados).", { icon: "ℹ️" });
      }
    } catch (e) {
      console.error("Erro ao gerar flashcards em lote:", e);
      if (e instanceof OfflineQueuedError) {
        toast("Criação de flashcards aguardando sincronização.", { icon: "💾" });
      } else {
        toast.error("Erro ao gerar flashcards em lote.");
      }
    } finally {
      setGeneratingBatchFlashcards(false);
    }
  };

  const handleSendMessage = async (overrideText?: string) => {
    if (!currentDetail) return;
    const textToSend = (overrideText ?? preceptorInput).trim();
    if (!textToSend) return;

    const userMsg: ChatMessage = {
      id: "u_" + Date.now(),
      role: "user",
      content: textToSend,
    };

    const nextHistory = [...chatMessages, userMsg];
    setChatMessages(nextHistory);
    setPreceptorInput("");
    setAskingPreceptor(true);

    try {
      const apiHistory = nextHistory.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await api.questions.askAI(
        currentDetail.id,
        textToSend,
        selectedLetter || undefined,
        apiHistory
      );

      const assistantMsg: ChatMessage = {
        id: "a_" + Date.now(),
        role: "assistant",
        content: res.answer,
        model: res.model,
        source: res.source,
        grounding_sources: res.grounding_sources,
        tool_call: res.tool_call,
      };

      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao consultar o preceptor.";
      toast.error(msg);
    } finally {
      setAskingPreceptor(false);
    }
  };

  const nextQuestion = useCallback(() => {
    ensureCurrentQuestionReviewed();
    if (currentIndex + 1 < queue.length) {
      setCurrentIndex(prev => prev + 1);
      loadQuestionDetail(queue[currentIndex + 1].id);
    } else {
      setState("FINISHED");
    }
  }, [currentIndex, queue, loadQuestionDetail, ensureCurrentQuestionReviewed]);

  const handleReviewFSRS = useCallback(async (conf: string, explicitIsCorrect?: boolean) => {
    if (!currentDetail || reviewLockRef.current) return;
    reviewLockRef.current = true;

    // Snapshot variables for background request
    const questionId = currentDetail.id;
    const twinQuestionId = currentDetail.twin_for_question_id;
    const currentAttemptResult = attemptResult;
    const currentSelectedLetter = selectedLetter;
    const currentWrittenAnswer = userWrittenAnswer;
    const isDiscursive = Boolean(currentDetail.is_discursive || (currentDetail.alternatives || []).length <= 1);
    const institutionCode = currentDetail.institution_code;

    // Optimistic UI updates - Update session answers synchronously before advancing
    const isCorr = explicitIsCorrect !== undefined ? explicitIsCorrect : (currentAttemptResult?.is_correct ?? false);
    const optimisticDays = !isCorr ? 7 : conf === "chutei" ? 15 : conf === "certeza" ? 76 : 34;
    const optimisticDueIso =
      currentAttemptResult?.next_review_date ??
      new Date(Date.now() + optimisticDays * 86400_000).toISOString();

    const optimisticResult: AttemptResult = {
      ...(currentAttemptResult || {
        correct_letter: institutionCode || "A",
        explanation: null,
      }),
      is_correct: isCorr,
      next_review_date: optimisticDueIso,
    };
    attemptResultRef.current = optimisticResult;
    reviewedQuestionsRef.current.add(questionId);

    setSessionAnswers(prev => ({
      ...prev,
      [questionId]: {
        letter: currentSelectedLetter || "A",
        result: optimisticResult,
        writtenAnswer: currentWrittenAnswer,
        isDiscursive: isDiscursive
      }
    }));

    reviewLockRef.current = false;
    if (currentIndex + 1 < queue.length) {
      setCurrentIndex(prev => prev + 1);
      loadQuestionDetail(queue[currentIndex + 1].id);
    } else {
      setState("FINISHED");
    }

    // Call API in background to persist FSRS card and next review date
    try {
      const res = await api.questions.reviewFSRS(
        questionId,
        conf,
        explicitIsCorrect,
        twinQuestionId,
        currentAttemptResult?.attempt_id
      );
      const updatedResult: AttemptResult = {
        ...optimisticResult,
        next_review_date: res.next_review_date,
      };

      // Reconcile next_review_date from API response
      setSessionAnswers(prev => ({
        ...prev,
        [questionId]: {
          letter: currentSelectedLetter || "A",
          result: updatedResult,
          writtenAnswer: currentWrittenAnswer,
          isDiscursive: isDiscursive
        }
      }));
    } catch {
      reviewedQuestionsRef.current.delete(questionId);
      toast.error("Erro ao salvar revisão (FSRS) em background.");
    }
  }, [currentDetail, attemptResult, selectedLetter, userWrittenAnswer, currentIndex, queue, loadQuestionDetail]);

  const prevQuestion = useCallback(() => {
    ensureCurrentQuestionReviewed();
    if (currentIndex > 0) {
      setCurrentIndex(prev => prev - 1);
      loadQuestionDetail(queue[currentIndex - 1].id);
    }
  }, [currentIndex, queue, loadQuestionDetail, ensureCurrentQuestionReviewed]);

  const navigateQuestion = useCallback((direction: "next" | "previous") => {
    if (direction === "previous") {
      prevQuestion();
      return;
    }
    nextQuestion();
  }, [nextQuestion, prevQuestion]);

  const toggleFavorite = async () => {
    if (!currentDetail || togglingFavorite || favoriteLockRef.current) return;
    favoriteLockRef.current = true;
    setTogglingFavorite(true);
    const updated = { ...currentDetail, is_favorite: !currentDetail.is_favorite };
    setCurrentDetail(updated);
    detailsCacheRef.current[updated.id] = updated;
    try {
      await api.questions.toggleFavorite(currentDetail.id);
    } catch {
      setCurrentDetail(currentDetail);
      detailsCacheRef.current[currentDetail.id] = currentDetail;
    } finally {
      favoriteLockRef.current = false;
      setTogglingFavorite(false);
    }
  };

  useQuizKeyboard({
    state,
    currentDetail,
    loadingDetail,
    attemptResult,
    currentIndex,
    queue,
    selectedLetter,
    submitting,
    handleAttempt,
    handleDiscursiveReveal,
    handleReviewFSRS,
    nextQuestion,
    prevQuestion,
    navigateQuestion,
    selectAlternative,
    toggleEliminate: toggleEliminateAlternative,
    disabled: Boolean(showFinishModal || isClassificationModalOpen || enlargedImage)
  });

  if (state === "FILTERS") {
    return (
      <QuizFilters
        hasSavedState={hasSavedState}
        savedSessionData={savedSessionData}
        discardSavedQuiz={discardSavedQuiz}
        resumeSavedQuiz={resumeSavedQuiz}
        showCustomSession={showCustomSession}
        setShowCustomSession={setShowCustomSession}
        startRecommendedSession={startRecommendedSession}
        handleFilterSubmit={handleFilterSubmit}
        studyMode={studyMode}
        setStudyMode={setStudyMode}
        filters={filters}
        setFilters={setFilters}
        localLimit={localLimit}
        setLocalLimit={setLocalLimit}
        isUpdatingMeta={isUpdatingMeta}
        dynamicMeta={dynamicMeta}
        subtemaSearch={subtemaSearch}
        setSubtemaSearch={setSubtemaSearch}
        showTopicTree={showTopicTree}
        setShowTopicTree={setShowTopicTree}
      />
    );
  }
  if (state === "LOADING_QUEUE") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
        <p className="text-muted-foreground font-medium">Montando seu simulado...</p>
      </div>
    );
  }

  if (state === "FINISHED") {
    const totalAnswered = Object.keys(sessionAnswers).length;
    const correctCount = Object.values(sessionAnswers).filter(a => a.result?.is_correct).length;
    const wrongItems = Object.entries(sessionAnswers)
      .filter(([, ans]) => ans.result && !ans.result.is_correct)
      .map(([qid, ans]) => ({ question_id: Number(qid), wrong_letter: ans.letter }));
    const accuracy = totalAnswered > 0 ? Math.round((correctCount / totalAnswered) * 100) : 0;

    return (
      <QuizSessionReportModal
        studyMode={studyMode}
        totalAnswered={totalAnswered}
        correctCount={correctCount}
        accuracy={accuracy}
        wrongItems={wrongItems}
        generatingBatchFlashcards={generatingBatchFlashcards}
        batchFlashcardsResult={batchFlashcardsResult}
        onGenerateBatchFlashcards={handleGenerateAllWrongFlashcards}
        onBackToFilters={handleNewSession}
        onRestartSession={() => {
          setState("PLAYING");
          setCurrentIndex(0);
          if (queue.length > 0) {
            loadQuestionDetail(queue[0].id);
          }
        }}
      />
    );
  }

  // PLAYING STATE
  const q = currentDetail;
  const completedCount = Object.values(sessionAnswers).filter(answer => answer.result || answer.isOffline).length;
  const extraCaseImages = filterExtraImages(q?.clinical_case?.images, q?.clinical_case?.stem);
  const extraStemImages = filterExtraImages(q?.images, q?.stem);

  return (
    <div className={clsx("mx-auto w-full flex flex-col gap-4 pb-12 relative", zenMode ? "max-w-4xl" : "max-w-7xl px-2 sm:px-4")}>
      {/* Fullscreen Image Modal */}
      {enlargedImage && (
        <ImageViewer 
          src={resolveImageUrl(enlargedImage)} 
          isOpen={!!enlargedImage} 
          onClose={() => setEnlargedImage(null)} 
        />
      )}
      {/* Top Bar */}
      <QuizHeader
        onBackToFilters={handleBackToFilters}
        completedCount={completedCount}
        totalCount={queue.length}
        onRequestFinish={handleRequestFinish}
        zenMode={zenMode}
        onToggleZenMode={toggleZenMode}
        quizTimerRef={quizTimerRef}
        isTimerRunning={state === "PLAYING" && !!currentDetail && !attemptResult}
        initialTime={initialTime}
        hasQuestion={Boolean(q)}
        isFavorite={q?.is_favorite}
        onToggleFavorite={toggleFavorite}
      />

      {filters.mode === "remediation" && (
        <div className="bg-critical/5 border border-critical/25 text-ink rounded-sm px-3.5 py-2.5 flex items-center justify-between gap-3 text-xs shadow-xs">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-xs bg-critical/15 text-critical font-bold font-mono-lab uppercase text-[10px]">
              🎯 Treino de Recuperação Ativa
            </span>
            <span className="text-ink-muted">
              Focando na retificação das questões erradas e conceitos vulneráveis.
            </span>
          </div>
          {queue[currentIndex]?.remediation_reason === "unresolved_error" ? (
            <span className="hidden sm:inline-flex items-center gap-1 font-semibold text-critical">
              Questão do Caderno de Erros
            </span>
          ) : queue[currentIndex]?.remediation_reason === "twin_unseen_concept" ? (
            <span className="hidden sm:inline-flex items-center gap-1 font-semibold text-accent">
              Questão Gêmea (Conceito Inédito)
            </span>
          ) : null}
        </div>
      )}

      {detailError ? (
        <div className="bg-surface border border-line-subtle shadow-xs rounded-sm p-8 min-h-64 flex flex-col gap-4 items-center justify-center text-center" role="alert">
          <AlertTriangle className="text-critical" size={32} />
          <p className="font-bold text-ink text-sm">Erro ao carregar a questão</p>
          <p className="text-xs text-ink-muted max-w-md">{detailError}</p>
          <button
            onClick={() => queue[currentIndex] && loadQuestionDetail(queue[currentIndex].id)}
            className="flex items-center gap-2 bg-accent text-white px-3.5 py-2 rounded-sm hover:opacity-90 transition-opacity font-semibold text-xs cursor-pointer shadow-xs"
          >
            <RotateCcw size={14} /> Tentar novamente
          </button>
        </div>
      ) : loadingDetail || !q ? (
        <div className="flex flex-col gap-4 animate-pulse">
          <div className="bg-surface border border-line-subtle rounded-sm p-6 h-36" />
          <div className="flex flex-col gap-2.5">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-12 bg-surface border border-line-subtle rounded-sm" />)}
          </div>
        </div>
      ) : (
        <div className={clsx(
          "grid gap-6 items-start w-full",
          zenMode
            ? "grid-cols-1 max-w-4xl mx-auto"
            : "lg:grid-cols-12"
        )}>
          {q.clinical_case && (
            <div className={clsx(
              "bg-surface border border-line-subtle border-l-4 border-l-accent shadow-xs rounded-sm p-5 md:p-6 flex flex-col gap-4",
              !zenMode && "lg:col-span-6 lg:sticky lg:top-20 h-fit max-h-[calc(100vh-6rem)] overflow-y-auto"
            )}>
              <h4 className="text-xs font-bold text-accent uppercase tracking-wider flex items-center gap-2 font-mono-lab">
                <BookOpen size={16} /> Caso Clínico Associado
              </h4>
              <FormattedContent 
                content={q.clinical_case.stem} 
                onImageClick={setEnlargedImage} 
                className="text-ink text-base md:text-lg leading-relaxed font-normal" 
              />
              {extraCaseImages.length > 0 && (
                <div className="flex flex-col sm:flex-row flex-wrap gap-3 mt-1">
                  {extraCaseImages.map((img, i) => (
                    <div 
                      key={i} 
                      className="relative group rounded-sm overflow-hidden border border-line-subtle bg-canvas cursor-zoom-in hover:border-line-strong transition-all sm:max-w-xs"
                      onClick={() => setEnlargedImage(img)}
                    >
                      <Image
                        src={resolveImageUrl(img)} 
                        alt={`Imagem do Caso ${i+1}`} 
                        width={800}
                        height={600}
                        unoptimized
                        className="max-w-full h-auto object-cover hover:scale-[1.01] transition-transform duration-200" 
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Question Stem: quando não há caso clínico, ocupa coluna 7 no desktop */}
          <div className={clsx("flex flex-col gap-5", !zenMode && (q.clinical_case ? "lg:col-span-6" : "lg:col-span-7"))}>
            {/* Question Stem Card */}
            <div className="bg-surface border border-line-subtle shadow-xs rounded-sm p-5 md:p-6 flex flex-col gap-5">
              {q.technical_note && (
                <div className="bg-warning/10 border border-warning/30 rounded-xs p-3.5 flex gap-3 text-ink text-xs shadow-xs">
                  <AlertTriangle className="text-warning shrink-0 mt-0.5" size={18} />
                  <div>
                    <p className="font-bold text-ink mb-0.5 uppercase tracking-wider font-mono-lab text-[11px]">Atenção: Questão Histórica / Desatualizada</p>
                    <p className="leading-relaxed">{q.technical_note}</p>
                  </div>
                </div>
              )}
              <div className="flex items-start md:items-center justify-between flex-col md:flex-row gap-3">
                <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold uppercase tracking-wider">
                  {q.is_verified && (
                    <span className="bg-normal/10 text-normal border border-normal/30 px-2 py-0.5 rounded-xs flex items-center gap-1 text-[11px] font-mono-lab" title={q.last_updated_at ? `Revisado em ${q.last_updated_at}` : "Revisado por um médico"}>
                      <ClinicalIcon name="checkCircle" size={12} /> Revisado
                    </span>
                  )}
                  {Boolean(q.is_discursive || (q.alternatives || []).length <= 1) && (
                    <span className="bg-accent/10 text-accent border border-accent/30 px-2 py-0.5 rounded-xs flex items-center gap-1 font-bold text-[11px] font-mono-lab">
                      Discursiva
                    </span>
                  )}
                  <span className="bg-canvas border border-line-subtle text-ink px-2 py-0.5 rounded-xs font-mono-lab text-[11px] font-bold">
                    {q.institution_code}{q.is_autoral ? " (A)" : ""} {q.year}
                  </span>
                  {q.is_target_institution && (
                    <span
                      className="bg-primary/10 text-primary border border-primary/30 px-2 py-0.5 rounded-xs flex items-center gap-1 font-bold font-mono-lab text-[11px] animate-in fade-in"
                      title="Questão da sua banca-alvo selecionada no Planejador de Residência"
                    >
                      <Target size={12} className="text-primary shrink-0" /> Alvo Residência
                    </span>
                  )}
                  {q.is_twin && (
                    <span
                      className="bg-accent/10 text-accent border border-accent/30 px-2 py-0.5 rounded-xs flex items-center gap-1 font-bold font-mono-lab text-[11px] animate-in fade-in"
                      title={q.twin_origin_institution ? `Questão Gêmea: aplicando o conceito de ${q.twin_subtema || q.subtema} (revisão de ${q.twin_origin_institution}) a um novo caso clínico para testar seu raciocínio real sem vícios de memorização.` : "Questão Gêmea: aplicando o conceito a um novo caso clínico."}
                    >
                      <ClinicalIcon name="sparkles" size={12} />
                      Questão Gêmea{q.twin_origin_institution ? ` (${q.twin_origin_institution})` : ""}
                    </span>
                  )}
                  {(q.area || q.subtema) && (
                    <button
                      type="button"
                      onClick={toggleTopic}
                      className="bg-canvas border border-line-subtle px-2 py-0.5 rounded-xs flex items-center gap-1.5 transition-colors hover:bg-elevated cursor-pointer text-left text-[11px] font-mono-lab text-ink-muted"
                      title={showTopic ? "Ocultar Tema" : "Mostrar Tema"}
                    >
                      {showTopic ? (
                        <>
                          <span className="flex items-center gap-1.5">
                            {q.area && <span>{q.area}</span>}
                            {q.area && q.subtema && <span>&bull;</span>}
                            {q.subtema && <span>{q.subtema}</span>}
                          </span>
                          <EyeOff size={12} className="text-ink-muted ml-0.5" />
                        </>
                      ) : (
                        <>
                          <span>Tema Oculto</span>
                          <Eye size={12} className="text-ink-muted ml-0.5" />
                        </>
                      )}
                    </button>
                  )}
                  {isCurator && (
                    <button
                      type="button"
                      onClick={() => setIsClassificationModalOpen(true)}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs bg-accent/10 hover:bg-accent/20 text-accent border border-accent/25 transition-colors font-bold text-[11px] font-mono-lab cursor-pointer shadow-xs"
                      title="Editar Classificação da Questão (Curadoria)"
                    >
                      <Pencil size={11} /> Editar Tema
                    </button>
                  )}
                </div>
                
                <div className="flex items-center gap-1 bg-canvas px-1.5 py-0.5 rounded-xs border border-line-subtle">
                  <button 
                    onClick={() => navigateQuestion("previous")}
                    disabled={currentIndex === 0 || loadingDetail}
                    className="p-1 min-w-[32px] min-h-[32px] flex items-center justify-center hover:bg-elevated rounded-xs transition-colors disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent text-ink-muted hover:text-ink"
                    title="Questão Anterior (Seta Esquerda)"
                    aria-label="Questão Anterior"
                  >
                    <ClinicalIcon name="arrowLeft" size={14} aria-hidden="true" />
                  </button>
                  <span className="text-xs font-mono-lab tabular-nums font-bold text-ink min-w-[2.5rem] text-center select-none">
                    {currentIndex + 1} / {queue.length}
                  </span>
                  <button 
                    onClick={() => navigateQuestion("next")}
                    disabled={loadingDetail}
                    className="p-1 min-w-[32px] min-h-[32px] flex items-center justify-center hover:bg-elevated rounded-xs transition-colors disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent text-ink-muted hover:text-ink"
                    title="Próxima questão (Seta Direita)"
                    aria-label="Próxima Questão"
                  >
                    <ClinicalIcon name="arrowRight" size={14} aria-hidden="true" />
                  </button>
                </div>
              </div>

              <FormattedContent 
                content={q.stem} 
                onImageClick={setEnlargedImage} 
                className="text-ink text-base md:text-lg leading-relaxed font-normal" 
              />

              {extraStemImages.length > 0 && (
                <div className="flex flex-col sm:flex-row flex-wrap gap-3 mt-2">
                  {extraStemImages.map((img, i) => (
                    <div 
                      key={i} 
                      className="relative group rounded-sm overflow-hidden border border-line-subtle bg-canvas cursor-zoom-in hover:border-line-strong transition-all sm:max-w-sm"
                      onClick={() => setEnlargedImage(img)}
                    >
                      <Image
                        src={resolveImageUrl(img)} 
                        alt={`Imagem ${i+1}`} 
                        width={800}
                        height={600}
                        unoptimized
                        className="max-w-full h-auto object-cover hover:scale-[1.01] transition-transform duration-200" 
                        onError={(e) => { 
                          e.currentTarget.style.display = 'none'; 
                          if (e.currentTarget.nextElementSibling) {
                            (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'flex';
                          }
                        }} 
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center pointer-events-none">
                        <ClinicalIcon name="maximize" size={18} className="text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-md" />
                      </div>
                      <div className="hidden flex-col items-center justify-center p-6 text-ink-muted gap-2">
                        <ImageOff size={24} />
                        <span className="text-xs font-mono-lab">Imagem indisponível</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* PAINEL DIREITO: Alternativas e Ações de Resposta */}
          <div className={clsx(
            "flex flex-col gap-4",
            !zenMode && (
              q.clinical_case
                ? "lg:col-span-6"
                : "lg:col-span-5"
            )
          )}>
            {/* Alternatives or Discursive Response */}
            {Boolean(q.is_discursive || (q.alternatives || []).length <= 1) ? (
              !attemptResult && (
                <div className="bg-surface border border-line-subtle shadow-xs rounded-sm p-5 md:p-6 flex flex-col gap-3.5 animate-in fade-in duration-200">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-accent font-bold text-sm">
                      <ClinicalIcon name="notes" size={16} />
                      <span>Questão Discursiva (Resposta Aberta)</span>
                    </div>
                    <span className="text-[11px] font-mono-lab text-ink-muted">
                      Atalho: <kbd className="bg-canvas px-1 py-0.5 rounded-xs border border-line-subtle text-[10px] text-ink">Ctrl+Enter</kbd>
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted leading-relaxed">
                    Anote seus achados clínicos, hipótese diagnóstica ou conduta antes de revelar o gabarito e padrão oficial da banca:
                  </p>
                  <textarea
                    value={userWrittenAnswer}
                    onChange={(e) => setUserWrittenAnswer(e.target.value)}
                    placeholder="Escreva sua hipótese diagnóstica ou conduta aqui..."
                    rows={4}
                    className="w-full bg-canvas border border-line-subtle focus:border-accent focus:bg-surface rounded-sm p-3.5 text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-1 focus:ring-accent transition-all resize-y text-sm font-normal leading-relaxed min-h-[100px]"
                    onKeyDown={(e) => {
                      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                        e.preventDefault();
                        handleDiscursiveReveal();
                      }
                    }}
                  />
                  <button
                    onClick={handleDiscursiveReveal}
                    disabled={submitting}
                    className="w-full bg-accent hover:opacity-90 text-white font-bold py-3 rounded-sm transition-opacity flex items-center justify-center gap-2 shadow-xs cursor-pointer text-xs uppercase tracking-wider font-mono-lab disabled:opacity-50"
                  >
                    {submitting ? (
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <ClinicalIcon name="checkCircle" size={14} />
                        Confirmar Resposta & Ver Padrão da Banca
                      </>
                    )}
                  </button>
                </div>
              )
            ) : (
              <div className="flex flex-col gap-2.5">
                <AlternativeList
                  alternatives={q.alternatives || []}
                  selectedLetter={selectedLetter}
                  attemptResult={attemptResult}
                  eliminatedLetters={eliminatedAlternatives[q.id] || []}
                  submitting={submitting}
                  onSelectAlternative={selectAlternative}
                  onToggleEliminate={toggleEliminateAlternative}
                />

                {!attemptResult && !isOfflineSaved && selectedLetter && (
                  <button
                    onClick={handleAttempt}
                    disabled={submitting}
                    className="mt-1 w-full bg-accent hover:opacity-90 text-white font-bold py-3 rounded-sm transition-opacity flex items-center justify-center shadow-xs text-xs uppercase tracking-wider font-mono-lab cursor-pointer disabled:opacity-50"
                  >
                    {submitting ? (
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : (
                      "Confirmar Resposta [Enter]"
                    )}
                  </button>
                )}
              </div>
            )}

          {/* Offline Saved Banner */}
          {isOfflineSaved && (
            <div className="bg-accent/10 border border-accent/25 rounded-sm p-4 flex flex-col gap-3 text-ink animate-in slide-in-from-bottom-2 duration-200 shadow-xs mt-2">
              <div className="flex items-center gap-3">
                <CloudOff className="text-accent shrink-0" size={20} />
                <div>
                  <p className="font-bold text-xs uppercase tracking-wider font-mono-lab">Resposta Salva Offline</p>
                  <p className="text-xs text-ink-muted">Sua resposta foi salva neste dispositivo e será sincronizada automaticamente assim que a conexão for restabelecida.</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2.5 pt-2 border-t border-accent/20">
                <button
                  type="button"
                  onClick={async () => {
                    if (!navigator.onLine) {
                      toast("Ainda sem conexão com a internet. Sua resposta segue gravada localmente.", { icon: "💾" });
                      return;
                    }
                    try {
                      const { syncManager } = await import("@/lib/sync");
                      await syncManager.sync(true);
                    } catch (e) {
                      if (e instanceof OfflineQueuedError) {
                        toast("Sem conexão com a internet no momento.", { icon: "💾" });
                      } else {
                        toast.error("Erro ao sincronizar.");
                      }
                    }
                  }}
                  className="flex items-center gap-1.5 text-xs font-mono-lab font-bold text-accent hover:text-accent/80 transition-colors bg-surface border border-line-subtle px-2.5 py-1.5 rounded-xs"
                >
                  <RotateCcw size={12} /> Sincronizar Gabarito Agora
                </button>
                {currentIndex === queue.length - 1 ? (
                  <button
                    type="button"
                    onClick={confirmFinish}
                    className="flex items-center gap-1.5 bg-accent text-white font-mono-lab font-bold px-3 py-1.5 rounded-xs transition-opacity text-xs hover:opacity-90 cursor-pointer shadow-xs"
                  >
                    Finalizar Sessão <CheckCircle2 size={14} />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={nextQuestion}
                    className="flex items-center gap-1.5 bg-accent text-white font-mono-lab font-bold px-3 py-1.5 rounded-xs transition-opacity text-xs hover:opacity-90 cursor-pointer"
                  >
                    Próxima Questão <ArrowRight size={14} />
                  </button>
                )}
              </div>
            </div>
          )}
          </div>

          {/* BLOCO PÓS-TENTATIVA (Abaixo da Questão em Largura Total) */}
          {attemptResult && (
            <div className={clsx(
              "w-full flex flex-col gap-5 animate-in slide-in-from-bottom-2 fade-in duration-200",
              !zenMode && "lg:col-span-12"
            )}>
              {/* If question is discursive, show user's written answer and the board's short expected answer */}
              {Boolean(q.is_discursive || (q.alternatives || []).length <= 1) && (
                <div className="bg-surface border border-line-subtle shadow-xs rounded-sm p-4 md:p-5 flex flex-col gap-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {userWrittenAnswer ? (
                      <div className="flex flex-col gap-1.5 bg-canvas p-3 rounded-xs border border-line-subtle">
                        <div className="flex items-center gap-1.5 text-[11px] font-bold text-ink-muted uppercase tracking-wider font-mono-lab">
                          <ClinicalIcon name="notes" size={13} />
                          <span>Sua Resposta Anotada</span>
                        </div>
                        <div className="text-ink text-sm leading-relaxed whitespace-pre-wrap font-normal">
                          {userWrittenAnswer}
                        </div>
                      </div>
                    ) : null}
                    {q.alternatives?.[0]?.text && !/^(?:anote sua|questão dissertativa|ver padrão)/i.test(q.alternatives[0].text) && (
                      <div className={clsx(
                        "flex flex-col gap-1.5 bg-normal/10 p-3 rounded-xs border border-normal/25",
                        !userWrittenAnswer && "md:col-span-2"
                      )}>
                        <div className="flex items-center gap-1.5 text-[11px] font-bold text-normal uppercase tracking-wider font-mono-lab">
                          <ClinicalIcon name="checkCircle" size={13} />
                          <span>Resposta Curta Esperada pela Banca</span>
                        </div>
                        <div className="text-ink text-sm leading-relaxed font-bold">
                          {q.alternatives[0].text}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className={clsx(
                "rounded-sm border shadow-xs overflow-hidden",
                attemptResult.is_correct === true ? "bg-normal/5 border-normal/25" :
                attemptResult.is_correct === false ? "bg-critical/5 border-critical/25" :
                "bg-surface border-line-subtle"
              )}>
                <div className={clsx(
                  "px-4 py-3 border-b flex items-center justify-between",
                  attemptResult.is_correct === true ? "border-normal/20 bg-normal/10" :
                  attemptResult.is_correct === false ? "border-critical/20 bg-critical/10" :
                  "border-line-subtle bg-canvas"
                )}>
                  <div className="flex items-center gap-2 font-bold text-sm">
                    {attemptResult.is_correct === true ? (
                      <><ClinicalIcon name="checkCircle" size={16} className="text-normal" /> <span className="text-normal font-mono-lab uppercase tracking-wide">Resposta Correta</span></>
                    ) : attemptResult.is_correct === false ? (
                      <><ClinicalIcon name="crossCircle" size={16} className="text-critical" /> <span className="text-critical font-mono-lab uppercase tracking-wide">Resposta Incorreta</span></>
                    ) : (
                      <><ClinicalIcon name="checkCircle" size={16} className="text-accent" /> <span className="text-ink font-mono-lab uppercase tracking-wide">Padrão Oficial da Banca</span></>
                    )}
                  </div>
                  {attemptResult.is_correct !== null && (
                    <div className="flex items-center gap-2">
                      {currentIndex < queue.length - 1 && (
                        <button
                          type="button"
                          onClick={handleRequestFinish}
                          className="flex items-center gap-1 bg-surface border border-line-subtle hover:bg-elevated font-mono-lab text-ink-muted hover:text-ink px-2.5 py-1 rounded-xs transition-colors text-[11px] cursor-pointer"
                          title="Finalizar sessão agora"
                        >
                          <CheckCircle2 size={12} /> Finalizar
                        </button>
                      )}
                      <button
                        onClick={nextQuestion}
                        className="flex items-center gap-1.5 bg-surface border border-line-subtle hover:bg-elevated font-mono-lab font-bold text-ink px-3 py-1 rounded-xs transition-colors text-xs cursor-pointer"
                      >
                        {currentIndex === queue.length - 1 ? (
                          <>Finalizar <CheckCircle2 size={14} className="text-normal" /></>
                        ) : (
                          <>Próxima <ArrowRight size={14} /></>
                        )}
                      </button>
                    </div>
                  )}
                </div>
                
                <div className="p-4 md:p-6 flex flex-col gap-5">
                  <h3 className="text-sm font-bold text-ink flex items-center gap-2 uppercase tracking-wider font-mono-lab">
                    <ClinicalIcon name="notes" size={16} className="text-accent" />
                    {Boolean(q.is_discursive || (q.alternatives || []).length <= 1) ? "Padrão de Resposta da Banca & Comentário" : "Comentário do Professor"}
                  </h3>
                  <ExplanationViewer 
                    explanation={attemptResult.explanation} 
                    correctLetter={Boolean(q.is_discursive || (q.alternatives || []).length <= 1) ? null : attemptResult.correct_letter}
                    questionId={currentDetail?.id}
                    userLetter={selectedLetter || attemptResult.correct_letter || undefined}
                    isDiscursive={Boolean(q.is_discursive || (q.alternatives || []).length <= 1)}
                  />

                  {currentDetail?.times_wrong && currentDetail.times_wrong > 0 ? (
                    <div className="flex items-center gap-1.5 text-xs text-critical font-mono-lab font-semibold bg-critical/10 border border-critical/20 px-2.5 py-1 rounded-xs w-fit">
                      Você já errou esta questão {currentDetail.times_wrong} {currentDetail.times_wrong === 1 ? 'vez' : 'vezes'} no passado.
                    </div>
                  ) : null}
                  
                  {/* Ferramentas de Estudo Ativo: Preceptor AI e Flashcards em grid de 2 colunas no desktop */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
                    {/* Preceptor AI Section */}
                    <PreceptorSection
                      messages={chatMessages}
                      preceptorInput={preceptorInput}
                      askingPreceptor={askingPreceptor}
                      onChangeInput={setPreceptorInput}
                      onSendMessage={handleSendMessage}
                      onClearChat={() => {
                        setChatMessages([]);
                        setPreceptorInput("");
                      }}
                    />

                    {/* Flashcard Generation & FSRS Section */}
                    <QuizFlashcardSection
                      isWrong={attemptResult.is_correct === false}
                      autoGeneratingFlashcard={autoGeneratingFlashcard}
                      autoFsrsOnWrong={autoFsrsOnWrong}
                      onToggleAutoFsrs={handleToggleAutoFsrs}
                      flashcardResult={flashcardResult}
                      draftFlashcard={draftFlashcard}
                      savingFlashcard={savingFlashcard}
                      generatingFlashcard={generatingFlashcard}
                      onQuickSaveFlashcard={handleQuickSaveFlashcard}
                      onGenerateFlashcard={handleGenerateFlashcard}
                      onSaveFlashcard={handleSaveFlashcard}
                      onCancelDraft={() => setDraftFlashcard(null)}
                      onChangeDraft={setDraftFlashcard}
                      onEditSavedFlashcard={() => {
                        if (flashcardResult) {
                          setDraftFlashcard({
                            front: flashcardResult.front,
                            back: flashcardResult.back || "",
                            context: flashcardResult.context || ""
                          });
                          setFlashcardResult(null);
                        }
                      }}
                    />
                  </div>

                  {/* Self-Assessment / FSRS Block */}
                  {attemptResult.is_correct === null ? (
                    <DiscursiveAssessmentSection onReviewFSRS={handleReviewFSRS} />
                  ) : attemptResult.next_review_date ? (
                    <div className="pt-3 border-t border-line-subtle flex items-center justify-between flex-wrap gap-2 text-xs font-mono-lab text-ink-muted">
                      <div className="flex items-center gap-1.5">
                        <Clock size={14} />
                        Próxima revisão FSRS: {new Date(attemptResult.next_review_date).toLocaleDateString('pt-BR')}
                      </div>
                      {Boolean(q.is_discursive || (q.alternatives || []).length <= 1) && (
                        <button
                          onClick={() => setAttemptResult(prev => prev ? { ...prev, is_correct: null } : null)}
                          className="text-xs text-accent hover:underline font-semibold cursor-pointer"
                        >
                          Alterar autoavaliação
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="pt-3 border-t border-line-subtle flex flex-col gap-2.5">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs font-bold text-ink uppercase tracking-wider font-mono-lab">
                          {attemptResult.is_correct 
                            ? "Como foi resolver essa questão?" 
                            : "Revisão agendada (FSRS v6):"}
                        </span>
                        <span className="text-[11px] text-ink-muted">
                          {attemptResult.is_correct
                            ? "Classifique seu nível de domínio para calibrar a repetição espaçada."
                            : "Questões erradas retornam na próxima semana (D+7) para consolidação clínica."}
                        </span>
                      </div>
                      
                      {attemptResult.is_correct ? (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                          <button
                            title="Acertei no chute ou com grande insegurança. Intervalo FSRS: ~15 dias."
                            onClick={() => handleReviewFSRS("chutei")}
                            className="bg-warning/10 hover:bg-warning/20 text-ink border border-warning/30 font-bold py-2.5 px-2 rounded-xs transition-colors text-xs flex flex-col items-center justify-center gap-0.5 cursor-pointer font-mono-lab"
                          >
                            <span className="flex items-center gap-1 font-semibold">🎲 Chutei</span>
                            <span className="text-[10px] text-ink-muted font-normal">+15 dias • [1]</span>
                          </button>
                          <button
                            title="Raciocínio correto, mas exigiu esforço ou dúvida. Intervalo FSRS: ~34 dias."
                            onClick={() => handleReviewFSRS("duvida")}
                            className="bg-accent/10 hover:bg-accent/20 text-ink border border-accent/40 shadow-xs font-bold py-2.5 px-2 rounded-xs transition-colors text-xs flex flex-col items-center justify-center gap-0.5 cursor-pointer font-mono-lab ring-1 ring-accent/20"
                          >
                            <span className="flex items-center gap-1 font-semibold">👍 Com Esforço</span>
                            <span className="text-[10px] text-accent font-normal">+34 dias • [2]</span>
                          </button>
                          <button
                            title="Questão dominada com total convicção. Intervalo FSRS: ~76 dias."
                            onClick={() => handleReviewFSRS("certeza")}
                            className="bg-normal/10 hover:bg-normal/20 text-ink border border-normal/30 font-bold py-2.5 px-2 rounded-xs transition-colors text-xs flex flex-col items-center justify-center gap-0.5 cursor-pointer font-mono-lab"
                          >
                            <span className="flex items-center gap-1 font-semibold">🎯 Domino</span>
                            <span className="text-[10px] text-normal font-normal">+76 dias • [3]</span>
                          </button>
                        </div>
                      ) : (
                        <div className="flex flex-col sm:flex-row gap-2">
                          <button
                            title="Agendada para 7 dias no FSRS v6."
                            onClick={() => handleReviewFSRS("duvida")}
                            className="flex-1 bg-critical/10 hover:bg-critical/20 text-critical border border-critical/30 font-bold py-2.5 px-3 rounded-xs transition-colors text-xs flex items-center justify-center gap-2 cursor-pointer font-mono-lab shadow-xs"
                          >
                            <RotateCcw size={14} />
                            <span>Revisar na Próxima Semana</span>
                            <span className="text-[10px] font-normal py-0.5 px-1.5 bg-critical/15 rounded-xs">D+7 • [Enter]</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {isCurator && q && (
        <QuestionClassificationModal
          isOpen={isClassificationModalOpen}
          onClose={() => setIsClassificationModalOpen(false)}
          questionId={q.id}
          currentArea={q.area}
          currentSubtema={q.subtema}
          currentTopic={q.topic}
          onSuccess={(updated) => {
            setCurrentDetail((prev) => (prev ? { ...prev, area: updated.area, subtema: updated.subtema, topic: updated.topic } : prev));
            setQueue((prevQueue) =>
              prevQueue.map((item, idx) =>
                idx === currentIndex ? { ...item, area: updated.area, subtema: updated.subtema, topic: updated.topic } : item
              )
            );
            toast.success("Tema da questão atualizado com sucesso!");
          }}
          onDelete={(deletedId) => {
            setIsClassificationModalOpen(false);
            delete detailsCacheRef.current[deletedId];
            setSessionAnswers((prev) => {
              const copy = { ...prev };
              delete copy[deletedId];
              return copy;
            });
            setQueue((prevQueue) => {
              const newQueue = prevQueue.filter((item) => item.id !== deletedId);
              if (newQueue.length === 0) {
                setState("FINISHED");
                setCurrentDetail(null);
                return [];
              }
              const nextIndex = currentIndex >= newQueue.length ? newQueue.length - 1 : currentIndex;
              setCurrentIndex(nextIndex);
              loadQuestionDetail(newQueue[nextIndex].id);
              return newQueue;
            });
            toast.success(`Questão #${deletedId} excluída com sucesso!`);
          }}
        />
      )}

      {showFinishModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setShowFinishModal(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="finish-modal-title"
        >
          <div 
            className="bg-card border border-border shadow-2xl rounded-2xl p-6 max-w-md w-full flex flex-col gap-4 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                <CheckCircle2 size={22} />
              </div>
              <div>
                <h3 id="finish-modal-title" className="text-lg font-bold text-foreground">Finalizar Sessão de Estudos?</h3>
                <p className="text-xs text-muted-foreground">Você pode encerrar a sessão a qualquer momento.</p>
              </div>
            </div>

            <div className="bg-muted/40 rounded-xl p-3.5 border border-border/60 text-sm text-foreground/90 leading-relaxed">
              Você respondeu <strong className="text-foreground">{completedCount}</strong> de <strong className="text-foreground">{queue.length}</strong> questões. Restam {queue.length - completedCount} não respondidas.
              <p className="mt-2 text-xs text-muted-foreground">
                Todas as questões já respondidas terão suas revisões (FSRS) preservadas. Ao finalizar, você verá seu relatório de acertos e poderá gerar flashcards dos seus erros.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowFinishModal(false)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              >
                Continuar Respondendo
              </button>
              <button
                type="button"
                onClick={confirmFinish}
                className="px-4 py-2 rounded-xl text-sm font-bold bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm transition-all cursor-pointer flex items-center gap-2"
              >
                <CheckCircle2 size={16} />
                Sim, Finalizar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
