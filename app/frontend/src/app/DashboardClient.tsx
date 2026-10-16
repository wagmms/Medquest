"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useUser } from "@clerk/nextjs";
import { isLocalIdentityReady } from "@/lib/db";
import { api } from "@/lib/api";
import { 
  OverviewStats, PlannerWeek, PlannerTopic,
  BenchmarkStat, BottleneckTopic, DomainSummaryResponse, ErrorNotebookSummary,
  DashboardSummaryResponse
} from "@/types/api";
import { motion, Variants } from "framer-motion";
import { useEffect, useRef, useState, useCallback } from "react";
import { readLearningSession, syncSessionFromCloud } from "@/lib/sessionState";
import { triggerConfetti } from "@/lib/confetti";
import { PreceptorFocusCard } from "@/components/PreceptorFocusCard";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";
import clsx from "clsx";

const DASHBOARD_CACHE_KEY = "medquest_dashboard_cache_v1";

interface DashboardCachedData {
  stats: OverviewStats;
  currentPlannerWeek: PlannerWeek | null;
  suggestedPlannerTopic?: PlannerTopic | null;
  remainingPlannerMetas?: number;
  isPlanCompleted?: boolean;
  benchmarkStats?: BenchmarkStat | null;
  bottlenecks?: BottleneckTopic[];
  domainSummary?: DomainSummaryResponse | null;
  errorNotebook?: ErrorNotebookSummary | null;
  timestamp: number;
}

const OfflineModal = dynamic(
  () => import("@/components/OfflineModal").then((m) => m.OfflineModal),
  { ssr: false }
);

function formatExamDate(dateStr: string): string {
  try {
    const parts = dateStr.slice(0, 10).split("-");
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(year, month, day, 12, 0, 0);
      return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
    }
  } catch {
    // fallback to default parsing
  }
  return dateStr;
}

interface DashboardClientProps {
  stats: OverviewStats;
  currentPlannerWeek: PlannerWeek | null;
  suggestedPlannerTopic?: PlannerTopic | null;
  remainingPlannerMetas?: number;
  isPlanCompleted?: boolean;
  firstName: string;
  benchmarkStats?: BenchmarkStat | null;
  bottlenecks?: BottleneckTopic[];
  domainSummary?: DomainSummaryResponse | null;
  errorNotebook?: ErrorNotebookSummary | null;
  hasOverviewError?: boolean;
  hasPlannerError?: boolean;
}

export function DashboardClient({ 
  stats: initialStats, 
  currentPlannerWeek: initialPlannerWeek, 
  suggestedPlannerTopic: initialSuggestedPlannerTopic,
  remainingPlannerMetas: initialRemainingPlannerMetas,
  isPlanCompleted: initialIsPlanCompleted,
  firstName, 
  benchmarkStats: initialBenchmarkStats,
  bottlenecks: initialBottlenecks = [],
  domainSummary: initialDomainSummary,
  errorNotebook: initialErrorNotebook,
  hasOverviewError: initialHasOverviewError = false,
  hasPlannerError: initialHasPlannerError = false,
}: DashboardClientProps) {
  const { isLoaded: authLoaded } = useUser();
  const hasAnimated = useRef(false);
  const [activeSession, setActiveSession] = useState<{ kind: "quiz" | "simulado"; url: string } | null>(null);
  const [isOfflineModalOpen, setIsOfflineModalOpen] = useState(false);

  // Estados reativos internos para dados e auto-recuperação
  const [stats, setStats] = useState<OverviewStats>(initialStats);
  const [currentPlannerWeek, setCurrentPlannerWeek] = useState<PlannerWeek | null>(initialPlannerWeek);
  const [suggestedPlannerTopic, setSuggestedPlannerTopic] = useState<PlannerTopic | null | undefined>(initialSuggestedPlannerTopic);
  const [remainingPlannerMetas, setRemainingPlannerMetas] = useState<number>(initialRemainingPlannerMetas ?? 0);
  const [isPlanCompleted, setIsPlanCompleted] = useState<boolean>(initialIsPlanCompleted ?? false);
  const [benchmarkStats, setBenchmarkStats] = useState<BenchmarkStat | null | undefined>(initialBenchmarkStats);
  const [bottlenecks, setBottlenecks] = useState<BottleneckTopic[]>(initialBottlenecks);
  const [domainSummary, setDomainSummary] = useState<DomainSummaryResponse | null | undefined>(initialDomainSummary);
  const [errorNotebook, setErrorNotebook] = useState<ErrorNotebookSummary | null | undefined>(initialErrorNotebook);
  const [hasOverviewError, setHasOverviewError] = useState<boolean>(initialHasOverviewError);
  const [hasPlannerError, setHasPlannerError] = useState<boolean>(initialHasPlannerError);

  const [isReconnecting, setIsReconnecting] = useState<boolean>(false);
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);
  const [isUsingCache, setIsUsingCache] = useState<boolean>(false);

  useEffect(() => {
    // Dispara confete se as revisões diárias estiverem zeradas e houver pelo menos 1 questão feita
    if (stats.srs_due_count === 0 && (stats.flashcards_due_count || 0) === 0 && stats.distinct_answered > 0 && !hasAnimated.current) {
      hasAnimated.current = true;
      triggerConfetti();
    }
  }, [stats]);

  useEffect(() => {
    if (!isLocalIdentityReady(authLoaded)) return;
    let active = true;
    // Check for active sessions
    const checkSessions = async () => {
      // Sincroniza da nuvem de forma assíncrona para não travar o carregamento
      await Promise.allSettled([
        syncSessionFromCloud<{ state?: string }>("simulado", (val): val is { state?: string } => typeof val === "object" && val !== null),
        syncSessionFromCloud<{ state?: string }>("quiz", (val): val is { state?: string } => typeof val === "object" && val !== null)
      ]);

      if (!active) return;
      const hasSimulado = readLearningSession<{ state?: string }>(
        "simulado",
        (val): val is { state?: string } => typeof val === "object" && val !== null
      );
      if (hasSimulado?.state === "PLAYING" || hasSimulado?.state === "SUBMITTING") {
        setActiveSession({ kind: "simulado", url: "/simulado" });
      } else {
        const hasQuiz = readLearningSession<{ state?: string }>(
          "quiz",
          (val): val is { state?: string } => typeof val === "object" && val !== null
        );
        if (hasQuiz?.state === "PLAYING") {
          setActiveSession({ kind: "quiz", url: "/estudar?resume=true" });
        } else {
          setActiveSession(null);
        }
      }
    };
    void checkSessions();

    const handleSessionChange = () => {
      if (active) void checkSessions();
    };

    window.addEventListener("learning-session-changed", handleSessionChange);
    window.addEventListener("focus", handleSessionChange);

    return () => {
      active = false;
      window.removeEventListener("learning-session-changed", handleSessionChange);
      window.removeEventListener("focus", handleSessionChange);
    };
  }, [authLoaded]);

  // Listen to open-offline-modal custom event
  useEffect(() => {
    const handleOpenOffline = () => setIsOfflineModalOpen(true);
    window.addEventListener("open-offline-modal", handleOpenOffline);
    return () => window.removeEventListener("open-offline-modal", handleOpenOffline);
  }, []);

  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const updateOnline = () => {
      if (typeof navigator !== "undefined") {
        setIsOffline(!navigator.onLine);
      }
    };
    updateOnline();
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    return () => {
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
    };
  }, []);

  const applySummaryData = useCallback((summaryData: DashboardSummaryResponse) => {
    if (summaryData.stats) {
      setStats(summaryData.stats);
      setHasOverviewError(false);
    }
    if (summaryData.benchmark !== undefined) setBenchmarkStats(summaryData.benchmark);
    if (summaryData.bottlenecks !== undefined) setBottlenecks(summaryData.bottlenecks || []);
    if (summaryData.domain_summary !== undefined) setDomainSummary(summaryData.domain_summary);
    if (summaryData.error_notebook !== undefined) setErrorNotebook(summaryData.error_notebook);
    setIsUsingCache(false);

    const planner = summaryData.planner;
    const config = planner?.config;
    const progressMap = planner?.progress || {};
    const topicProgressMap = planner?.topic_progress || {};

    if (config && config.exam_date && config.start_date) {
      api.planner.generatePlan({
        start_date: config.start_date,
        exam_date: config.exam_date,
        hours_per_week: Math.min(168, (config.days_per_week || 5) * (config.hours_per_day || 4)),
        intensive: false
      }).then((planResponse) => {
        if (planResponse.plan && planResponse.plan.length > 0) {
          let foundWeek = null;
          let foundTopic = null;
          let metas = 0;
          let completed = false;

          for (const week of planResponse.plan) {
            if (progressMap[week.week.toString()]?.studied) continue;
            const pending = (week.topics || []).filter(
              (t) => !topicProgressMap[`${week.week}:${t.subtema}`] && !topicProgressMap[t.subtema]
            );
            if (pending.length > 0) {
              foundWeek = week;
              foundTopic = pending[0];
              metas = pending.length;
              break;
            }
          }

          if (!foundTopic && planResponse.plan.length > 0) {
            completed = true;
            foundWeek = planResponse.plan[planResponse.plan.length - 1];
          }

          setCurrentPlannerWeek(foundWeek);
          setSuggestedPlannerTopic(foundTopic);
          setRemainingPlannerMetas(metas);
          setIsPlanCompleted(completed);
          setHasPlannerError(false);
        }
      }).catch((planErr) => {
        console.warn("[Dashboard] Erro ao sincronizar planner no cliente:", planErr);
      });
    }

    try {
      const cachePayload: DashboardCachedData = {
        stats: summaryData.stats || stats,
        currentPlannerWeek,
        suggestedPlannerTopic,
        remainingPlannerMetas,
        isPlanCompleted,
        benchmarkStats: summaryData.benchmark,
        bottlenecks: summaryData.bottlenecks || [],
        domainSummary: summaryData.domain_summary,
        errorNotebook: summaryData.error_notebook,
        timestamp: Date.now(),
      };
      localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(cachePayload));
    } catch {}
  }, [currentPlannerWeek, isPlanCompleted, remainingPlannerMetas, stats, suggestedPlannerTopic]);

  const fetchDashboardDataRef = useRef<((retryCount?: number) => Promise<boolean>) | null>(null);

  const fetchDashboardData = useCallback(async (retryCount = 0) => {
    setIsReconnecting(true);
    setReconnectAttempt(retryCount + 1);
    try {
      const data = await api.stats.getDashboardSummary();
      if (data && data.stats) {
        applySummaryData(data);
        setIsReconnecting(false);
        setReconnectAttempt(0);
        return true;
      }
    } catch (err) {
      console.warn(`[Dashboard] Falha na tentativa ${retryCount + 1} de sincronização:`, err);
    }

    if (retryCount < 4) {
      const delay = [2000, 4000, 6000, 10000][retryCount] || 5000;
      setTimeout(() => {
        void fetchDashboardDataRef.current?.(retryCount + 1);
      }, delay);
    } else {
      setIsReconnecting(false);
    }
    return false;
  }, [applySummaryData]);

  useEffect(() => {
    fetchDashboardDataRef.current = fetchDashboardData;
  }, [fetchDashboardData]);

  // Efeito de persistência e auto-recuperação do cache local
  useEffect(() => {
    if (!initialHasOverviewError) {
      try {
        const cachePayload: DashboardCachedData = {
          stats: initialStats,
          currentPlannerWeek: initialPlannerWeek,
          suggestedPlannerTopic: initialSuggestedPlannerTopic,
          remainingPlannerMetas: initialRemainingPlannerMetas,
          isPlanCompleted: initialIsPlanCompleted,
          benchmarkStats: initialBenchmarkStats,
          bottlenecks: initialBottlenecks,
          domainSummary: initialDomainSummary,
          errorNotebook: initialErrorNotebook,
          timestamp: Date.now(),
        };
        localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(cachePayload));
      } catch {}
      return;
    }

    const timer = setTimeout(() => {
      let loadedFromCache = false;
      try {
        const raw = localStorage.getItem(DASHBOARD_CACHE_KEY);
        if (raw) {
          const cached: DashboardCachedData = JSON.parse(raw);
          if (cached && cached.stats) {
            setStats(cached.stats);
            if (cached.currentPlannerWeek !== undefined) setCurrentPlannerWeek(cached.currentPlannerWeek);
            if (cached.suggestedPlannerTopic !== undefined) setSuggestedPlannerTopic(cached.suggestedPlannerTopic);
            if (cached.remainingPlannerMetas !== undefined) setRemainingPlannerMetas(cached.remainingPlannerMetas);
            if (cached.isPlanCompleted !== undefined) setIsPlanCompleted(cached.isPlanCompleted);
            if (cached.benchmarkStats !== undefined) setBenchmarkStats(cached.benchmarkStats);
            if (cached.bottlenecks !== undefined) setBottlenecks(cached.bottlenecks);
            if (cached.domainSummary !== undefined) setDomainSummary(cached.domainSummary);
            if (cached.errorNotebook !== undefined) setErrorNotebook(cached.errorNotebook);
            setHasOverviewError(false);
            setIsUsingCache(true);
            loadedFromCache = true;
          }
        }
      } catch {}

      setTimeout(() => {
        void fetchDashboardDataRef.current?.(0);
      }, loadedFromCache ? 600 : 100);
    }, 50);

    return () => clearTimeout(timer);
  }, [
    initialHasOverviewError,
    initialStats,
    initialPlannerWeek,
    initialSuggestedPlannerTopic,
    initialRemainingPlannerMetas,
    initialIsPlanCompleted,
    initialBenchmarkStats,
    initialBottlenecks,
    initialDomainSummary,
    initialErrorNotebook,
  ]);

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.06 }
    }
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 8 },
    show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 320, damping: 26 } }
  };

  // Métricas de Decisão Diária
  const pendentesRevisao = (stats.srs_due_count || 0) + (stats.flashcards_due_count || 0);
  const dailyTarget = stats.daily_target || 20;
  const todayDone = stats.today_answered || 0;
  const dailyRemaining = Math.max(0, dailyTarget - todayDone);
  const dailyProgressPct = Math.min(100, Math.round((todayDone / dailyTarget) * 100));

  const sugestaoTema = suggestedPlannerTopic
    ? suggestedPlannerTopic.subtema 
    : (bottlenecks.length > 0 ? bottlenecks[0].subtema : "Clínica Médica");

  const sugestaoArea = suggestedPlannerTopic
    ? suggestedPlannerTopic.area
    : (bottlenecks.length > 0 ? bottlenecks[0].area : "");

  const topBottleneck = bottlenecks.length > 0 ? bottlenecks[0] : null;

  const totalAttempts = benchmarkStats?.total_attempts || stats.total_attempts || 0;
  const rawTarget = stats.target_score || benchmarkStats?.target_score_pct || 76;
  const targetScorePct = rawTarget <= 1 ? rawTarget * 100 : rawTarget;
  const overallAccPct = stats.accuracy_all_attempts != null ? stats.accuracy_all_attempts * 100 : null;
  const diffPct = overallAccPct != null ? parseFloat((overallAccPct - targetScorePct).toFixed(1)) : null;

  // Semanas do planner
  const plannerWeekNum = suggestedPlannerTopic ? (currentPlannerWeek?.week || null) : null;
  const plannerMetasCount = remainingPlannerMetas !== undefined ? remainingPlannerMetas : (currentPlannerWeek?.topics?.length || 0);

  // Subtítulo Contextual Direto
  const subtitleMessage = (() => {
    if (hasOverviewError) {
      return isReconnecting
        ? "Conectando ao servidor em nuvem e sincronizando suas métricas..."
        : "Suas métricas estão temporariamente indisponíveis. Você pode continuar estudando pelo menu.";
    }
    if (stats.distinct_answered === 0) {
      return "Defina seu plano e resolva 20 questões para calibrar seu diagnóstico inicial.";
    }
    if (pendentesRevisao > 0) {
      return `Foco de hoje: ${pendentesRevisao} ${pendentesRevisao === 1 ? 'revisão pendente' : 'revisões pendentes'} para blindar sua curva de esquecimento.`;
    }
    if (dailyRemaining > 0) {
      return `Você está a ${dailyRemaining} ${dailyRemaining === 1 ? 'questão' : 'questões'} de bater a meta diária de hoje.`;
    }
    return "Todas as metas de estudo de hoje concluídas! Excelente consistência.";
  })();

  // Determina a Ação Principal (Hero CTA)
  const renderPrimaryAction = () => {
    // 1. Retomar sessão ativa
    if (activeSession) {
      return (
        <div className="bg-surface border border-line-strong rounded-sm p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative overflow-hidden min-w-0">
          <div className="flex items-center gap-3 sm:gap-4 relative z-10 min-w-0 flex-1">
            <div className="w-10 h-10 rounded-xs bg-ink-primary text-surface flex items-center justify-center shrink-0 shadow-2xs">
              <ClinicalIcon name={activeSession.kind === "simulado" ? "description" : "menu_book"} className="w-5 h-5 text-canvas" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="px-1.5 py-0.5 rounded-xs text-[10px] font-mono-lab font-bold uppercase tracking-wider bg-elevated border border-line-subtle text-accent">
                  Sessão em Andamento
                </span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-ink-primary break-words">Retomar {activeSession.kind === "simulado" ? "Simulado" : "Sessão de Estudos"}</h3>
              <p className="text-xs text-ink-secondary font-medium break-words">Continue de onde você parou para não perder o ritmo.</p>
            </div>
          </div>
          <Link 
            href={activeSession.url} 
            className="w-full sm:w-auto px-4 py-2 font-bold bg-ink-primary text-surface rounded-xs hover:bg-ink-primary/90 transition-all flex items-center justify-center gap-1.5 shadow-2xs shrink-0 text-xs"
          >
            Continuar sessão <ClinicalIcon name="arrow_forward" className="w-3.5 h-3.5" />
          </Link>
        </div>
      );
    }

    // 2. Revisões vencidas no FSRS
    if (pendentesRevisao > 0) {
      const estimatedMinutes = Math.max(5, Math.ceil(pendentesRevisao * 1.5));
      const srsCount = stats.srs_due_count || 0;
      const flashcardsCount = stats.flashcards_due_count || 0;

      return (
        <div className="shrink-0 bg-surface border border-line-strong rounded-sm p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative overflow-hidden min-w-0">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0 flex-1">
            <div className="w-10 h-10 rounded-xs bg-accent/10 border border-accent/30 text-accent flex items-center justify-center shrink-0">
              <ClinicalIcon name="psychology" className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="px-1.5 py-0.5 rounded-xs text-[10px] font-mono-lab font-bold uppercase tracking-wider bg-elevated border border-line-subtle text-accent">
                  Ação Prioritária FSRS
                </span>
                <span className="text-xs font-mono-lab text-ink-muted tabular-nums">• ~{estimatedMinutes} min</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-ink-primary break-words">
                <span className="font-mono-lab tabular-nums text-accent">{pendentesRevisao}</span> {pendentesRevisao === 1 ? "revisão vencida" : "revisões vencidas"} hoje
              </h3>
              <p className="text-xs text-ink-secondary break-words">
                Reforce os conceitos no tempo ideal do FSRS antes de resolver questões inéditas.
              </p>
            </div>
          </div>

          <div className={clsx(
            "gap-2 w-full sm:w-auto shrink-0",
            flashcardsCount > 0 && srsCount > 0 ? "grid grid-cols-2 sm:flex sm:items-center" : "flex flex-col sm:flex-row sm:items-center"
          )}>
            {flashcardsCount > 0 && (
              <Link 
                href="/revisao-ativa" 
                className="px-3.5 py-2 bg-elevated hover:bg-line-subtle text-ink-primary font-bold rounded-xs text-xs transition-colors flex items-center justify-center gap-1.5 border border-line-subtle"
              >
                <ClinicalIcon name="sparkles" className="w-3.5 h-3.5 text-accent" /> Flashcards (<span className="font-mono-lab tabular-nums">{flashcardsCount}</span>)
              </Link>
            )}
            {srsCount > 0 && (
              <Link 
                href="/estudar?status=srs_due&limit=100" 
                className="px-3.5 py-2 bg-ink-primary hover:bg-ink-primary/90 text-surface font-bold rounded-xs text-xs transition-colors flex items-center justify-center gap-1.5 shadow-2xs"
              >
                <ClinicalIcon name="refresh" className="w-3.5 h-3.5" /> Questões (<span className="font-mono-lab tabular-nums">{srsCount}</span>)
              </Link>
            )}
          </div>
        </div>
      );
    }

    // 3. Meta diária de questões novas pendente
    if (dailyRemaining > 0) {
      const practiceUrl = suggestedPlannerTopic
        ? `/estudar?subtema=${encodeURIComponent(sugestaoTema)}&status=new&limit=${Math.min(20, dailyRemaining)}`
        : bottlenecks.length > 0
        ? `/estudar?subtema=${encodeURIComponent(bottlenecks[0].subtema)}&status=new&limit=${Math.min(20, dailyRemaining)}`
        : `/estudar?status=new&limit=${Math.min(20, dailyRemaining)}`;

      return (
        <div className="shrink-0 bg-surface border border-line-subtle rounded-sm p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative overflow-hidden min-w-0">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0 flex-1">
            <div className="w-10 h-10 rounded-xs bg-elevated border border-line-subtle text-accent flex items-center justify-center shrink-0">
              <ClinicalIcon name="play_arrow" className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="px-1.5 py-0.5 rounded-xs text-[10px] font-mono-lab font-bold uppercase tracking-wider bg-elevated border border-line-subtle text-accent">
                  Meta de Hoje
                </span>
                <span className="text-xs font-mono-lab text-ink-muted tabular-nums">• {todayDone}/{dailyTarget} concluídas</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-ink-primary break-words">
                <span className="font-mono-lab tabular-nums text-accent">{dailyRemaining}</span> {dailyRemaining === 1 ? "questão" : "questões"} para bater sua meta de hoje
              </h3>
              <p className="text-xs text-ink-secondary break-words">
                Tópico sugerido: <strong className="text-ink-primary">{sugestaoTema}</strong> {sugestaoArea ? `(${sugestaoArea})` : ""}
              </p>
            </div>
          </div>

          <Link 
            href={practiceUrl}
            className="w-full sm:w-auto px-4 py-2 font-bold bg-ink-primary text-surface rounded-xs hover:bg-ink-primary/90 transition-all flex items-center justify-center gap-1.5 shadow-2xs shrink-0 text-xs"
          >
            Iniciar bateria (<span className="font-mono-lab tabular-nums">{Math.min(20, dailyRemaining)}</span> Qs) <ClinicalIcon name="arrow_forward" className="w-3.5 h-3.5" />
          </Link>
        </div>
      );
    }

    // 4. Todas as metas do dia concluídas
    if (errorNotebook && errorNotebook.currently_unresolved_count > 0) {
      const topErrorSubtema = topBottleneck ? topBottleneck.subtema : null;
      const targetUrl = topBottleneck ? topBottleneck.practice_url : errorNotebook.practice_url;

      return (
        <div className="shrink-0 bg-surface border border-critical/30 rounded-sm p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative overflow-hidden min-w-0">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0 flex-1">
            <div className="w-10 h-10 rounded-xs bg-critical-bg border border-critical/30 text-critical flex items-center justify-center shrink-0">
              <ClinicalIcon name="edit" className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="px-1.5 py-0.5 rounded-xs text-[10px] font-mono-lab font-bold uppercase tracking-wider bg-critical-bg text-critical">
                  Metas Diárias Concluídas 🎉
                </span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-ink-primary break-words">
                Aproveite para limpar seu Caderno de Erros
              </h3>
              <p className="text-xs text-ink-secondary break-words">
                {topErrorSubtema ? (
                  <>Foco sugerido: <strong className="text-ink-primary">{topErrorSubtema}</strong> (<span className="font-mono-lab tabular-nums">{topBottleneck?.unresolved_count || errorNotebook.currently_unresolved_count}</span> pendentes)</>
                ) : (
                  <>Você possui <strong className="text-ink-primary font-mono-lab tabular-nums">{errorNotebook.currently_unresolved_count} {errorNotebook.currently_unresolved_count === 1 ? "questão" : "questões"}</strong> aguardando retificação.</>
                )}
              </p>
            </div>
          </div>

          <Link 
            href={targetUrl}
            className="w-full sm:w-auto px-4 py-2 font-bold bg-critical text-surface rounded-xs hover:bg-critical/90 transition-all flex items-center justify-center gap-1.5 shadow-2xs shrink-0 text-xs"
          >
            Limpar erros <ClinicalIcon name="arrow_forward" className="w-3.5 h-3.5" />
          </Link>
        </div>
      );
    }

    return (
      <div className="shrink-0 bg-surface border border-normal/30 rounded-sm p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 min-w-0">
        <div className="flex items-center gap-3 sm:gap-4 min-w-0 flex-1">
          <div className="w-10 h-10 rounded-xs bg-normal-bg border border-normal/30 text-normal flex items-center justify-center shrink-0">
            <ClinicalIcon name="check_circle" className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm sm:text-base font-bold text-ink-primary break-words">Metas de hoje cumpridas com sucesso!</h3>
            <p className="text-xs text-ink-secondary break-words">Você está mantendo sua consistência em dia. Descanse ou avance no cronograma semanal.</p>
          </div>
        </div>
        <Link 
          href="/planner" 
          className="w-full sm:w-auto px-3.5 py-1.5 bg-elevated hover:bg-line-subtle text-ink-primary font-semibold rounded-xs text-xs transition-colors flex items-center justify-center gap-1.5 shrink-0 border border-line-subtle"
        >
          Acessar Planner
        </Link>
      </div>
    );
  };

  return (
    <motion.div 
      variants={containerVariants} 
      initial="hidden" 
      animate="show" 
      className="shrink-0 flex flex-col gap-4 sm:gap-6 pt-1 sm:pt-2 pb-10 max-w-6xl mx-auto w-full min-w-0 overflow-x-hidden px-0.5 sm:px-0"
    >
      {/* Banner de Modo Plantão (Offline) */}
      {isOffline && (
        <motion.div 
          variants={itemVariants}
          className="bg-surface border border-warning/40 rounded-sm p-3.5 sm:p-4 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-ink-primary animate-in fade-in min-w-0"
        >
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className="w-8 h-8 rounded-xs bg-warning/15 text-warning flex items-center justify-center shrink-0 border border-warning/30">
              <ClinicalIcon name="cloud_off" className="w-4 h-4" />
            </div>
            <div className="min-w-0 flex-1">
              <h4 className="font-bold text-xs sm:text-sm text-ink-primary flex items-center gap-2">
                Modo Plantão Ativo (Offline)
                <span className="text-[10px] font-mono-lab uppercase font-extrabold px-1.5 py-0.2 rounded-xs bg-warning/15 text-warning border border-warning/30 tracking-wider">Dispositivo</span>
              </h4>
              <p className="text-[11px] sm:text-xs text-ink-secondary mt-0.5 break-words">
                Você pode estudar questões e simulados salvos. As respostas serão sincronizadas ao reconectar.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
            <Link
              href="/estudar"
              className="flex-1 sm:flex-initial px-3 py-1.5 bg-ink-primary text-surface font-bold text-xs rounded-xs hover:bg-ink-primary/90 transition-all text-center shadow-2xs"
            >
              Questões Offline
            </Link>
            <Link
              href="/simulado"
              className="flex-1 sm:flex-initial px-3 py-1.5 bg-surface border border-line-subtle text-ink-primary font-bold text-xs rounded-xs hover:bg-elevated transition-all text-center"
            >
              Simulados Offline
            </Link>
            <button
              onClick={() => setIsOfflineModalOpen(true)}
              className="p-1.5 text-xs text-ink-secondary hover:text-ink-primary font-semibold rounded-xs bg-elevated hover:bg-line-subtle border border-line-subtle transition-colors cursor-pointer flex items-center justify-center shrink-0"
              title="Gerenciar pacotes offline"
              aria-label="Gerenciar pacotes offline"
            >
              <ClinicalIcon name="settings" className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}

      {/* Header: Saudação & Contagem Regressiva */}
      <motion.section variants={itemVariants} className="flex flex-col gap-1 w-full min-w-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3 w-full min-w-0">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-ink-primary truncate">
                Olá, {firstName}
              </h2>
              {isUsingCache && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-elevated text-warning text-[11px] font-mono-lab font-semibold border border-warning/30 shrink-0 shadow-2xs">
                  <ClinicalIcon name="refresh" className="w-3 h-3 animate-spin" />
                  <span className="hidden sm:inline">Sincronizando com a nuvem</span>
                  <span className="sm:hidden">Sincronizando</span>
                </div>
              )}
            </div>
            <p className="text-ink-secondary text-xs sm:text-sm mt-0.5 break-words">
              {subtitleMessage}
            </p>
          </div>

          {/* Badge Contagem Regressiva da Prova */}
          <div className="self-start sm:self-auto shrink-0">
            {stats.days_until_exam != null ? (
              <div className="flex items-center gap-2 bg-surface border border-line-subtle rounded-xs px-3 py-1.5 shadow-2xs font-mono-lab">
                <ClinicalIcon name="schedule" className="w-3.5 h-3.5 text-accent" />
                <span className="text-xs text-ink-secondary font-medium">Prova em:</span>
                <span className="text-xs font-bold text-ink-primary tabular-nums">{stats.days_until_exam} dias</span>
              </div>
            ) : stats.exam_date ? (
              <div className="flex items-center gap-2 bg-surface border border-line-subtle rounded-xs px-3 py-1.5 shadow-2xs font-mono-lab">
                <ClinicalIcon name="schedule" className="w-3.5 h-3.5 text-accent" />
                <span className="text-xs text-ink-secondary font-medium">Data-alvo:</span>
                <span className="text-xs font-bold text-ink-primary" suppressHydrationWarning>
                  {formatExamDate(stats.exam_date)}
                </span>
              </div>
            ) : (
              <Link 
                href="/planner" 
                className="flex items-center gap-1.5 bg-surface hover:bg-elevated text-accent border border-line-subtle rounded-xs px-3 py-1.5 text-xs font-mono-lab font-bold transition-colors shadow-2xs"
              >
                <ClinicalIcon name="calendar_month" className="w-3.5 h-3.5" />
                <span>Definir data da prova →</span>
              </Link>
            )}
          </div>
        </div>
      </motion.section>

      {/* ESTADO DE ERRO / RESILIÊNCIA CONTRA FALHAS DE REDE */}
      {hasOverviewError ? (
        <motion.div variants={itemVariants} className="shrink-0 bg-surface border border-warning/40 rounded-sm p-5 sm:p-6 shadow-2xs">
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4">
            <div className="w-10 h-10 rounded-xs bg-warning/15 text-warning border border-warning/30 flex items-center justify-center shrink-0">
              <ClinicalIcon name={isReconnecting ? "refresh" : "cloud_off"} className={clsx("w-5 h-5", isReconnecting && "animate-spin")} />
            </div>
            <div className="flex-1 text-center sm:text-left">
              <div className="flex items-center justify-center sm:justify-start gap-2 mb-1">
                <span className="px-1.5 py-0.5 rounded-xs text-[10px] font-mono-lab font-bold uppercase tracking-wider bg-warning/15 text-warning border border-warning/30 flex items-center gap-1.5">
                  {isReconnecting && <span className="w-1.5 h-1.5 rounded-full bg-warning animate-ping inline-block" />}
                  {isReconnecting ? "Inicializando Servidor" : "Instabilidade Temporária"}
                </span>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-ink-primary mb-1">
                {isReconnecting ? "Conectando ao servidor em nuvem..." : "Não foi possível sincronizar as métricas do painel"}
              </h3>
              <p className="text-xs text-ink-secondary max-w-xl mb-3.5">
                {isReconnecting
                  ? `O servidor em nuvem está inicializando (cold start). Tentativa ${reconnectAttempt} de sincronização automática em andamento... Suas métricas serão carregadas em instantes.`
                  : "Ocorreu uma falha temporária ao carregar seus dados do servidor. Seu histórico e progresso continuam seguros. Você pode sincronizar novamente ou continuar estudando pelo menu."}
              </p>
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2.5">
                <button
                  onClick={() => fetchDashboardData(0)}
                  disabled={isReconnecting}
                  className="px-3.5 py-1.5 bg-ink-primary hover:bg-ink-primary/90 text-surface text-xs font-bold rounded-xs transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer disabled:opacity-60"
                >
                  <ClinicalIcon name="refresh" className={clsx("w-3.5 h-3.5", isReconnecting && "animate-spin")} />
                  <span>{isReconnecting ? "Sincronizando..." : "Sincronizar agora"}</span>
                </button>
                <button
                  onClick={() => window.location.reload()}
                  className="px-3.5 py-1.5 bg-surface hover:bg-elevated text-ink-primary border border-line-subtle text-xs font-semibold rounded-xs transition-colors cursor-pointer"
                >
                  Recarregar página
                </button>
                <Link
                  href="/estudar"
                  className="px-3.5 py-1.5 bg-surface hover:bg-elevated text-ink-primary border border-line-subtle text-xs font-semibold rounded-xs transition-colors"
                >
                  Ir para Questões
                </Link>
                <Link
                  href="/simulado"
                  className="px-3.5 py-1.5 bg-surface hover:bg-elevated text-ink-primary border border-line-subtle text-xs font-semibold rounded-xs transition-colors"
                >
                  Ir para Simulados
                </Link>
              </div>
            </div>
          </div>
        </motion.div>
      ) : stats.distinct_answered === 0 ? (
        <motion.div variants={itemVariants} className="shrink-0 bg-surface border border-line-subtle rounded-sm p-5 sm:p-6 shadow-2xs">
          <div className="flex flex-col sm:flex-row items-center gap-4 mb-5">
            <div className="w-12 h-12 rounded-xs bg-ink-primary text-surface flex items-center justify-center shadow-2xs shrink-0">
              <ClinicalIcon name="local_hospital" className="w-6 h-6 text-canvas" />
            </div>
            <div className="text-center sm:text-left">
              <h3 className="text-lg sm:text-xl font-bold text-ink-primary mb-0.5">
                Boas-vindas ao MedQuest!
              </h3>
              <p className="text-xs text-ink-secondary max-w-xl">
                Seu painel inteligente é calibrado a cada questão respondida. Siga os 2 passos abaixo para configurar seu direcionamento:
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Passo 1 */}
            <div className="p-4 rounded-xs bg-elevated/40 border border-line-subtle flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 text-accent font-mono-lab font-bold text-xs uppercase tracking-wider">
                  <span className="w-4 h-4 rounded-xs bg-accent text-accent-fg flex items-center justify-center text-[10px]">1</span>
                  Planejamento
                </div>
                <h4 className="font-bold text-ink-primary text-sm mb-1">Defina sua Prova e Meta</h4>
                <p className="text-xs text-ink-secondary mb-3">
                  Informe a data do seu exame e horas semanais para receber sugestões de cronograma.
                </p>
              </div>
              <Link 
                href="/planner" 
                className="w-full py-2 px-3 bg-surface hover:bg-elevated text-ink-primary border border-line-subtle font-bold rounded-xs text-xs flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
              >
                <span>Configurar no Planner →</span>
              </Link>
            </div>

            {/* Passo 2 */}
            <div className="p-4 rounded-xs bg-elevated/40 border border-line-subtle flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1.5 mb-1.5 text-accent font-mono-lab font-bold text-xs uppercase tracking-wider">
                  <span className="w-4 h-4 rounded-xs bg-accent text-accent-fg flex items-center justify-center text-[10px]">2</span>
                  Diagnóstico Inicial
                </div>
                <h4 className="font-bold text-ink-primary text-sm mb-1">Faça 20 Questões de Teste</h4>
                <p className="text-xs text-ink-secondary mb-3">
                  Calibre seu diagnóstico inicial de pontos fracos, retenção e faixa estimada de prontidão.
                </p>
              </div>
              <Link 
                href="/estudar?limit=20" 
                className="w-full py-2 px-3 bg-ink-primary hover:bg-ink-primary/90 text-surface font-bold rounded-xs text-xs flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
              >
                <ClinicalIcon name="play_arrow" className="w-3.5 h-3.5" /> <span>Iniciar 20 Questões</span>
              </Link>
            </div>
          </div>
        </motion.div>
      ) : (
        <>
          {/* AÇÃO PRINCIPAL / HERO PRIORITÁRIO */}
          <motion.section variants={itemVariants}>
            {renderPrimaryAction()}
          </motion.section>

          {/* PLANO DE ATAQUE DO PRECEPTOR IA */}
          <motion.section variants={itemVariants}>
            <PreceptorFocusCard
              initialBottlenecks={bottlenecks}
              srsDueCount={stats.srs_due_count || 0}
              overallAccuracy={overallAccPct}
              totalAttempts={totalAttempts}
            />
          </motion.section>

          {/* PLANO DE HOJE (Card Integrado em 3 Pilares) */}
          <motion.section variants={itemVariants} className="shrink-0 bg-surface border border-line-subtle rounded-sm p-4 sm:p-5 shadow-2xs">
            <div className="flex items-center justify-between gap-2 mb-3 sm:mb-4 pb-2.5 sm:pb-3 border-b border-line-subtle">
              <div className="flex items-center gap-2 text-ink-primary">
                <ClinicalIcon name="schedule" className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-bold tracking-tight">Plano de Hoje</h3>
              </div>
              <span className="text-[11px] font-mono-lab text-ink-muted">Metas personalizadas diárias</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
              {/* Pilar 1: Revisões */}
              <div className="p-3.5 sm:p-4 rounded-xs bg-elevated/40 border border-line-subtle flex flex-col justify-between gap-3 min-w-0">
                <div className="min-w-0">
                  <div className="flex items-center justify-between text-xs font-semibold text-accent mb-1">
                    <span className="flex items-center gap-1.5">
                      <ClinicalIcon name="psychology" className="w-3.5 h-3.5" /> Revisão Ativa
                    </span>
                    {pendentesRevisao === 0 && (
                      <span className="inline-flex items-center gap-0.5 text-normal text-[11px] font-bold">
                        <ClinicalIcon name="check" className="w-3 h-3" /> Em dia
                      </span>
                    )}
                  </div>
                  <p className="text-lg sm:text-xl font-bold text-ink-primary tracking-tight font-mono-lab tabular-nums">
                    {pendentesRevisao > 0 ? `${pendentesRevisao} ${pendentesRevisao === 1 ? 'pendente' : 'pendentes'}` : "Tudo em dia!"}
                  </p>
                  <p className="text-xs text-ink-secondary mt-0.5 font-mono-lab tabular-nums">
                    {(stats.flashcards_due_count || 0) === 1 ? "1 flashcard" : `${stats.flashcards_due_count || 0} flashcards`} · {(stats.srs_due_count || 0) === 1 ? "1 questão" : `${stats.srs_due_count || 0} questões`}
                  </p>
                </div>
                {pendentesRevisao > 0 ? (
                  <Link 
                    href={(stats.flashcards_due_count || 0) > 0 ? "/revisao-ativa" : "/estudar?status=srs_due&limit=100"}
                    className="w-full py-1.5 bg-surface hover:bg-elevated text-accent border border-line-subtle font-bold rounded-xs text-xs flex items-center justify-center gap-1 transition-colors shadow-2xs font-mono-lab"
                  >
                    <span>Revisar agora →</span>
                  </Link>
                ) : (
                  <span className="text-[11px] text-normal font-semibold flex items-center gap-1">
                    <ClinicalIcon name="check_circle" className="w-3.5 h-3.5" /> Sem revisões atrasadas
                  </span>
                )}
              </div>

              {/* Pilar 2: Questões Novas */}
              <div className="p-3.5 sm:p-4 rounded-xs bg-elevated/40 border border-line-subtle flex flex-col justify-between gap-3 min-w-0">
                <div className="min-w-0">
                  <div className="flex items-center justify-between text-xs font-semibold text-accent mb-1">
                    <span className="flex items-center gap-1.5">
                      <ClinicalIcon name="description" className="w-3.5 h-3.5" /> Questões do Dia
                    </span>
                    <span className="text-xs font-bold text-ink-primary font-mono-lab tabular-nums">{todayDone}/{dailyTarget}</span>
                  </div>
                  <p className="text-lg sm:text-xl font-bold text-ink-primary tracking-tight font-mono-lab tabular-nums">
                    {dailyRemaining > 0 ? `${dailyRemaining} restantes` : "Meta batida! 🎉"}
                  </p>
                  <div 
                    role="progressbar"
                    aria-valuenow={todayDone}
                    aria-valuemin={0}
                    aria-valuemax={dailyTarget}
                    aria-label={`Progresso de questões diárias: ${todayDone} de ${dailyTarget}`}
                    className="w-full bg-line-subtle rounded-xs h-1.5 overflow-hidden mt-2"
                  >
                    <div 
                      className="bg-accent h-1.5 rounded-xs transition-all duration-500"
                      style={{ width: `${dailyProgressPct}%` }}
                    />
                  </div>
                </div>
                <Link 
                  href={`/estudar?status=new&limit=${Math.min(20, Math.max(5, dailyRemaining))}`}
                  className="w-full py-1.5 bg-surface hover:bg-elevated text-accent border border-line-subtle font-bold rounded-xs text-xs flex items-center justify-center gap-1 transition-colors shadow-2xs font-mono-lab"
                >
                  {dailyRemaining > 0 ? "Praticar questões →" : "Fazer questões extras →"}
                </Link>
              </div>

              {/* Pilar 3: Tema Sugerido */}
              {hasPlannerError ? <div role="alert" className="p-4 rounded-xs border border-warning/40 text-xs">
                Não foi possível carregar seu progresso no planner.
                <button onClick={() => window.location.reload()} className="block mt-2 font-semibold underline">Tentar novamente</button>
              </div> : <>
              <div className="p-3.5 sm:p-4 rounded-xs bg-elevated/40 border border-line-subtle flex flex-col justify-between gap-3 min-w-0">
                <div className="min-w-0">
                  <div className="flex items-center justify-between text-xs font-semibold text-accent mb-1">
                    <span className="flex items-center gap-1.5">
                      <ClinicalIcon name="calendar_month" className="w-3.5 h-3.5" /> Tema Sugerido
                    </span>
                    {plannerWeekNum && <span className="text-[11px] font-mono-lab text-ink-muted">Semana {plannerWeekNum}</span>}
                    {isPlanCompleted && <span className="text-[11px] text-normal font-bold">100% Concluído</span>}
                  </div>
                  <p className="text-sm font-bold text-ink-primary line-clamp-2 break-words" title={sugestaoTema}>
                    {isPlanCompleted ? "Plano 100% Concluído! 🎉" : sugestaoTema}
                  </p>
                  <p className="text-xs text-ink-secondary mt-0.5 line-clamp-2 break-words">
                    {isPlanCompleted
                      ? "Parabéns! Todas as metas do cronograma foram finalizadas."
                      : suggestedPlannerTopic
                      ? `${plannerMetasCount} ${plannerMetasCount === 1 ? "meta restante" : "metas restantes"} no cronograma semanal`
                      : "Baseado nas prioridades do edital"}
                  </p>
                </div>
                <Link 
                  href={
                    isPlanCompleted
                      ? "/planner"
                      : suggestedPlannerTopic
                      ? `/estudar?subtema=${encodeURIComponent(sugestaoTema)}&limit=20`
                      : bottlenecks.length > 0
                      ? `/estudar?subtema=${encodeURIComponent(bottlenecks[0].subtema)}&limit=20`
                      : "/planner"
                  }
                  className="w-full py-1.5 bg-surface hover:bg-elevated text-accent border border-line-subtle font-bold rounded-xs text-xs flex items-center justify-center gap-1 transition-colors shadow-2xs font-mono-lab"
                >
                  {isPlanCompleted ? "Ver cronograma →" : "Continuar plano →"}
                </Link>
              </div>
              </>}
            </div>
          </motion.section>

          {/* CADERNO DE ERROS & RETIFICAÇÃO ATIVA */}
          <motion.section variants={itemVariants} className="shrink-0 bg-surface border border-line-subtle rounded-sm p-4 sm:p-5 shadow-2xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 sm:mb-4 pb-2.5 sm:pb-3 border-b border-line-subtle">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-xs bg-critical-bg text-critical border border-critical/30 flex items-center justify-center shrink-0">
                  <ClinicalIcon name="edit" className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-ink-primary">Caderno de Erros & Retificação</h3>
                  <p className="text-xs text-ink-secondary">Questões com erro em aberto aguardando nova tentativa</p>
                </div>
              </div>

              {/* Botão para revisar todos os erros */}
              {errorNotebook && errorNotebook.currently_unresolved_count > 0 && (
                <Link 
                  href={errorNotebook.practice_url}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs bg-critical-bg hover:bg-critical/20 text-critical border border-critical/30 text-xs font-bold font-mono-lab transition-colors self-start sm:self-auto"
                >
                  <ClinicalIcon name="refresh" className="w-3.5 h-3.5" />
                  <span>Limpar todos (<span className="tabular-nums">{errorNotebook.currently_unresolved_count}</span>)</span>
                  <ClinicalIcon name="arrow_forward" className="w-3.5 h-3.5" />
                </Link>
              )}
            </div>

            {bottlenecks.length > 0 ? (
              <div className="flex flex-col gap-2">
                {bottlenecks.slice(0, 3).map((b) => {
                  const unresolved = b.unresolved_count ?? b.wrong_count;
                  return (
                    <div 
                      key={b.subtema}
                      className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xs bg-elevated/40 hover:bg-elevated border border-line-subtle transition-colors gap-2.5 min-w-0"
                    >
                      <div className="flex flex-col min-w-0 flex-1">
                        <div className="flex flex-wrap sm:flex-nowrap items-center gap-1.5 min-w-0">
                          <span className="font-bold text-xs text-ink-primary line-clamp-2 break-words flex-1 min-w-0" title={b.subtema}>
                            {b.subtema}
                          </span>
                          <span className="px-1.5 py-0.5 rounded-xs bg-surface border border-line-subtle text-ink-muted text-[10px] font-mono-lab font-bold shrink-0">
                            {b.area}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-secondary mt-0.5 font-mono-lab">
                          <span className="text-critical font-semibold tabular-nums">
                            {unresolved} {unresolved === 1 ? "questão com erro" : "questões com erro"}
                          </span>
                          <span className="text-ink-muted/50">•</span>
                          <span className="tabular-nums">{b.attempts} {b.attempts === 1 ? "tentativa" : "tentativas"} ({b.accuracy_pct}% acerto)</span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between sm:justify-end gap-2 w-full sm:w-auto shrink-0 pt-1.5 sm:pt-0 border-t sm:border-t-0 border-line-subtle">
                        <span className="text-xs font-mono-lab font-bold px-2 py-0.5 rounded-xs bg-critical-bg text-critical border border-critical/30 shrink-0 tabular-nums">
                          {unresolved} pendentes
                        </span>
                        <Link 
                          href={b.practice_url}
                          className="px-3 py-1 bg-critical hover:bg-critical/90 text-surface text-xs font-bold rounded-xs transition-colors flex items-center gap-1 shadow-2xs shrink-0"
                        >
                          <ClinicalIcon name="refresh" className="w-3 h-3" /> Retificar
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-6 text-center text-ink-secondary flex flex-col items-center justify-center gap-2">
                <ClinicalIcon name="check_circle" className="w-6 h-6 text-normal" />
                <p className="text-sm font-semibold text-ink-primary">Caderno de erros 100% limpo! 🎉</p>
                <p className="text-xs max-w-sm">Você não possui questões com erro em aberto. Continue praticando para calibrar sua preparação.</p>
              </div>
            )}
          </motion.section>

          {/* RITMO DA SEMANA (COMPACTO) */}
          {benchmarkStats && (
            <motion.section variants={itemVariants} className="shrink-0 bg-surface border border-line-subtle rounded-sm p-4 sm:p-5 shadow-2xs min-w-0">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2.5 min-w-0">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <ClinicalIcon name="schedule" className="w-4 h-4 text-accent shrink-0" />
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-bold text-ink-primary">Ritmo da Semana</h3>
                    <p className="text-xs text-ink-secondary font-mono-lab break-words">
                      <span className="tabular-nums">{benchmarkStats.last7_attempts}</span> de <span className="tabular-nums">{benchmarkStats.weekly_target_questions}</span> questões nos últimos 7 dias
                      {benchmarkStats.accuracy_last7 != null && (
                        <span> · <strong className="text-ink-primary tabular-nums">{Math.round(benchmarkStats.accuracy_last7 * 100)}%</strong> de acerto recente</span>
                      )}
                    </p>
                  </div>
                </div>

                <Link 
                  href="/analise" 
                  className="text-xs font-bold text-accent hover:underline flex items-center gap-1 self-start sm:self-auto shrink-0 font-mono-lab"
                >
                  Ver análise detalhada <ClinicalIcon name="arrow_forward" className="w-3 h-3" />
                </Link>
              </div>

              <div 
                role="progressbar"
                aria-valuenow={Math.round(benchmarkStats.weekly_progress_pct)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Ritmo da semana: ${Math.round(benchmarkStats.weekly_progress_pct)}% concluído`}
                className="w-full bg-line-subtle rounded-xs h-1.5 overflow-hidden"
              >
                <div 
                  className="bg-accent h-1.5 rounded-xs transition-all duration-500"
                  style={{ width: `${benchmarkStats.weekly_progress_pct}%` }}
                />
              </div>
            </motion.section>
          )}

          {/* FAIXA ESTIMADA DE PRONTIDÃO (BENCHMARK PROBABILÍSTICO CONDICIONAL) */}
          {stats.distinct_answered >= 20 && benchmarkStats && overallAccPct != null && (
            <motion.section variants={itemVariants} className="shrink-0 bg-surface border border-line-subtle rounded-sm p-4 sm:p-5 shadow-2xs relative overflow-hidden min-w-0">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 min-w-0">
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <div className="w-7 h-7 rounded-xs bg-ink-primary text-surface flex items-center justify-center shrink-0">
                    <ClinicalIcon name="analytics" className="w-3.5 h-3.5 text-canvas" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-bold text-ink-primary">Faixa Estimada de Prontidão</h3>
                    <p className="text-xs text-ink-secondary font-mono-lab break-words">
                      Estimativa preliminar baseada em <span className="tabular-nums">{totalAttempts}</span> tentativas vs. Meta de corte (<span className="tabular-nums">{targetScorePct}%</span>)
                    </p>
                  </div>
                </div>

                {/* Badge Probabilístico */}
                <div className="shrink-0 self-start sm:self-auto font-mono-lab">
                  {diffPct != null && diffPct >= 0 ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs bg-normal-bg text-normal border border-normal/30 text-xs font-bold tabular-nums">
                      <ClinicalIcon name="check_circle" className="w-3.5 h-3.5" />
                      Faixa Competitiva (+{diffPct}%)
                    </span>
                  ) : diffPct != null && diffPct >= -10 ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs bg-elevated text-accent border border-line-subtle text-xs font-bold tabular-nums">
                      <ClinicalIcon name="my_location" className="w-3.5 h-3.5" />
                      Faixa de Aproximação ({diffPct}%)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs bg-warning/15 text-warning border border-warning/30 text-xs font-bold tabular-nums">
                      <ClinicalIcon name="warning" className="w-3.5 h-3.5" />
                      Fase de Consolidação ({diffPct}%)
                    </span>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-1.5 p-3 bg-elevated/40 border border-line-subtle rounded-xs min-w-0 font-mono-lab">
                <div className="flex justify-between text-xs min-w-0">
                  <span className="text-ink-secondary font-medium truncate">Seu Acerto Geral vs. Meta</span>
                  <span className="font-bold text-ink-primary shrink-0 ml-2 tabular-nums">
                    {overallAccPct.toFixed(1)}% <span className="text-ink-muted font-normal text-[11px]">/ Meta: {targetScorePct}%</span>
                  </span>
                </div>

                <div 
                  role="progressbar"
                  aria-valuenow={Math.round(overallAccPct)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Acurácia geral: ${overallAccPct.toFixed(1)}% vs meta de corte de ${targetScorePct}%`}
                  className="relative w-full bg-line-subtle rounded-xs h-2 overflow-hidden"
                >
                  <div 
                    className="bg-accent h-2 rounded-xs transition-all duration-700"
                    style={{ width: `${Math.min(100, Math.max(0, overallAccPct))}%` }}
                  />
                  <div 
                    className="absolute top-0 bottom-0 w-0.5 bg-ink-primary z-20"
                    style={{ left: `${targetScorePct}%` }}
                    title={`Meta: ${targetScorePct}%`}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-ink-muted mt-0.5 tabular-nums">
                  <span>0%</span>
                  <span className="font-semibold text-ink-primary">Meta de Corte: {targetScorePct}%</span>
                  <span>100%</span>
                </div>
              </div>

              <p className="text-[11px] text-ink-muted mt-2 break-words">
                * A acurácia por Grande Área e o desempenho em simulados refinam a projeção na aba <Link href="/analise" className="text-accent font-semibold hover:underline">Análise</Link>.
              </p>
            </motion.section>
          )}

          {/* RESUMO DISCRETO DE CONTEXTO (BOTTOM STRIP) */}
          <motion.section variants={itemVariants} className="shrink-0 bg-surface border border-line-subtle rounded-sm p-3 sm:px-4 sm:py-2.5 shadow-2xs w-full min-w-0">
            <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center justify-between gap-2 sm:gap-3 text-xs font-mono-lab">
              <Link href="/cobertura" className="flex items-center gap-1.5 hover:text-accent transition-colors text-ink-secondary p-1 min-w-0 overflow-hidden">
                <ClinicalIcon name="check_circle" className="w-3.5 h-3.5 text-normal shrink-0" />
                <span className="truncate">
                  {domainSummary ? "Domínio:" : "Cobertura:"} <strong className="text-ink-primary tabular-nums">
                    {domainSummary ? `${domainSummary.overall_domain_pct}%` : (stats.coverage_pct != null ? `${(stats.coverage_pct * 100).toFixed(0)}%` : "--")}
                  </strong>
                </span>
              </Link>

              {errorNotebook && (
                <Link href={errorNotebook.practice_url} className="flex items-center gap-1.5 hover:text-critical transition-colors text-ink-secondary p-1 min-w-0 overflow-hidden">
                  <ClinicalIcon name="edit" className="w-3.5 h-3.5 text-critical shrink-0" />
                  <span className="truncate">
                    Erros: <strong className="text-critical tabular-nums">{errorNotebook.currently_unresolved_count}</strong>
                  </span>
                </Link>
              )}

              <div className="flex items-center gap-1.5 text-ink-secondary p-1 min-w-0 overflow-hidden">
                <ClinicalIcon name="schedule" className="w-3.5 h-3.5 text-warning shrink-0" />
                <span className="truncate">
                  Sequência: <strong className="text-ink-primary tabular-nums">{stats.streak_days}d</strong>
                </span>
              </div>

              <button
                onClick={() => setIsOfflineModalOpen(true)}
                className="flex items-center justify-center gap-1.5 text-xs text-ink-secondary hover:text-ink-primary font-semibold px-2.5 py-1 rounded-xs bg-elevated hover:bg-line-subtle transition-colors cursor-pointer border border-line-subtle col-span-2 sm:col-span-1 shrink-0"
                title="Abrir gerenciador do Modo Plantão (Offline)"
                aria-label="Abrir gerenciador do Modo Plantão offline"
              >
                <ClinicalIcon name="cloud_download" className="w-3.5 h-3.5 text-accent shrink-0" />
                <span>Modo Plantão</span>
              </button>
            </div>
          </motion.section>
        </>
      )}

      {/* Modal do Modo Plantão (Offline) */}
      <OfflineModal 
        isOpen={isOfflineModalOpen} 
        onClose={() => setIsOfflineModalOpen(false)} 
      />
    </motion.div>
  );
}


