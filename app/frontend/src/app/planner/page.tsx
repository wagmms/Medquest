import { isDynamicServerUsageError, serverApi } from "@/lib/server-api";
import { PlannerConfig, PlannerProgressMap, PlannerTopicProgressMap, PlannerPlanResponse } from "@/types/api";
import { PlannerWizard } from "./PlannerWizard";
import { PlannerClient } from "./PlannerClient";

export const dynamic = "force-dynamic";

export default async function PlannerPage({ searchParams }: { searchParams: Promise<{ intensive?: string }> }) {
  let hasError = false;
  let config: PlannerConfig | null = null;
  let isIntensive = false;
  let planResponse: PlannerPlanResponse | null = null;
  let progressMap: PlannerProgressMap = {};
  let topicProgressMap: PlannerTopicProgressMap = {};

  try {
    config = await serverApi.planner.getConfig();
    const sp = await searchParams;
    isIntensive = sp.intensive === 'true';

    if (config && config.exam_date && config.start_date) {
      const [generatedPlan, pMap, tMap] = await Promise.all([
        serverApi.planner.generatePlan({
          start_date: config.start_date,
          exam_date: config.exam_date,
          hours_per_week: Math.min(168, (config.days_per_week || 5) * (config.hours_per_day || 4)),
          intensive: isIntensive
        }),
        serverApi.planner.getProgress(),
        serverApi.planner.getTopicProgress(),
      ]);
      planResponse = generatedPlan;
      progressMap = pMap;
      topicProgressMap = tMap;
    }
  } catch (e) {
    if (isDynamicServerUsageError(e)) {
      throw e;
    }
    console.error("Failed to load planner:", e);
    hasError = true;
  }

  if (hasError) {
    return (
      <div className="animate-in fade-in duration-500 flex flex-col items-center justify-center min-h-[60vh] p-6 text-center">
        <div className="w-12 h-12 bg-destructive/15 text-destructive rounded-2xl flex items-center justify-center mb-4 border border-destructive/20">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-foreground mb-2">Erro ao carregar cronograma</h2>
        <p className="text-sm text-muted-foreground max-w-md mb-6">
          Não foi possível conectar ao servidor para obter seu plano de estudos.
        </p>
        <a
          href="/planner"
          className="px-4 py-2 bg-primary text-primary-foreground text-sm font-semibold rounded-xl hover:bg-primary/90 transition-colors shadow-sm"
        >
          Tentar novamente
        </a>
      </div>
    );
  }

  // Se não houver configuração salva ou se faltar data da prova, força o Onboarding
  if (!config || !config.exam_date || !config.start_date) {
    return (
      <div className="animate-in fade-in duration-500 flex flex-col items-center justify-center min-h-[70vh]">
        <PlannerWizard />
      </div>
    );
  }

  // Se a geração falhar ou retornar array vazio
  if (!planResponse?.plan || planResponse.plan.length === 0) {
    return (
      <div className="animate-in fade-in duration-500 flex flex-col items-center justify-center min-h-[70vh]">
        <div className="bg-destructive/10 text-destructive text-center p-6 rounded-xl border border-destructive/20 max-w-md">
          A data da prova precisa ser no futuro (ou não há temas no modo intensivo).
        </div>
        <div className="mt-8">
          <PlannerWizard initialConfig={config} />
        </div>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-500">
      <PlannerClient 
        plan={planResponse.plan}
        initialProgress={progressMap}
        initialTopicProgress={topicProgressMap}
        warning={planResponse.warning}
        isIntensive={isIntensive}
        config={config}
      />
    </div>
  );
}
