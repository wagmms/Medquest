import { serverApi } from "@/lib/server-api";
import dynamic from "next/dynamic";


const AnalysisClient = dynamic(
  () => import("./AnalysisClient").then(mod => mod.AnalysisClient),
  {
    loading: () => (
      <div className="flex flex-col gap-6 animate-pulse p-4">
        <div className="h-64 bg-muted/40 rounded-2xl w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-48 bg-muted/40 rounded-2xl" />
          <div className="h-48 bg-muted/40 rounded-2xl" />
        </div>
      </div>
    ),
  }
);

export default async function AnalisePage() {
  // Fazemos fetch paralelo de todos os dados do dashboard analítico
  const ALLOWED_INSTITUTIONS = [
    { key: "USP-SP", label: "USP - São Paulo" },
    { key: "USP-RP", label: "USP - Ribeirão Preto" },
    { key: "UNICAMP", label: "Unicamp" },
    { key: "UNIFESP", label: "Unifesp / EPM" },
    { key: "SUS-SP", label: "SUS-SP" },
  ];

  const overviewPromise = serverApi.stats.getOverview().catch(() => null);
  const readinessPromise = overviewPromise.then(overview => {
    const raw = overview?.primary_institution || overview?.target_institution;
    const inst = (raw && raw !== "Todas as Bancas" && raw !== "TODAS")
      ? raw.split(",")[0].trim()
      : undefined;
    const targetInst = (inst && ALLOWED_INSTITUTIONS.some(i => i.key === inst)) ? inst : "USP-SP";
    return serverApi.stats.getExamReadiness(targetInst);
  });
  const radarPromise = overviewPromise.then(overview => {
    const raw = overview?.primary_institution || overview?.target_institution;
    const inst = (raw && raw !== "Todas as Bancas" && raw !== "TODAS")
      ? raw.split(",")[0].trim()
      : "USP-SP";
    const targetInst = (inst && ALLOWED_INSTITUTIONS.some(i => i.key === inst)) ? inst : "USP-SP";
    return serverApi.stats.getInstitutionRadar(targetInst);
  }).catch(() => null);
  const results = await Promise.allSettled([
    serverApi.stats.getTimeline(14),
    serverApi.stats.getWeakTopics(),
    serverApi.stats.getBreakdown("institution"),
    serverApi.stats.getDistractors(),
    serverApi.stats.getPredictiveScore(),
    serverApi.stats.getAtRiskTopics(),
    serverApi.stats.getLearningProfile(),
    readinessPromise,
    serverApi.stats.getTimeline(180),
  ]);

  const sectionNames = ["Evolução", "Temas prioritários", "Instituições", "Distratores", "Projeção", "Risco de esquecimento", "Perfil de estudo", "Prontidão", "Histórico de 180 dias"];
  const failedSections = sectionNames.filter((_, index) => results[index].status === "rejected");
  const timeline = results[0].status === 'fulfilled' ? results[0].value : [];
  const weakTopics = results[1].status === 'fulfilled' ? results[1].value : [];
  const breakdown = results[2].status === 'fulfilled' ? results[2].value : [];
  const distractors = results[3].status === 'fulfilled' ? results[3].value : [];
  const predictiveScore = results[4].status === 'fulfilled' ? results[4].value : { projected_score: 0, target_score: null, areas: [] };
  const atRiskTopics = results[5].status === 'fulfilled' ? results[5].value : [];
  const learningProfile = results[6].status === 'fulfilled' ? results[6].value : {
    generated_at: '',
    goal: { questions_today: 30, configured_daily_questions: 30, reviews_due: 0, reviews_to_do_today: 0, backlog_pending: 0, hours_budget: 4, max_capacity: 80, target_score: null, exam_date: null },
    topics: [],
    method: { deterministic: true, signals: [] },
  };
  const fallbackReadiness = results[7].status === 'fulfilled' ? results[7].value : {
    institution: "USP-SP", coverage: 0, answered: 0, available: 0, areas: [],
    disclaimer: 'Ainda não há dados suficientes para este relatório.',
    limitations: [
      'A prontidão estimada reflete exclusivamente as questões resolvidas no MedQuest sob o perfil de edital configurado.',
      'Não constitui probabilidade de aprovação, garantia de classificação ou nota de corte oficial.',
    ],
  };
  const timeline180 = results[8].status === 'fulfilled' ? results[8].value : [];
  const examReadiness = fallbackReadiness;
  const institutionRadar = await radarPromise;

  const institutionOptions = ALLOWED_INSTITUTIONS;

  return (
    <div className="flex flex-col gap-8 animate-in fade-in duration-500">

      {/* Header */}
      <section className="bg-card border border-border shadow-sm rounded-2xl p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 relative overflow-hidden isolation-auto">
        <div className="absolute top-0 right-0 w-64 h-64 bg-secondary/10 rounded-full blur-3xl -z-10" />
        <div className="absolute bottom-0 left-0 w-40 h-40 bg-primary/10 rounded-full blur-3xl -z-10" />

        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary/10 text-secondary text-sm font-semibold mb-4 border border-secondary/20">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Análise adaptativa
          </div>

          <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-3">
            Análise de Desempenho
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl leading-relaxed">
            Evidências transparentes para decidir o que estudar: cobertura, desempenho, risco de esquecimento e evolução ao longo do tempo.
          </p>
        </div>
      </section>

      {failedSections.length > 0 && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">
        Falha no carregamento inicial: {failedSections.join(", ")}. Use os controles de nova tentativa ou recarregue o relatório para recuperar as seções indisponíveis.
        <a href="/analise" className="ml-2 font-semibold underline">Recarregar relatório</a>
      </div>}
      {/* Main Content Dashboard */}
      <AnalysisClient
        initialErrors={failedSections}
        timeline={timeline}
        weakTopics={weakTopics}
        breakdown={breakdown}
        distractors={distractors}
        predictiveScore={predictiveScore}
        atRiskTopics={atRiskTopics}
        learningProfile={learningProfile}
        examReadiness={examReadiness}
        institutionOptions={institutionOptions}
        timeline180={timeline180}
        institutionRadar={institutionRadar}
      />

    </div>
  );
}
