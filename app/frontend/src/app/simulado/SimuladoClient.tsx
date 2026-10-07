"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { QuestionMeta, QuestionListItem, QuestionDetail, BatchAttemptItem, BatchAttemptResultItem, FlashcardGenerateResponse } from "@/types/api";
import { api, OfflineQueuedError } from "@/lib/api";
import { localDb, getLocalOwnerId, isLocalIdentityReady, SimuladoPackage, isPackageValid, isDeviceOffline } from "@/lib/db";
import { getReadySimuladoPackage, downloadSimuladoPackage } from "@/lib/simuladoPackage";
import { useWakeLock } from "@/hooks/useWakeLock";
import {
  AlertTriangle,
  BookOpen,
  AlertCircle,
  RotateCcw,
  CloudOff,
  Sparkles,
  Pencil,
  Eye,
  EyeOff,
  ShieldCheck,
  Scissors
} from "lucide-react";

import clsx from "clsx";
import toast from "react-hot-toast";
import Link from "next/link";
import { useUser } from "@clerk/nextjs";
import { useCurator } from "@/hooks/useCurator";

import { normalizeFlashcard } from "@/lib/normalizeFlashcard";
import { LEARNING_SESSION_VERSION, readLearningSession, writeLearningSession, removeLearningSession, deadlineFromNow } from "@/lib/sessionState";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import { ImageViewer } from "@/components/ImageViewer";
import { ExplanationViewer } from "@/components/ExplanationViewer";
const QuestionClassificationModal = dynamic(
  () => import("@/components/QuestionClassificationModal").then((mod) => mod.QuestionClassificationModal),
  { ssr: false }
);
import { FormattedContent, normalizeImageSrc, filterExtraImages } from "@/components/FormattedContent";
import Image from "next/image";
import { SimuladoStartScreen } from "./components/SimuladoStartScreen";
import { SimuladoResultsView } from "./components/SimuladoResultsView";
import { SimuladoNavGrid } from "./components/SimuladoNavGrid";
import { SimuladoHeader } from "./components/SimuladoHeader";

type SimuladoState = "START" | "LOADING" | "PLAYING" | "SUBMITTING" | "RESULTS" | "OFFLINE_SUBMITTED";

function resolveImageUrl(img: string | null | undefined): string {
  return normalizeImageSrc(img);
}
interface SavedSimuladoState {
  version: number;
  state: SimuladoState;
  queue: QuestionListItem[];
  answers: Record<number, string>;
  deadlineAt: number;
  currentIndex: number;
  resultsMap: Record<number, BatchAttemptResultItem>;
  flagged: Record<number, boolean>;
  force4Options: boolean;
  queueId?: string;
  sessionId?: string;
  plannedDurationSeconds?: number;
  savedAt: number;
  eliminatedMap?: Record<number, string[]>;
  feedbackMode?: "exam" | "practice";
}

function isSavedSimuladoState(value: unknown): value is SavedSimuladoState {
  if (typeof value !== "object" || value === null) return false;
  const saved = value as Partial<SavedSimuladoState>;
  return saved.version === LEARNING_SESSION_VERSION &&
    (saved.state === "PLAYING" || saved.state === "RESULTS" || saved.state === "OFFLINE_SUBMITTED") &&
    Array.isArray(saved.queue) && saved.queue.length > 0 &&
    typeof saved.currentIndex === "number" && saved.currentIndex >= 0 &&
    saved.currentIndex < saved.queue.length &&
    typeof saved.answers === "object" && saved.answers !== null &&
    typeof saved.resultsMap === "object" && saved.resultsMap !== null &&
    typeof saved.flagged === "object" && saved.flagged !== null &&
    typeof saved.deadlineAt === "number" && Number.isFinite(saved.deadlineAt);
}

export function SimuladoClient({
  initialFilters = {},
  meta
}: {
  initialFilters?: Record<string, string | string[]>;
  meta?: QuestionMeta;
}) {
  const { isLoaded: authLoaded } = useUser();
  const { isCurator } = useCurator();
  const [isClassificationModalOpen, setIsClassificationModalOpen] = useState(false);
  const [state, setState] = useState<SimuladoState>("START");
  const [queue, setQueue] = useState<QuestionListItem[]>([]);

  // Quiz State
  const [currentIndex, setCurrentIndex] = useState(0);
  const [detailsCache, setDetailsCache] = useState<Record<number, QuestionDetail>>({});
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const [showAreaSummary, setShowAreaSummary] = useState(false);
  const [showResultsSummary, setShowResultsSummary] = useState(false);
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
  const [enlargedImage, setEnlargedImage] = useState<string | null>(null);

  // Answers: question_id -> letter
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [eliminatedMap, setEliminatedMap] = useState<Record<number, string[]>>({});
  const [resultsMap, setResultsMap] = useState<Record<number, BatchAttemptResultItem>>({});
  const [queueId, setQueueId] = useState<string | undefined>(undefined);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [plannedDurationSeconds, setPlannedDurationSeconds] = useState(0);
  const [isSyncingOffline, setIsSyncingOffline] = useState(false);

  // Flashcards
  const [generatingBatchFlashcards, setGeneratingBatchFlashcards] = useState(false);
  const [batchFlashcardsResult, setBatchFlashcardsResult] = useState<{ count: number } | null>(null);
  const [questionFlashcardsMap, setQuestionFlashcardsMap] = useState<Record<number, FlashcardGenerateResponse>>({});
  const [generatingSingleFlashcard, setGeneratingSingleFlashcard] = useState<number | null>(null);
  const [draftFlashcardsMap, setDraftFlashcardsMap] = useState<Record<number, { front: string; back: string; context: string }>>({});
  const [savingSingleFlashcard, setSavingSingleFlashcard] = useState<number | null>(null);

  // Marcar para revisar
  const [flagged, setFlagged] = useState<Record<number, boolean>>({});

  // Duração proporcional: 3 min/questão (120 Qs = 6h), arredondado
  const [timeLeft, setTimeLeft] = useState(6 * 60 * 60);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const deadlineRef = useRef(0);
  const hasCustomFilters = Object.keys(initialFilters).length > 0;

  const [customConfig, setCustomConfig] = useState({
    institutions: [] as string[],
    years: [] as string[],
    questions_per_area: 20,
    duration_minutes: 300,
    force_4_options: false,
  });

  const [hasSavedState, setHasSavedState] = useState(false);
  const [clientReady, setClientReady] = useState(false);
  const [storageReady, setStorageReady] = useState(false);
  const [force4Options, setForce4Options] = useState(false);
  const [feedbackMode, setFeedbackMode] = useState<"exam" | "practice">(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("medquest_simulado_mode");
      if (saved === "practice" || saved === "exam") return saved;
    }
    return "exam";
  });

  const handleSetFeedbackMode = (mode: "exam" | "practice") => {
    setFeedbackMode(mode);
    if (typeof window !== "undefined") {
      localStorage.setItem("medquest_simulado_mode", mode);
    }
  };
  const summarySavedRef = useRef(new Set<string>());
  const submitLockRef = useRef(false);
  const startLockRef = useRef(false);
  const detailRequestRef = useRef(0);
  const dialogInitialFocusRef = useRef<HTMLButtonElement>(null);
  const customConfigLoadedRef = useRef(false);
  const syncResolutionRef = useRef<"idle" | "pending" | "confirmed_results" | "removed_no_results" | "terminal_failed">("idle");

  const [isOffline, setIsOffline] = useState(false);
  useWakeLock(state === "PLAYING");

  const [offlinePackage, setOfflinePackage] = useState<SimuladoPackage | null>(null);
  const [isDownloadingPackage, setIsDownloadingPackage] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadStatus, setDownloadStatus] = useState("");

  const groupedInstitutions = useMemo(() => {
    const map = new Map<string, { codes: string[], n: number }>();
    const defaultInsts = ['SCMSP', 'USP-SP', 'SUS-SP', 'USP-RP', 'UNIFESP', 'HSL', 'EINSTEIN', 'UNICAMP', 'HRAC-USP'];
    
    if (meta?.institutions) {
        for (const i of meta.institutions) {
            let base = i.institution_code.replace(/\s+\d{4}$/, '').replace(/\s+\d$/, '').trim();
            if (base === 'FAMEMA SP') base = 'FAMEMA';
            if (base === 'SCMRP') base = 'SCM-RP';
            if (base === 'SCM') base = 'SCM-SP';
            
            const existing = map.get(base);
            if (existing) {
                existing.codes.push(i.institution_code);
                existing.n += i.n;
            } else {
                map.set(base, { codes: [i.institution_code], n: i.n });
            }
        }
        return Array.from(map.entries())
            .map(([base, data]) => ({ base, codes: data.codes, n: data.n }))
            .sort((a, b) => b.n - a.n);
    } else {
        return defaultInsts.map(code => ({ base: code, codes: [code], n: 0 }));
    }
  }, [meta]);

  const refreshOfflinePackage = useCallback(async () => {
    if (typeof window === "undefined" || !localDb) return;
    try {
      const uid = getLocalOwnerId();
      const readyPkg = await getReadySimuladoPackage(uid);
      setOfflinePackage(readyPkg);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    const updateOnline = () => {
      setIsOffline(isDeviceOffline());
      void refreshOfflinePackage();
    };

    const initialTimer = setTimeout(() => {
      updateOnline();
    }, 0);

    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    window.addEventListener("forced-offline-changed", updateOnline);
    window.addEventListener("simulado-package-updated", refreshOfflinePackage);

    return () => {
      clearTimeout(initialTimer);
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
      window.removeEventListener("forced-offline-changed", updateOnline);
      window.removeEventListener("simulado-package-updated", refreshOfflinePackage);
    };
  }, [refreshOfflinePackage]);


  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const saved = localStorage.getItem("medquest_simulado_config");
        if (saved) {
          const parsed = JSON.parse(saved) as Partial<typeof customConfig>;
          setCustomConfig(prev => ({
            ...prev,
            institutions: Array.isArray(parsed.institutions) ? parsed.institutions.slice(0, 20) : prev.institutions,
            years: Array.isArray(parsed.years) ? parsed.years.slice(0, 20) : prev.years,
            questions_per_area: Math.max(1, Math.min(100, Number(parsed.questions_per_area) || prev.questions_per_area)),
            duration_minutes: Math.max(15, Math.min(600, Number(parsed.duration_minutes) || prev.duration_minutes)),
            force_4_options: typeof parsed.force_4_options === "boolean" ? parsed.force_4_options : prev.force_4_options,
          }));
        }
      } catch {
        localStorage.removeItem("medquest_simulado_config");
      } finally {
        customConfigLoadedRef.current = true;
      }
    }, 0);
    return () => clearTimeout(timer);
  }, []);


  useEffect(() => {
    if (customConfigLoadedRef.current) {
      localStorage.setItem("medquest_simulado_config", JSON.stringify(customConfig));
    }
  }, [customConfig]);

  useEffect(() => {
    if (showAreaSummary) dialogInitialFocusRef.current?.focus();
  }, [showAreaSummary]);

  useEffect(() => {
    if (!isLocalIdentityReady(authLoaded)) return;
    const timer = setTimeout(() => {
      setHasSavedState(readLearningSession("simulado", isSavedSimuladoState) !== null);
      setStorageReady(true);
      setClientReady(true);
    }, 0);
    return () => clearTimeout(timer);
  }, [authLoaded]);

  const resumeSimulado = () => {
    const saved = readLearningSession("simulado", isSavedSimuladoState);
    if (saved) {
      setState(saved.state);
      setQueue(saved.queue);
      setAnswers(saved.answers);
      deadlineRef.current = saved.deadlineAt;
      setTimeLeft(Math.max(0, Math.ceil((saved.deadlineAt - Date.now()) / 1000)));
      setCurrentIndex(saved.currentIndex);
      setResultsMap(saved.resultsMap);
      setFlagged(saved.flagged);
      setForce4Options(saved.force4Options);
      setQueueId(saved.queueId);
      setSessionId(saved.sessionId);
      if (saved.eliminatedMap) {
        setEliminatedMap(saved.eliminatedMap);
      }
      if (saved.feedbackMode) {
        setFeedbackMode(saved.feedbackMode);
      }
      setPlannedDurationSeconds(saved.plannedDurationSeconds || Math.max(0, saved.deadlineAt - Date.now()));
      setShowResultsSummary(saved.state === "RESULTS");

      const ids = saved.queue.map((question: QuestionListItem) => question.id);
      api.questions.getBatch(ids, saved.force4Options).then(batchRes => {
        const cache: Record<number, QuestionDetail> = {};
        for (const q of batchRes.questions) cache[q.id] = q;
        setDetailsCache(cache);
      }).catch(() => {
        toast.error("Erro ao carregar detalhes do simulado retomado.");
      });
      setHasSavedState(false);
      toast.success("Simulado retomado do ponto em que você parou.");
    }
  };

  useEffect(() => {
    if (!storageReady) return;
    if (state === "PLAYING" || state === "RESULTS" || state === "OFFLINE_SUBMITTED") {
      writeLearningSession("simulado", {
        version: LEARNING_SESSION_VERSION,
        state,
        queue,
        answers,
        deadlineAt: deadlineRef.current,
        currentIndex,
        resultsMap,
        flagged,
        force4Options,
        queueId,
        sessionId,
        plannedDurationSeconds,
        savedAt: Date.now(),
        eliminatedMap,
        feedbackMode,
      } satisfies SavedSimuladoState);
    }
  }, [storageReady, state, queue, answers, currentIndex, resultsMap, flagged, force4Options, queueId, sessionId, plannedDurationSeconds, eliminatedMap, feedbackMode]);

  const handleDownloadOfflineSimulado = async () => {
    if (isDownloadingPackage || isOffline) return;
    setIsDownloadingPackage(true);
    setDownloadProgress(0);
    setDownloadStatus("Iniciando download do pacote...");

    try {
      const questionsPerArea = customConfig.questions_per_area || 20;
      const totalQ = questionsPerArea * 5;
      const pkg = await downloadSimuladoPackage(
        {
          name: `Simulado Offline (${totalQ} Qs)`,
          institutions: customConfig.institutions,
          years: customConfig.years,
          questions_per_area: questionsPerArea,
          duration_minutes: customConfig.duration_minutes,
          force_4_options: customConfig.force_4_options,
        },
        (p: { progress: number; message: string }) => {
          setDownloadProgress(p.progress);
          setDownloadStatus(p.message);
        }
      );
      setOfflinePackage(pkg);
      toast.success("Simulado offline baixado com sucesso!");
    } catch (e) {
      console.error("Erro ao baixar pacote offline:", e);
      const message = e instanceof Error ? e.message : "Erro desconhecido";
      toast.error(`Não foi possível concluir o pacote: ${message}`);
    } finally {
      setTimeout(() => {
        setIsDownloadingPackage(false);
        setDownloadProgress(0);
        setDownloadStatus("");
      }, 1000);
    }
  };

  // Load Simulado
  const startSimulado = async () => {
    if (startLockRef.current) return;
    startLockRef.current = true;
    if (hasSavedState) {
      removeLearningSession("simulado");
      setHasSavedState(false);
    }
    setState("LOADING");
    try {
      // Se offline ou em Modo Plantão, iniciar estritamente a partir do pacote pronto
      if (isDeviceOffline()) {
        const uid = getLocalOwnerId();
        const readyPkg = await getReadySimuladoPackage(uid);
        const validity = isPackageValid(readyPkg);
        if (!validity.valid || !readyPkg) {
          toast.error(validity.reason || "Nenhum pacote offline pronto. Baixe um simulado quando estiver online.");
          setState("START");
          startLockRef.current = false;
          return;
        }

        const cachedQuestions = await localDb.questions
          .where('_owner_id')
          .equals(uid)
          .filter(q => readyPkg.question_ids.includes(q.id))
          .toArray();


        if (cachedQuestions.length === 0 || cachedQuestions.length < readyPkg.questions_count) {
          toast.error("Pacote offline incompleto ou inconsistente. Baixe novamente quando estiver online.");
          setState("START");
          startLockRef.current = false;
          return;
        }

        const qList: QuestionListItem[] = cachedQuestions.map(q => ({
          id: q.id,
          source_file: q.source_file,
          source_number: q.source_number,
          year: q.year,
          institution_code: q.institution_code,
          institution_label: q.institution_label,
          topic: q.topic,
          area: q.area,
          subtema: q.subtema,
        }));

        const cache: Record<number, QuestionDetail> = {};
        for (const q of cachedQuestions) {
          cache[q.id] = q;
        }
        setDetailsCache(cache);

        const durationMinutes = readyPkg.config.duration_minutes || Math.round((qList.length / 20) * 60);
        const calcTime = Math.round(durationMinutes * 60);

        setTimeLeft(calcTime);
        setPlannedDurationSeconds(calcTime);
        deadlineRef.current = deadlineFromNow(calcTime);
        setForce4Options(readyPkg.config.force_4_options || false);
        setSessionId(crypto.randomUUID());

        setQueue(qList);
        setCurrentIndex(0);
        setAnswers({});
        setResultsMap({});
        setFlagged({});
        setState("PLAYING");
        toast.success(`Iniciando Simulado Offline: ${readyPkg.name}`);
        startLockRef.current = false;
        return;
      }

      let qList: QuestionListItem[];
      const isForce4Options = hasCustomFilters ? false : customConfig.force_4_options;
      let durationHours = 6;

      if (hasCustomFilters) {
        const limit = initialFilters.limit || "50";
        qList = await api.questions.getList({ ...initialFilters, limit });
        durationHours = (qList.length / 120) * 6;
      } else {
        qList = await api.questions.getCustomSimulado(customConfig);
        durationHours = customConfig.duration_minutes / 60;
      }

      if (qList.length === 0) {
        toast.error("Erro: Não há questões suficientes para montar o simulado com esses filtros.");
        setState("START");
        return;
      }

      const calcTime = Math.round(durationHours * 60 * 60);
      setTimeLeft(calcTime);
      setPlannedDurationSeconds(calcTime);
      deadlineRef.current = deadlineFromNow(calcTime);
      setForce4Options(isForce4Options);
      setSessionId(crypto.randomUUID());

      setQueue(qList);
      setCurrentIndex(0);
      setAnswers({});
      setResultsMap({});
      setFlagged({});
      setState("PLAYING");

      // Batch prefetch all question details in one request
      const ids = qList.map(q => q.id);
      try {
        const batchRes = await api.questions.getBatch(ids, isForce4Options);
        const cache: Record<number, QuestionDetail> = {};
        for (const q of batchRes.questions) {
          cache[q.id] = q;
        }
        setDetailsCache(cache);
      } catch {
        // Fallback: load first question individually
        loadDetail(qList[0].id);
      }
    } catch {
      toast.error("Erro ao gerar simulado.");
      setState("START");
    } finally {
      startLockRef.current = false;
    }
  };

  const loadDetail = async (id: number) => {
    if (detailsCache[id]) return; // Already cached
    const requestId = ++detailRequestRef.current;
    setLoadingDetail(true);
    setDetailError(false);
    try {
      const detail = await api.questions.getDetail(id);
      setDetailsCache(prev => ({ ...prev, [id]: detail }));
    } catch {
      if (typeof window !== "undefined" && localDb) {
        const uid = getLocalOwnerId();
        const localQuestion = await localDb.questions
          .where('_owner_id')
          .equals(uid)
          .filter(q => q.id === id)
          .first();


        if (localQuestion) {
          setDetailsCache(prev => ({ ...prev, [id]: localQuestion }));
          setLoadingDetail(false);
          return;
        }
      }
      console.error("Erro ao carregar questão", id);
      if (detailRequestRef.current === requestId) setDetailError(true);
    } finally {
      if (detailRequestRef.current === requestId) setLoadingDetail(false);
    }
  };


  const submitSimulado = useCallback(async () => {
    if (submitLockRef.current) return;
    submitLockRef.current = true;
    setState("SUBMITTING");
    if (timerRef.current) clearInterval(timerRef.current);

    const attempts: BatchAttemptItem[] = Object.keys(answers).map(qIdStr => {
      const qId = parseInt(qIdStr);
      return {
        question_id: qId,
        selected_letter: answers[qId],
        confidence: "duvida" // We don't ask for confidence in Simulado, default to duvida
      };
    });

    try {
      const res = await api.questions.submitAttemptBatch(attempts);
      const rMap: Record<number, BatchAttemptResultItem> = {};
      res.results.forEach(r => {
        rMap[r.question_id] = r;
      });
      setResultsMap(rMap);
      setState("RESULTS");
      setShowResultsSummary(true);
      setCurrentIndex(0); // Go back to first question to review

      removeLearningSession("simulado");

    } catch (err) {
      if (err instanceof OfflineQueuedError) {
        toast("Respostas do simulado salvas no dispositivo; serão sincronizadas quando a conexão voltar.", { icon: "💾" });
        syncResolutionRef.current = "pending";
        setQueueId(err.localId);
        setState("OFFLINE_SUBMITTED");
      } else {

        toast.error("Erro ao enviar simulado. Tente novamente.");
        setState("PLAYING");
      }
    } finally {
      submitLockRef.current = false;
    }
  }, [answers]);

  const handleGenerateSingleFlashcard = async (qid: number, wrongLetter: string) => {
    if (generatingSingleFlashcard) return;
    setGeneratingSingleFlashcard(qid);
    try {
      const res = await api.flashcards.preview(qid, wrongLetter || undefined);
      setDraftFlashcardsMap(prev => ({ ...prev, [qid]: res }));
    } catch {
      toast.error("Erro ao gerar prévia do flashcard.");
    } finally {
      setGeneratingSingleFlashcard(null);
    }
  };

  const handleSaveSingleFlashcard = async (qid: number) => {
    const draft = draftFlashcardsMap[qid];
    if (!draft || savingSingleFlashcard) return;
    setSavingSingleFlashcard(qid);
    try {
      const res = await api.flashcards.save(qid, draft.front, draft.back, draft.context);
      const qDetail = detailsCache[qid];
      const normalized = normalizeFlashcard({ ...res, stem: qDetail?.stem || "" });
      setQuestionFlashcardsMap(prev => ({ ...prev, [qid]: normalized }));
      setDraftFlashcardsMap(prev => {
        const next = { ...prev };
        delete next[qid];
        return next;
      });
      toast.success("Flashcard criado e inserido na sua Revisão Ativa!");
    } catch (error) {
      if (error instanceof OfflineQueuedError) {
        toast("Flashcard aguardando sincronização. Ficará disponível para revisão após o envio.", { icon: "💾" });
      } else {
        toast.error("Erro ao salvar flashcard.");
      }
    } finally {
      setSavingSingleFlashcard(null);
    }
  };

  const handleGenerateAllSimuladoWrongFlashcards = async () => {
    const seen = new Set<number>();
    const wrongItems: Array<{ question_id: number; wrong_letter: string }> = [];
    for (const q of queue) {
      if (resultsMap[q.id] && !resultsMap[q.id].is_correct && !seen.has(q.id)) {
        seen.add(q.id);
        const rawLetter = (answers[q.id] || "A").trim().slice(0, 1).toUpperCase();
        const wrong_letter = /^[A-E]$/.test(rawLetter) ? rawLetter : "A";
        wrongItems.push({ question_id: q.id, wrong_letter });
      }
    }

    if (wrongItems.length === 0) {
      toast("Nenhuma questão errada encontrada neste simulado.", { icon: "ℹ️" });
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
      console.error("Erro ao gerar flashcards em lote no simulado:", e);
      if (e instanceof OfflineQueuedError) {
        toast("Criação de flashcards aguardando sincronização.", { icon: "💾" });
      } else {
        toast.error("Erro ao gerar flashcards em lote.");
      }
    } finally {
      setGeneratingBatchFlashcards(false);
    }
  };

  const submitSimuladoRef = useRef(submitSimulado);
  useEffect(() => {
    submitSimuladoRef.current = submitSimulado;
  }, [submitSimulado]);

  // Timer Effect
  useEffect(() => {
    if (state === "PLAYING") {
      timerRef.current = setInterval(() => {
        const remaining = Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000));
        setTimeLeft(remaining);
        if (remaining === 0) {
          if (timerRef.current) clearInterval(timerRef.current);
          setTimeout(() => submitSimuladoRef.current(), 0);
        }
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [state]);

  const handleManualSyncSimulado = useCallback(async () => {
    if (isSyncingOffline) return;
    setIsSyncingOffline(true);
    try {
      const attempts: BatchAttemptItem[] = Object.keys(answers).map(qIdStr => {
        const qId = parseInt(qIdStr, 10);
        return {
          question_id: qId,
          selected_letter: answers[qId],
          confidence: "duvida"
        };
      });

      if (attempts.length === 0) {
        removeLearningSession("simulado");
        setHasSavedState(false);
        setState("START");
        return;
      }

      const { syncManager } = await import("@/lib/sync");
      await syncManager.sync(true);
      // Reuse the queued request and its idempotency key. Reposting the batch
      // here would record every answer twice after connectivity returns.
      toast.success("Sincronização solicitada.");
    } catch (err) {
      if (err instanceof OfflineQueuedError) {
        toast("Ainda sem conexão com a internet. Suas respostas permanecem salvas com segurança.", { icon: "💾" });
      } else {
        toast.error("Erro ao sincronizar. Verifique sua conexão e tente novamente.");
      }
    } finally {
      setIsSyncingOffline(false);
    }
  }, [answers, isSyncingOffline]);

  // Sincronização offline e ouvinte de sucesso
  useEffect(() => {
    if (state !== "OFFLINE_SUBMITTED") return;

    const handleSyncSuccess = (e: Event) => {
      const customEvent = e as CustomEvent<{
        id: string;
        endpoint: string;
        method: string;
        data: unknown;
      }>;
      const detail = customEvent.detail;
      if (!detail) return;

      const isBatchAttempt =
        detail.endpoint.includes("/api/attempt/batch") ||
        detail.endpoint.includes("/api/questions/attempts/batch") ||
        detail.endpoint.includes("attempt") ||
        (queueId && detail.id === queueId);

      if (!isBatchAttempt) return;

      const res = detail.data as { results?: BatchAttemptResultItem[] } | null;

      if (res && Array.isArray(res.results) && res.results.length > 0) {
        // a) Sucesso confirmado com resultados do servidor
        syncResolutionRef.current = "confirmed_results";
        const rMap: Record<number, BatchAttemptResultItem> = {};
        res.results.forEach(r => {
          rMap[r.question_id] = r;
        });
        setResultsMap(rMap);
        removeLearningSession("simulado");
        setHasSavedState(false);
        setState("RESULTS");
        setShowResultsSummary(true);
        setCurrentIndex(0);
        toast.success("Simulado sincronizado e corrigido com sucesso!");
      } else {
        // b) Fila removida sem resposta utilizável
        syncResolutionRef.current = "removed_no_results";
        const rMap: Record<number, BatchAttemptResultItem> = {};
        queue.forEach(q => {
          const detail = detailsCache[q.id];
          const selected = answers[q.id];
          const correctLetter = (detail && "correct_letter" in detail ? (detail as { correct_letter?: string }).correct_letter : undefined) || "A";
          rMap[q.id] = {
            question_id: q.id,
            is_correct: selected === correctLetter,
            correct_letter: correctLetter,
            explanation: (detail && "explanation" in detail ? (detail as { explanation?: string }).explanation : undefined) || detail?.technical_note || null,
            next_review_date: new Date().toISOString(),
          };
        });
        setResultsMap(rMap);
        removeLearningSession("simulado");
        setHasSavedState(false);
        setState("RESULTS");
        setShowResultsSummary(true);
        setCurrentIndex(0);
        toast.success("Simulado sincronizado!");
      }
    };


    window.addEventListener("sync-item-success", handleSyncSuccess);

    const checkAndSync = async () => {
      // Se já resolvido com resultados ou em RESULTS, nunca resetar ou alterar estado
      if (syncResolutionRef.current === "confirmed_results" || syncResolutionRef.current === "removed_no_results") {
        return;
      }

      try {
        const { syncManager } = await import('@/lib/sync');
        if (navigator.onLine) {
          await syncManager.sync();
        }
        if (queueId) {
          const failed = await syncManager.getFailedItems();
          if (failed.find(i => i.id === queueId)) {
            // c) Falha terminal
            syncResolutionRef.current = "terminal_failed";
            toast.error("A sincronização encontrou uma falha terminal. Você pode tentar reenviar as respostas salvas.");
            setState("PLAYING");
            setQueueId(undefined);
            return;
          }
        }
      } catch (e) {
        console.error(e);
      }
    };

    const handleOnline = () => {
      void checkAndSync();
    };
    window.addEventListener("online", handleOnline);
    const interval = setInterval(checkAndSync, 5000);

    return () => {
      window.removeEventListener("sync-item-success", handleSyncSuccess);
      window.removeEventListener("online", handleOnline);
      clearInterval(interval);
    };
  }, [state, queueId, queue, answers, detailsCache]);


  const toggleEliminate = useCallback((letter: string) => {
    if (state !== "PLAYING") return;
    const currentQ = queue[currentIndex];
    if (!currentQ) return;
    const qid = currentQ.id;
    setEliminatedMap(prev => {
      const currentList = prev[qid] || [];
      const isEliminated = currentList.includes(letter);
      const nextList = isEliminated
        ? currentList.filter(l => l !== letter)
        : [...currentList, letter];
      return { ...prev, [qid]: nextList };
    });
    // If eliminating the currently selected letter, clear answer
    setAnswers(prev => {
      if (prev[qid] === letter) {
        const next = { ...prev };
        delete next[qid];
        return next;
      }
      return prev;
    });
  }, [state, queue, currentIndex]);

  const handleSelect = useCallback((letter: string) => {
    if (state !== "PLAYING") return;
    const currentQ = queue[currentIndex];
    if (!currentQ) return;
    const qid = currentQ.id;
    // Un-eliminate if selected
    setEliminatedMap(prev => {
      if (!prev[qid]?.includes(letter)) return prev;
      return {
        ...prev,
        [qid]: prev[qid].filter(l => l !== letter)
      };
    });
    setAnswers(prev => ({ ...prev, [qid]: letter }));

    // No modo Treino/Aprendizado (Feedback imediato), valida e revela a questão na hora
    if (feedbackMode === "practice" && !resultsMap[qid]) {
      api.questions.submitAttempt(qid, letter, 5000, "duvida").then(res => {
        setResultsMap(prev => ({
          ...prev,
          [qid]: {
            question_id: qid,
            is_correct: Boolean(res.is_correct),
            correct_letter: res.correct_letter || "",
            explanation: res.explanation || null,
            next_review_date: res.next_review_date || new Date().toISOString(),
            is_discursive: Boolean(res.is_discursive),
          }
        }));
      }).catch(err => {
        console.error("Erro ao validar feedback imediato em modo treino:", err);
      });
    }
  }, [state, queue, currentIndex, feedbackMode, resultsMap]);

  const toggleFlag = useCallback(() => {
    if (state !== "PLAYING") return;
    const currentQ = queue[currentIndex];
    setFlagged(prev => ({ ...prev, [currentQ.id]: !prev[currentQ.id] }));
  }, [state, queue, currentIndex]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      if (showAreaSummary) {
        if (e.key === "Escape") setShowAreaSummary(false);
        return;
      }

      if (state !== "PLAYING" && state !== "RESULTS") return;

      const key = e.key.toLowerCase();

      // Navigate
      if (key === 'arrowleft') {
        e.preventDefault();
        setCurrentIndex(prev => Math.max(0, prev - 1));
      } else if (key === 'arrowright') {
        e.preventDefault();
        setCurrentIndex(prev => Math.min(queue.length - 1, prev + 1));
      }

      if (state === "PLAYING") {
        // Toggle flag
        if (key === 'f') {
          e.preventDefault();
          toggleFlag();
        }

        // Select alternative (1-5 or a-e)
        const currentQ = queue[currentIndex];
        const detail = detailsCache[currentQ?.id];
        if (detail && detail.alternatives) {
          const idxMap: Record<string, number> = { '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, 'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4 };
          if (key in idxMap) {
            const idx = idxMap[key];
            if (idx < (detail.alternatives || []).length) {
              const letter = detail.alternatives[idx].letter;
              if (e.shiftKey || e.altKey) {
                e.preventDefault();
                toggleEliminate(letter);
              } else {
                handleSelect(letter);
              }
            }
          }
        }

        // Finish/submit
        if (key === 'enter') {
          e.preventDefault();
          setShowAreaSummary(true);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state, currentIndex, queue, detailsCache, handleSelect, toggleEliminate, toggleFlag, showAreaSummary]);



  // Resumo por área para modal de confirmação e resultados
  const areaSummary = useMemo(() => {
    const summary: Record<string, { total: number; answered: number; blank: number; correct: number }> = {};
    for (const q of queue) {
      const area = q.area || "Sem área";
      if (!summary[area]) summary[area] = { total: 0, answered: 0, blank: 0, correct: 0 };
      summary[area].total++;
      if (answers[q.id]) summary[area].answered++;
      else summary[area].blank++;
      if (resultsMap[q.id]?.is_correct) summary[area].correct++;
    }
    return Object.entries(summary).map(([area, data]) => ({ area, ...data }));
  }, [queue, answers, resultsMap]);

  useEffect(() => {
    if (state !== "RESULTS" || !sessionId || queue.length === 0 || summarySavedRef.current.has(sessionId)) return;
    summarySavedRef.current.add(sessionId);
    const correctCount = Object.values(resultsMap).filter(result => result.is_correct).length;
    const elapsedSeconds = Math.max(0, plannedDurationSeconds - timeLeft);
    void api.questions.saveSimuladoSession({
      client_session_id: sessionId,
      planned_duration_seconds: plannedDurationSeconds || 1,
      elapsed_seconds: elapsedSeconds,
      total_questions: queue.length,
      answered_count: Object.keys(answers).length,
      correct_count: correctCount,
      filters: hasCustomFilters ? initialFilters : customConfig,
      area_results: areaSummary.map(row => ({ ...row, correct: queue.filter(question => question.area === row.area && resultsMap[question.id]?.is_correct).length })),
    }).catch(error => {
      if (error instanceof OfflineQueuedError) return;
      summarySavedRef.current.delete(sessionId);
      toast.error("Não foi possível salvar o resumo do simulado. Reabra o resultado para tentar novamente.");
    });
  }, [state, sessionId, queue, resultsMap, answers, plannedDurationSeconds, timeLeft, hasCustomFilters, initialFilters, customConfig, areaSummary]);

  const navigateTo = (index: number) => {
    if (index >= 0 && index < queue.length) {
      setCurrentIndex(index);
      loadDetail(queue[index].id);
    }
  };

  const finishSimulado = () => {
    if (state !== "PLAYING") return;

    const unanswered = queue.length - Object.keys(answers).length;
    if (unanswered > 0) {
      setShowAreaSummary(true);
      return;
    }
    setShowAreaSummary(true);
  };

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (state === "START") {
    return (
      <SimuladoStartScreen
        hasCustomFilters={hasCustomFilters}
        groupedInstitutions={groupedInstitutions}
        metaYears={meta?.years || []}
        customConfig={customConfig}
        setCustomConfig={setCustomConfig}
        offlinePackage={offlinePackage}
        isOffline={isOffline}
        isDownloadingPackage={isDownloadingPackage}
        downloadStatus={downloadStatus}
        downloadProgress={downloadProgress}
        onDownloadOfflineSimulado={handleDownloadOfflineSimulado}
        hasSavedState={hasSavedState}
        clientReady={clientReady}
        onResumeSimulado={resumeSimulado}
        onStartSimulado={startSimulado}
        feedbackMode={feedbackMode}
        setFeedbackMode={handleSetFeedbackMode}
      />
    );
  }


  if (state === "LOADING" || state === "SUBMITTING") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
        <p className="text-muted-foreground font-medium text-lg">
          {state === "LOADING" ? "Gerando cadernos e balanceando questões..." : "Corrigindo gabarito e calculando SRS..."}
        </p>
      </div>
    );
  }

  if (state === "OFFLINE_SUBMITTED") {
    return (
      <div className="max-w-2xl mx-auto py-16 px-6 text-center flex flex-col items-center gap-6 bg-card border border-border rounded-2xl shadow-1 mt-8 animate-in zoom-in-95 duration-200">
        <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center">
          <CloudOff size={32} />
        </div>
        <div className="space-y-3">
          <h2 className="text-2xl font-bold text-foreground">Simulado Salvo Offline</h2>
          <p className="text-muted-foreground text-base">
            Todas as suas {Object.keys(answers).length} respostas foram salvas com segurança neste dispositivo.
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            A correção oficial, gabarito e atualização do seu algoritmo de repetição espaçada (FSRS) serão processados automaticamente assim que sua conexão com a internet for restabelecida.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full max-w-md mt-2">
          <button
            onClick={handleManualSyncSimulado}
            disabled={isSyncingOffline}
            className="flex-1 bg-primary text-primary-foreground font-bold px-6 py-3.5 rounded-xl hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-md text-sm flex items-center justify-center gap-2 cursor-pointer"
          >
            {isSyncingOffline ? (
              <>
                <RotateCcw className="animate-spin" size={18} />
                Sincronizando...
              </>
            ) : (
              <>
                <RotateCcw size={18} />
                Sincronizar e Ver Gabarito
              </>
            )}
          </button>
          <button
            onClick={() => {
              removeLearningSession("simulado");
              setHasSavedState(false);
              setState("START");
            }}
            className="flex-1 bg-muted hover:bg-muted/80 text-foreground font-semibold px-6 py-3.5 rounded-xl transition-colors text-sm cursor-pointer"
          >
            Concluir e Voltar ao Início
          </button>
        </div>
      </div>
    );
  }

  const currentQListItem = queue[currentIndex];
  const qDetail = detailsCache[currentQListItem?.id];
  const extraCaseImages = filterExtraImages(qDetail?.clinical_case?.images, qDetail?.clinical_case?.stem);
  const extraStemImages = filterExtraImages(qDetail?.images, qDetail?.stem);
  const isReview = state === "RESULTS";
  const unansweredCount = queue.length - Object.keys(answers).length;

  return (
    <div className="flex flex-col lg:flex-row gap-6 w-full max-w-[1400px] mx-auto pb-12 lg:h-[calc(100vh-8rem)]">

      {/* Sidebar: Grid de Questões */}
      <SimuladoNavGrid
        isReview={isReview}
        resultsMap={resultsMap}
        queue={queue}
        answers={answers}
        flagged={flagged}
        currentIndex={currentIndex}
        onNavigateTo={navigateTo}
        timeLeft={timeLeft}
        formatTime={formatTime}
        showResultsSummary={showResultsSummary}
        onHideResultsSummary={() => setShowResultsSummary(false)}
        onFinishSimulado={finishSimulado}
      />

      {/* Main Area: Question View */}
      <div className="flex-1 flex flex-col order-2 lg:order-2 h-full">
        {showResultsSummary ? (
          <SimuladoResultsView
            resultsMap={resultsMap}
            queue={queue}
            answers={answers}
            areaSummary={areaSummary}
            batchFlashcardsResult={batchFlashcardsResult}
            generatingBatchFlashcards={generatingBatchFlashcards}
            onGenerateBatchFlashcards={handleGenerateAllSimuladoWrongFlashcards}
            onStartReview={() => setShowResultsSummary(false)}
            initialInstitution={customConfig.institutions?.[0] || queue[0]?.institution_code || "ENARE"}
          />
        ) : detailError ? (
          <div className="bg-card border border-border shadow-1 rounded-xl p-8 flex-1 flex flex-col gap-4 items-center justify-center">
            <AlertCircle className="text-destructive w-10 h-10" />
            <p className="text-foreground font-semibold">Erro ao carregar a questão</p>
            <p className="text-muted-foreground text-sm text-center">Não foi possível carregar os detalhes desta questão. Verifique sua conexão.</p>
            <button
              onClick={() => {
                if (queue[currentIndex]) {
                  loadDetail(queue[currentIndex].id);
                } else {
                  startSimulado();
                }
              }}
              className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors font-medium text-sm mt-2"
            >
              <RotateCcw size={16} /> Tentar Novamente
            </button>
          </div>
        ) : loadingDetail || !qDetail ? (
          <div className="bg-card border border-border shadow-1 rounded-xl p-8 flex-1 flex flex-col gap-6 animate-pulse">
             <div className="h-6 w-32 bg-muted rounded" />
             <div className="h-40 bg-muted rounded-xl" />
             <div className="h-12 bg-muted rounded-xl" />
             <div className="h-12 bg-muted rounded-xl" />
             <div className="h-12 bg-muted rounded-xl" />
          </div>
        ) : (
          <div className="flex flex-col h-full gap-4">
            {/* Nav Header */}
            <SimuladoHeader
              currentIndex={currentIndex}
              totalCount={queue.length}
              answeredCount={Object.keys(answers).length}
              isReview={isReview}
              isFlagged={Boolean(flagged[queue[currentIndex]?.id])}
              onToggleFlag={toggleFlag}
              onNavigatePrev={() => navigateTo(currentIndex - 1)}
              onNavigateNext={() => navigateTo(currentIndex + 1)}
            />

            <div className="bg-card border border-border shadow-1 rounded-xl p-6 md:p-8 flex-1 overflow-x-hidden overflow-y-auto custom-scrollbar relative">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentIndex}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2 }}
                  className="w-full"
                >
                  {qDetail.technical_note && (
                <div className="bg-amber-500/15 border-2 border-amber-500/50 rounded-xl p-5 flex gap-4 text-foreground mb-6 shadow-sm">
                  <AlertTriangle className="text-amber-500 shrink-0 mt-0.5" size={24} />
                  <div className="text-sm">
                    <p className="font-bold text-amber-600 dark:text-amber-500 mb-1 text-base uppercase tracking-wider">Atenção: Questão Histórica / Desatualizada</p>
                    <p className="leading-relaxed font-medium">{qDetail.technical_note}</p>
                  </div>
                </div>
              )}

              <ImageViewer
                src={resolveImageUrl(enlargedImage)}
                isOpen={!!enlargedImage}
                onClose={() => setEnlargedImage(null)}
              />
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-6">
                {qDetail.is_verified && (
                  <span className="bg-success/15 text-success border border-success/30 px-2 py-1 rounded flex items-center gap-1" title={qDetail.last_updated_at ? `Revisado em ${qDetail.last_updated_at}` : "Revisado por um médico"}>
                    <ShieldCheck size={14} className="shrink-0 text-success" /> Revisado
                  </span>
                )}
                <span className="bg-muted px-2 py-1 rounded">{qDetail.institution_code}{qDetail.is_autoral ? " (A)" : ""} {qDetail.year}</span>
                {(qDetail.area || qDetail.subtema) && (
                  <button
                    type="button"
                    onClick={toggleTopic}
                    className="bg-muted px-2 py-1 rounded flex items-center gap-1.5 transition-colors hover:bg-muted/80 cursor-pointer text-left"
                    title={showTopic ? "Ocultar Tema" : "Mostrar Tema"}
                  >
                    {showTopic ? (
                      <>
                        <span className="flex items-center gap-1.5">
                          {qDetail.area && <span>{qDetail.area}</span>}
                          {qDetail.area && qDetail.subtema && <span>&bull;</span>}
                          {qDetail.subtema && <span>{qDetail.subtema}</span>}
                        </span>
                        <EyeOff size={13} className="text-muted-foreground ml-0.5" />
                      </>
                    ) : (
                      <>
                        <span>Tema Oculto</span>
                        <Eye size={13} className="text-muted-foreground ml-0.5" />
                      </>
                    )}
                  </button>
                )}
                {isCurator && (
                  <button
                    type="button"
                    onClick={() => setIsClassificationModalOpen(true)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded bg-primary/10 hover:bg-primary/20 text-primary border border-primary/25 transition-colors font-bold text-[11px] cursor-pointer shadow-xs"
                    title="Editar Classificação da Questão (Curadoria)"
                  >
                    <Pencil size={11} /> Editar Tema
                  </button>
                )}
              </div>

              {/* Clinical Case */}
              {qDetail.clinical_case && (
                <div className="bg-muted/30 border-l-4 border-primary rounded-r-xl p-5 mb-6">
                  <h4 className="text-sm font-bold text-primary mb-3 uppercase tracking-wider">Caso Clínico</h4>
                  <FormattedContent
                    content={qDetail.clinical_case.stem}
                    onImageClick={setEnlargedImage}
                    className="text-foreground text-lg leading-relaxed"
                  />
                  {extraCaseImages.length > 0 && (
                    <div className="flex flex-col sm:flex-row flex-wrap gap-4 mt-4">
                      {extraCaseImages.map((img, i) => (
                        <div
                          key={i}
                          className="relative group rounded-lg overflow-hidden border border-border bg-muted/20 cursor-zoom-in hover:shadow-md transition-all sm:max-w-xs"
                          onClick={() => setEnlargedImage(img)}
                        >
                          <Image
                            src={resolveImageUrl(img)}
                            alt={`Imagem do Caso ${i+1}`}
                            width={800}
                            height={600}
                            unoptimized
                            className="max-w-full h-auto object-cover hover:scale-[1.02] transition-transform duration-300"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <FormattedContent
                content={qDetail.stem}
                onImageClick={setEnlargedImage}
                className="text-foreground text-lg leading-relaxed mb-8"
              />

              {extraStemImages.length > 0 && (
                <div className="flex flex-col sm:flex-row flex-wrap gap-4 mb-8">
                  {extraStemImages.map((img, i) => (
                    <div
                      key={i}
                      className="relative group rounded-lg overflow-hidden border border-border bg-muted/20 cursor-zoom-in hover:shadow-md transition-all sm:max-w-sm"
                      onClick={() => setEnlargedImage(img)}
                    >
                      <Image
                        src={resolveImageUrl(img)}
                        alt={`Imagem ${i+1}`}
                        width={800}
                        height={600}
                        unoptimized
                        className="max-w-full h-auto object-cover hover:scale-[1.02] transition-transform duration-300"
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-col gap-3">
                {qDetail.alternatives.map((alt) => {
                  const isSelected = answers[qDetail.id] === alt.letter;
                  const res = resultsMap[qDetail.id];
                  const isEliminated = (eliminatedMap[qDetail.id] || []).includes(alt.letter);
                  const isQuestionResolved = isReview || (feedbackMode === "practice" && Boolean(res));

                  let altClass = "bg-card border-border hover:bg-muted/50 cursor-pointer";

                  if (isQuestionResolved) {
                    altClass = "bg-card border-border opacity-70 cursor-default";

                    if (res) {
                      if (alt.letter === res.correct_letter) {
                        altClass = "bg-success/20 border-success/60 cursor-default ring-2 ring-success";
                      } else if (isSelected && !res.is_correct) {
                        altClass = "bg-destructive/20 border-destructive/60 cursor-default ring-1 ring-destructive";
                      }
                    } else if (isSelected) {
                      altClass = "bg-primary/20 border-primary cursor-default";
                    }
                  } else {
                    if (isSelected) altClass = "bg-primary/10 border-primary cursor-pointer ring-1 ring-primary";
                    else if (isEliminated) altClass = "bg-muted/20 border-border/60 opacity-60 hover:opacity-85 cursor-pointer shadow-none";
                  }

                  return (
                    <div
                      key={alt.letter}
                      role="button"
                      tabIndex={isQuestionResolved ? -1 : 0}
                      onClick={() => !isQuestionResolved && handleSelect(alt.letter)}
                      onKeyDown={(e) => {
                        if (isQuestionResolved) return;
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleSelect(alt.letter);
                        }
                      }}
                      onContextMenu={(e) => {
                        if (!isQuestionResolved) {
                          e.preventDefault();
                          toggleEliminate(alt.letter);
                        }
                      }}
                      aria-pressed={isSelected}
                      aria-disabled={isQuestionResolved}
                      className={clsx(
                        "group relative text-left p-3.5 sm:p-4 rounded-xl border transition-all flex items-start gap-2.5 sm:gap-3 w-full select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                        altClass
                      )}
                    >
                      {/* Scissors Button / Spacer */}
                      {!isQuestionResolved ? (
                        <button
                          type="button"
                          title={isEliminated ? `Restaurar alternativa ${alt.letter}` : `Riscar alternativa ${alt.letter} (Shift+${alt.letter} ou botão direito)`}
                          aria-label={isEliminated ? `Restaurar alternativa ${alt.letter}` : `Riscar alternativa ${alt.letter}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleEliminate(alt.letter);
                          }}
                          className={clsx(
                            "w-6 h-8 shrink-0 flex items-center justify-center rounded-md transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary",
                            isEliminated
                              ? "opacity-100 text-destructive hover:scale-110"
                              : "opacity-0 group-hover:opacity-80 hover:opacity-100 hover:text-primary max-md:opacity-40 text-muted-foreground"
                          )}
                        >
                          <Scissors size={15} className={clsx("transition-transform duration-150", isEliminated && "rotate-45")} />
                        </button>
                      ) : (
                        <div className="w-6 h-8 shrink-0 flex items-center justify-center text-muted-foreground/40">
                          {isEliminated && res && alt.letter !== res.correct_letter && (
                            <Scissors size={13} className="opacity-40 rotate-45 text-destructive" />
                          )}
                        </div>
                      )}

                      <div className={clsx(
                        "w-8 h-8 shrink-0 flex items-center justify-center rounded-lg font-bold text-sm border border-transparent transition-colors",
                        isQuestionResolved && alt.letter === res?.correct_letter ? "bg-success text-success-foreground" :
                        isQuestionResolved && isSelected && !res?.is_correct ? "bg-destructive text-destructive-foreground" :
                        isSelected && !isQuestionResolved ? "bg-primary text-primary-foreground" :
                        isEliminated && !isQuestionResolved ? "bg-muted/40 text-muted-foreground/60 border-border/50" :
                        "bg-muted text-muted-foreground"
                      )}>
                        {alt.letter}
                      </div>
                      <div className={clsx(
                        "pt-1 text-foreground leading-relaxed flex-1 transition-all",
                        isEliminated && (!isQuestionResolved || alt.letter !== res?.correct_letter) && "line-through text-muted-foreground/75 decoration-muted-foreground/60"
                      )}>
                        {!isQuestionResolved && (qDetail.is_discursive || (qDetail.alternatives || []).length <= 1)
                          ? "Confirmar resposta da questão discursiva"
                          : alt.text}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Review Explanation */}
              {(isReview || (feedbackMode === "practice" && resultsMap[qDetail.id])) && resultsMap[qDetail.id] && (
                <div className="mt-8 animate-in slide-in-from-bottom-4 fade-in duration-300">
                  <div className="rounded-xl border shadow-1 overflow-hidden bg-card">
                    <div className="p-6 md:p-8">
                      <h3 className="text-lg font-bold text-foreground mb-5 flex items-center gap-2">
                        <BookOpen size={20} className="text-primary" />
                        Comentário do Professor
                      </h3>
                      <ExplanationViewer
                        explanation={resultsMap[qDetail.id].explanation}
                        correctLetter={Boolean(qDetail.is_discursive || (qDetail.alternatives || []).length <= 1) ? null : resultsMap[qDetail.id].correct_letter}
                        questionId={qDetail.id}
                        userLetter={answers[qDetail.id] || undefined}
                        isDiscursive={Boolean(qDetail.is_discursive || (qDetail.alternatives || []).length <= 1)}
                      />

                      {!questionFlashcardsMap[qDetail.id] && !draftFlashcardsMap[qDetail.id] && (
                        <div className="mt-6 pt-5 border-t border-border">
                          <button
                            onClick={() => handleGenerateSingleFlashcard(qDetail.id, answers[qDetail.id] || "")}
                            disabled={generatingSingleFlashcard === qDetail.id}
                            className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-2.5 px-5 rounded-xl shadow-sm transition-all disabled:opacity-50 cursor-pointer text-sm"
                          >
                            {generatingSingleFlashcard === qDetail.id ? (
                              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                              <Sparkles size={16} />
                            )}
                            {generatingSingleFlashcard === qDetail.id ? "Gerando Flashcard com IA..." : "Criar Flashcard com IA"}
                          </button>
                        </div>
                      )}

                      {draftFlashcardsMap[qDetail.id] && (
                        <div className="mt-6 pt-5 border-t border-border">
                          <div className="bg-purple-500/10 border border-purple-500/25 rounded-2xl p-5 animate-in slide-in-from-bottom-2 text-left">
                            <div className="flex items-center gap-2 text-purple-600 font-bold text-sm mb-4">
                              <Sparkles size={16} /> Editar Flashcard
                            </div>
                            <div className="space-y-4">
                              <div>
                                <label className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Frente</label>
                                <textarea
                                  value={draftFlashcardsMap[qDetail.id].front}
                                  onChange={(e) => setDraftFlashcardsMap(prev => ({ ...prev, [qDetail.id]: { ...prev[qDetail.id], front: e.target.value } }))}
                                  className="w-full bg-background border border-border rounded-lg p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary min-h-[100px]"
                                />
                              </div>
                              <div>
                                <label className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Verso</label>
                                <textarea
                                  value={draftFlashcardsMap[qDetail.id].back}
                                  onChange={(e) => setDraftFlashcardsMap(prev => ({ ...prev, [qDetail.id]: { ...prev[qDetail.id], back: e.target.value } }))}
                                  className="w-full bg-background border border-border rounded-lg p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary min-h-[120px]"
                                />
                              </div>
                              <div className="flex justify-end gap-3 pt-2">
                                <button
                                  onClick={() => setDraftFlashcardsMap(prev => { const next = {...prev}; delete next[qDetail.id]; return next; })}
                                  disabled={savingSingleFlashcard === qDetail.id}
                                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                                >
                                  Cancelar
                                </button>
                                <button
                                  onClick={() => handleSaveSingleFlashcard(qDetail.id)}
                                  disabled={savingSingleFlashcard === qDetail.id}
                                  className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-5 rounded-lg transition-colors text-sm shadow-sm disabled:opacity-50"
                                >
                                  {savingSingleFlashcard === qDetail.id ? (
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                  ) : (
                                    <BookOpen size={16} />
                                  )}
                                  Salvar Flashcard
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {questionFlashcardsMap[qDetail.id] && (
                        <div className="mt-6 pt-5 border-t border-border">
                          <div className="bg-purple-500/10 border border-purple-500/25 rounded-2xl p-5 animate-in slide-in-from-bottom-2 text-left">
                            <div className="flex items-center justify-between gap-2 mb-3">
                              <div className="flex items-center gap-2 text-purple-600 font-bold text-sm">
                                <Sparkles size={16} /> Flashcard Salvo na Revisão Ativa!
                              </div>
                              <Link
                                href="/revisao-ativa"
                                className="text-xs font-bold text-purple-600 hover:underline flex items-center gap-1"
                              >
                                Ir para Revisão Ativa →
                              </Link>
                            </div>
                            <div className="text-foreground text-sm space-y-2">
                              <div className="font-medium bg-background p-3.5 rounded-lg border border-border leading-relaxed whitespace-pre-line text-sm">
                                <span className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Frente:</span>
                                {questionFlashcardsMap[qDetail.id].front}
                              </div>
                              {questionFlashcardsMap[qDetail.id].back && (
                                <div className="text-muted-foreground bg-background p-3.5 rounded-lg border border-border leading-relaxed whitespace-pre-line text-sm">
                                  <span className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Verso:</span>
                                  {questionFlashcardsMap[qDetail.id].back}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Warning if missed */}
              {isReview && !answers[qDetail.id] && (
                <div className="mt-4 bg-destructive/10 text-destructive border border-destructive/20 rounded-lg p-4 flex items-center gap-3 w-full text-sm font-medium">
                  <AlertCircle size={20} className="shrink-0" />
                  Você não respondeu esta questão no simulado.
                </div>
              )}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>

      {showAreaSummary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="simulado-submit-title"
            className="bg-card border border-border shadow-lg rounded-xl p-6 max-w-md w-full flex flex-col gap-4 animate-in zoom-in-95 duration-200"
          >
            <h3 id="simulado-submit-title" className="font-bold text-lg text-foreground">Resumo por Área</h3>

            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left px-3 py-2 font-semibold text-muted-foreground">Área</th>
                    <th className="text-center px-3 py-2 font-semibold text-muted-foreground">Resp.</th>
                    <th className="text-center px-3 py-2 font-semibold text-muted-foreground">Branco</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {areaSummary.map(row => (
                    <tr key={row.area}>
                      <td className="px-3 py-2 text-foreground font-medium">{row.area}</td>
                      <td className="px-3 py-2 text-center text-success font-semibold">{row.answered}</td>
                      <td className={clsx("px-3 py-2 text-center font-semibold", row.blank > 0 ? "text-destructive" : "text-muted-foreground")}>
                        {row.blank}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-muted/30 border-t border-border">
                  <tr>
                    <td className="px-3 py-2 font-bold text-foreground">Total</td>
                    <td className="px-3 py-2 text-center font-bold text-success">{Object.keys(answers).length}</td>
                    <td className={clsx("px-3 py-2 text-center font-bold", unansweredCount > 0 ? "text-destructive" : "text-muted-foreground")}>
                      {unansweredCount}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {unansweredCount > 0 && (
              <div className="bg-warning/10 text-warning border border-warning/20 rounded-lg p-3 flex items-start gap-2 text-sm">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <span>Você ainda tem {unansweredCount} questão(ões) em branco.</span>
              </div>
            )}

            <div className="flex justify-end gap-3 mt-2">
              <button
                ref={dialogInitialFocusRef}
                onClick={() => setShowAreaSummary(false)}
                className="px-4 py-2 bg-muted text-muted-foreground rounded-lg font-medium hover:bg-muted/80 transition-colors"
              >
                Voltar à Prova
              </button>
              <button
                onClick={() => {
                  setShowAreaSummary(false);
                  submitSimulado();
                }}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors"
              >
                Entregar Prova
              </button>
            </div>
          </div>
        </div>
      )}

      {isCurator && qDetail && (
        <QuestionClassificationModal
          isOpen={isClassificationModalOpen}
          onClose={() => setIsClassificationModalOpen(false)}
          questionId={qDetail.id}
          currentArea={qDetail.area}
          currentSubtema={qDetail.subtema}
          currentTopic={qDetail.topic}
          onSuccess={(updated) => {
            setDetailsCache((prev) => ({
              ...prev,
              [qDetail.id]: {
                ...prev[qDetail.id],
                area: updated.area,
                subtema: updated.subtema,
                topic: updated.topic,
              },
            }));
            setQueue((prevQueue) =>
              prevQueue.map((item) =>
                item.id === qDetail.id
                  ? { ...item, area: updated.area, subtema: updated.subtema, topic: updated.topic }
                  : item
              )
            );
            toast.success("Tema da questão atualizado com sucesso!");
          }}
          onDelete={(deletedId) => {
            setIsClassificationModalOpen(false);
            setDetailsCache((prev) => {
              const copy = { ...prev };
              delete copy[deletedId];
              return copy;
            });
            setAnswers((prev) => {
              const copy = { ...prev };
              delete copy[deletedId];
              return copy;
            });
            setFlagged((prev) => {
              const copy = { ...prev };
              delete copy[deletedId];
              return copy;
            });
            setQueue((prevQueue) => {
              const newQueue = prevQueue.filter((item) => item.id !== deletedId);
              if (newQueue.length === 0) {
                toast("Todas as questões do simulado foram concluídas ou removidas.");
                return [];
              }
              if (currentIndex >= newQueue.length) {
                setCurrentIndex(newQueue.length - 1);
              }
              return newQueue;
            });
            toast.success(`Questão #${deletedId} excluída com sucesso!`);
          }}
        />
      )}
    </div>
  );
}
