import { serverApi } from "@/lib/server-api";
import { 
  OverviewStats, PlannerWeek, PlannerTopic, PlannerTopicProgressMap, PlannerProgressMap,
  BenchmarkStat, BottleneckTopic, DomainSummaryResponse, ErrorNotebookSummary 
} from "@/types/api";
import { currentUser } from '@clerk/nextjs/server';
import { DashboardClient } from "./DashboardClient";

export const dynamic = "force-dynamic";

const DEFAULT_STATS: OverviewStats = {
  total_questions: 0,
  distinct_answered: 0,
  total_attempts: 0,
  accuracy_all_attempts: null,
  accuracy_latest_attempt: null,
  coverage_pct: null,
  srs_due_count: 0,
  accuracy_last7: null,
  accuracy_prev7: null,
  streak_days: 0,
  daily_target: 20,
  today_answered: 0,
  flashcards_due_count: 0,
};

export default async function Dashboard() {
  const userPromise = currentUser().catch(() => null);

  let stats: OverviewStats = DEFAULT_STATS;
  let hasOverviewError = false;
  let hasPlannerError = false;
  let currentPlannerWeek: PlannerWeek | null = null;
  let suggestedPlannerTopic: PlannerTopic | null = null;
  let remainingPlannerMetas: number = 0;
  let isPlanCompleted: boolean = false;
  let benchmarkStats: BenchmarkStat | null = null;
  let bottlenecks: BottleneckTopic[] = [];
  let domainSummary: DomainSummaryResponse | null = null;
  let errorNotebook: ErrorNotebookSummary | null = null;

  let usedAggregatedPath = false;

  // Caminho otimizado de 1 round-trip quando getDashboardSummary está disponível
  let backendTimedOutOrDown = false;
  if (typeof serverApi.stats.getDashboardSummary === "function") {
    const summaryResult = await serverApi.stats.getDashboardSummary()
      .then((data) => ({ data, hasError: false, isDown: false }))
      .catch((err) => {
        console.error("Failed to fetch dashboard summary:", err);
        const errMsg = err instanceof Error ? err.message : String(err);
        const isDown = /timeout|timed out|econnrefused|502|503|504/i.test(errMsg);
        return { data: null, hasError: true, isDown };
      });

    backendTimedOutOrDown = summaryResult.isDown;

    if (!summaryResult.hasError && summaryResult.data) {
      usedAggregatedPath = true;
      const summaryData = summaryResult.data;
      stats = summaryData.stats || DEFAULT_STATS;
      hasOverviewError = !summaryData.stats;
      benchmarkStats = summaryData.benchmark;
      bottlenecks = summaryData.bottlenecks || [];
      domainSummary = summaryData.domain_summary;
      errorNotebook = summaryData.error_notebook;

      const planner = summaryData.planner;
      const config = planner?.config;
      const progressMap = planner?.progress || {};
      const topicProgressMap = planner?.topic_progress || {};

      if (config && config.exam_date && config.start_date) {
        try {
          const planResponse = await serverApi.planner.generatePlan({
            start_date: config.start_date,
            exam_date: config.exam_date,
            hours_per_week: Math.min(168, (config.days_per_week || 5) * (config.hours_per_day || 4)),
            intensive: false
          });

          if (planResponse.plan && planResponse.plan.length > 0) {
            const plan = planResponse.plan;
            for (const week of plan) {
              if (progressMap[week.week.toString()]?.studied) {
                continue;
              }
              const pendingTopics = (week.topics || []).filter(
                (t) => !topicProgressMap[`${week.week}:${t.subtema}`] && !topicProgressMap[t.subtema]
              );
              if (pendingTopics.length > 0) {
                currentPlannerWeek = week;
                suggestedPlannerTopic = pendingTopics[0];
                remainingPlannerMetas = pendingTopics.length;
                break;
              }
            }

            if (!suggestedPlannerTopic && plan.length > 0) {
              isPlanCompleted = true;
              currentPlannerWeek = plan[plan.length - 1];
            }
          }
        } catch (planErr) {
          hasPlannerError = true;
          console.error("Failed to generate plan for dashboard", planErr);
        }
      }
    } else if (backendTimedOutOrDown) {
      // Falha rápida: se o servidor estiver em cold start ou timeout, não disparar
      // 8 requisições adicionais em cascata que apenas prolongam a espera do SSR.
      hasOverviewError = true;
      hasPlannerError = true;
    }
  }

  // Caminho granular resiliente (isolamento de falhas e compatibilidade com suítes de testes)
  if (!usedAggregatedPath && !backendTimedOutOrDown) {
    const statsPromise = serverApi.stats.getOverview()
      .then((s) => ({ stats: s, hasError: false }))
      .catch((err) => {
        console.error("Failed to fetch dashboard overview stats:", err);
        return { stats: DEFAULT_STATS, hasError: true };
      });

    try {
      const [bench, bnecks, domain, errors, configResult, topicsResult, progressResult] = await Promise.all([
        serverApi.stats.getBenchmark().catch(() => null),
        serverApi.stats.getBottlenecks(3).catch(() => []),
        serverApi.stats.getDomainSummary().catch(() => null),
        serverApi.stats.getErrorNotebookSummary().catch(() => null),
        serverApi.planner.getConfig().then(data => ({ data, failed: false })).catch(() => ({ data: null, failed: true })),
        serverApi.planner.getTopicProgress().then(data => ({ data, failed: false })).catch(() => ({ data: {} as PlannerTopicProgressMap, failed: true })),
        serverApi.planner.getProgress().then(data => ({ data, failed: false })).catch(() => ({ data: {} as PlannerProgressMap, failed: true })),
      ]);
      hasPlannerError = configResult.failed || topicsResult.failed || progressResult.failed;
      const config = configResult.data;
      const topicProgressMap = topicsResult.data;
      const progressMap = progressResult.data;
      benchmarkStats = bench;
      bottlenecks = bnecks;
      domainSummary = domain;
      errorNotebook = errors;

      if (!hasPlannerError && config && config.exam_date && config.start_date) {
        const planResponse = await serverApi.planner.generatePlan({
          start_date: config.start_date,
          exam_date: config.exam_date,
          hours_per_week: Math.min(168, (config.days_per_week || 5) * (config.hours_per_day || 4)),
          intensive: false
        });

        if (planResponse.plan && planResponse.plan.length > 0) {
          const plan = planResponse.plan;

          for (const week of plan) {
            if (progressMap[week.week.toString()]?.studied) {
              continue;
            }
            const pendingTopics = (week.topics || []).filter(
              (t) => !topicProgressMap[`${week.week}:${t.subtema}`] && !topicProgressMap[t.subtema]
            );
            if (pendingTopics.length > 0) {
              currentPlannerWeek = week;
              suggestedPlannerTopic = pendingTopics[0];
              remainingPlannerMetas = pendingTopics.length;
              break;
            }
          }

          if (!suggestedPlannerTopic && plan.length > 0) {
            isPlanCompleted = true;
            currentPlannerWeek = plan[plan.length - 1];
          }
        }
      }
    } catch (e) {
      hasPlannerError = true;
      console.error("Failed to fetch dashboard metrics", e);
    }

    const statsResult = await statsPromise;
    stats = statsResult.stats;
    hasOverviewError = statsResult.hasError;
  }

  const user = await userPromise;
  const firstName = user?.firstName || "Doutor(a)";

  return (
    <DashboardClient 
      stats={stats} 
      currentPlannerWeek={currentPlannerWeek} 
      suggestedPlannerTopic={suggestedPlannerTopic}
      remainingPlannerMetas={remainingPlannerMetas}
      isPlanCompleted={isPlanCompleted}
      firstName={firstName} 
      benchmarkStats={benchmarkStats}
      bottlenecks={bottlenecks}
      domainSummary={domainSummary}
      errorNotebook={errorNotebook}
      hasOverviewError={hasOverviewError}
      hasPlannerError={hasPlannerError}
    />
  );
}
