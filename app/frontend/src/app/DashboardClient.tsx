"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useUser } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, RefreshCw, Target } from "lucide-react";
import { api } from "@/lib/api";
import { isLocalIdentityReady } from "@/lib/db";
import { readLearningSession, syncSessionFromCloud } from "@/lib/sessionState";
import { dashboardPriorities, topicAction, topicKey, topicReason } from "@/lib/dashboardLearning";
import type { LearningAnalysis, LearningMeasure, OverviewStats, PlannerTopic, PlannerWeek } from "@/types/api";

const OfflineModal = dynamic(() => import("@/components/OfflineModal").then(m => m.OfflineModal), { ssr: false });
const panel = "rounded-2xl border border-border bg-card p-4 sm:p-6 min-w-0";
const action = "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary";
const secondary = "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-border px-3 py-2 text-sm font-medium hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary";

interface DashboardClientProps {
  stats: OverviewStats;
  currentPlannerWeek: PlannerWeek | null;
  suggestedPlannerTopic?: PlannerTopic | null;
  remainingPlannerMetas?: number;
  isPlanCompleted?: boolean;
  firstName: string;
  hasOverviewError?: boolean;
  hasPlannerError?: boolean;
}

function result(measure: LearningMeasure) {
  return measure.total && measure.accuracy !== null
    ? `${Math.round(measure.accuracy * 100)}% · ${measure.correct}/${measure.total}`
    : "Sem respostas no período";
}

function Comparison({ previous }: { previous: LearningMeasure }) {
  return <p className="text-xs text-muted-foreground mt-2">Período anterior: {result(previous)}. A composição das questões pode mudar.</p>;
}

export function DashboardClient({ stats, currentPlannerWeek, suggestedPlannerTopic, remainingPlannerMetas = 0, isPlanCompleted, firstName, hasOverviewError = false, hasPlannerError = false }: DashboardClientProps) {
  const { isLoaded: authLoaded } = useUser();
  const [activeSession, setActiveSession] = useState<{ kind: string; url: string } | null>(null);
  const [offlineOpen, setOfflineOpen] = useState(false);
  const [offline, setOffline] = useState(false);
  const [data, setData] = useState<LearningAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!isLocalIdentityReady(authLoaded)) return;
    const controller = new AbortController();
    api.stats.getLearningAnalysis({ days: 30, institution: "", area: "", subtema: "", tz_offset: -new Date().getTimezoneOffset() }, controller.signal)
      .then(value => { if (!controller.signal.aborted) { setData(value); setFailed(false); } })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [authLoaded, retry]);

  useEffect(() => {
    if (!isLocalIdentityReady(authLoaded)) return;
    let active = true;
    const valid = (value: unknown): value is { state?: string } => typeof value === "object" && value !== null;
    const check = () => {
      if (!active) return;
      const simulado = readLearningSession("simulado", valid);
      const quiz = readLearningSession("quiz", valid);
      setActiveSession(simulado?.state === "PLAYING" || simulado?.state === "SUBMITTING"
        ? { kind: "simulado", url: "/simulado" }
        : quiz?.state === "PLAYING" ? { kind: "sessão de questões", url: "/estudar?resume=true" } : null);
    };
    check();
    void Promise.allSettled([syncSessionFromCloud("simulado", valid), syncSessionFromCloud("quiz", valid)]).then(check);
    return () => { active = false; };
  }, [authLoaded]);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    const open = () => setOfflineOpen(true);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    window.addEventListener("open-offline-modal", open);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
      window.removeEventListener("open-offline-modal", open);
    };
  }, []);

  const refresh = () => { setLoading(true); setFailed(false); setRetry(n => n + 1); };
  const priorities = data ? dashboardPriorities(data) : [];
  const nextTopic = priorities.find(t => topicAction(t));
  const nextAction = nextTopic ? topicAction(nextTopic) : null;
  const today = stats.today_answered ?? 0;
  const target = Math.max(1, stats.daily_target || 20);
  const remaining = Math.max(0, target - today);
  const summary = data?.summary;

  return <div className="mx-auto w-full max-w-6xl space-y-5 pb-10">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-sm font-semibold text-primary">Seu estudo de hoje</p><h1 className="text-2xl sm:text-3xl font-bold mt-1">Olá, {firstName}</h1><p className="text-sm text-muted-foreground mt-2">Escolha uma prioridade e acompanhe o que você consegue lembrar depois.</p></div>
      {!hasOverviewError && stats.days_until_exam != null && stats.days_until_exam >= 0 && <Link href="/planner" className={secondary}>Prova em {stats.days_until_exam} dias</Link>}
    </header>

    {offline && <aside className={`${panel} border-amber-500/40`}><p className="font-semibold">Modo Plantão · offline</p><p className="text-sm text-muted-foreground mt-1">Use questões e simulados salvos. As respostas serão sincronizadas ao reconectar.</p><div className="flex flex-wrap gap-2 mt-3"><Link href="/estudar" className={secondary}>Questões salvas</Link><Link href="/simulado" className={secondary}>Simulados salvos</Link><button onClick={() => setOfflineOpen(true)} className={secondary}>Gerenciar pacotes</button></div></aside>}

    {activeSession && <aside className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-2"><p className="text-sm">Você tem uma {activeSession.kind} em andamento.</p><Link href={activeSession.url} className={secondary}>Retomar sessão <ArrowRight size={16} /></Link></aside>}

    {loading ? <section className={panel} role="status">Carregando prioridades e evidências de aprendizagem…</section>
      : failed ? <section className={`${panel} border-amber-500/40`} role="alert"><h2 className="font-bold">Evidências temporariamente indisponíveis</h2><p className="text-sm text-muted-foreground mt-2">Não foi possível verificar seus erros e resultados. Isso não significa que suas pendências estejam zeradas.</p><div className="flex flex-wrap gap-3 mt-4"><button onClick={refresh} className={action}><RefreshCw size={16} /> Tentar novamente</button><Link href="/estudar" className={secondary}>Prática geral</Link></div></section>
      : data && summary && <>
        <section className={`${panel} border-primary/30 bg-primary/5`} aria-labelledby="next-action">
          <div className="flex items-center gap-2 text-primary text-sm font-semibold"><Target size={18} /> Próximo passo</div>
          <h2 id="next-action" className="text-xl font-bold mt-3">{nextTopic ? nextTopic.topic : summary.available === 0 ? "Nenhuma questão disponível" : "Continue avaliando sua aprendizagem"}</h2>
          <p className="text-sm text-muted-foreground mt-2">{nextTopic ? `${nextTopic.area} · ${topicReason(nextTopic)}.` : summary.available === 0 ? "Consulte o banco de questões ou ajuste seu plano." : "Nenhuma prioridade acionável pelos critérios atuais. Isso não comprova domínio."}</p>
          <div className="flex flex-wrap items-center gap-3 mt-4">{nextAction ? <Link href={nextAction.href} className={action}>{nextAction.label} <ArrowRight size={16} /></Link> : <Link href="/analise" className={action}>Examinar temas</Link>}<span className="text-xs text-muted-foreground">{nextAction ? "Até 10 questões por sessão. Você pode escolher outra prioridade abaixo." : "Confira os resultados e o planejamento."}</span></div>
          {summary.answered === 0 && <p className="text-xs text-muted-foreground mt-3">Primeiras respostas ajudam a conhecer seu ponto de partida. Uma sessão inicial não comprova domínio ou prontidão para a prova.</p>}
        </section>

        <section className={panel} aria-labelledby="priorities-title">
          <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="priorities-title" className="text-lg font-bold">Suas prioridades</h2><Link href="/analise" className={secondary}>Ver todos os temas <ArrowRight size={16} /></Link></div>
          <p className="text-sm text-muted-foreground mt-2">Pendências atuais, com espaço para acompanhar correções e avaliar temas pouco explorados.</p>
          <div className="grid gap-3 md:grid-cols-3 mt-4">{priorities.map(topic => <article key={topicKey(topic)} className="rounded-xl border border-border p-4 flex flex-col min-w-0">
            <p className="text-xs text-muted-foreground">{topic.area}</p><h3 className="font-bold mt-1 break-words">{topic.topic}</h3><p className="text-sm mt-3">{topicReason(topic)}.</p>
            <p className="text-xs text-muted-foreground mt-2">Primeiras respostas nos últimos 30 dias: {result(topic.new_questions)}.</p>
            {topic.pending_checks > 0 && <p className="text-xs text-muted-foreground mt-2">{topic.pending_checks} correções ainda sem acerto verificado após intervalo. Acompanhe as revisões agendadas; questões inéditas avaliam outros exemplos do tema.</p>}
            <div className="flex flex-col gap-2 mt-auto pt-4">{topic.actions.errors && <Link href={topic.actions.errors} className={secondary}>Revisar erros</Link>}{topic.actions.reviews && <Link href={topic.actions.reviews} className={secondary}>Revisar vencidas</Link>}{topic.actions.new && <Link href={topic.actions.new} className={secondary}>Praticar inéditas</Link>}{!topic.actions.errors && !topic.actions.reviews && !topic.actions.new && <p className="text-xs text-muted-foreground">Sem sessão disponível agora. Aguarde a revisão agendada ou acompanhe o tema na Análise.</p>}</div>
          </article>)}</div>
          {priorities.length === 0 && <p className="text-sm text-muted-foreground mt-4">Nenhum tema sinalizado pelos critérios atuais.</p>}
          <p className="text-sm mt-4 border-t border-border pt-4">{summary.unresolved} questões com última resposta incorreta · {summary.recurring} com erros repetidos. {summary.unresolved === 0 ? "Sem erros pendentes nas questões disponíveis; correções ainda podem precisar de verificação." : "Corrigir uma resposta é o primeiro passo; conferir depois traz nova evidência."}</p>
        </section>

        <section aria-labelledby="learning-title">
          <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="learning-title" className="text-lg font-bold">O que os resultados mostram</h2><button className={secondary} onClick={refresh} aria-label="Atualizar evidências"><RefreshCw size={16} /> Atualizar</button></div>
          <p className="text-xs text-muted-foreground mt-2 mb-3">Todas as bancas e áreas · {data.scope.start} a {data.scope.end} · horário local. Resultados por período; acompanhamento de correções considera o histórico.</p>
          <div className="grid gap-3 md:grid-cols-3">
            <article className={panel}><BookOpen size={20} className="text-primary" /><h3 className="font-semibold mt-3">Questões novas</h3><p className="text-xl font-bold mt-2">{result(summary.new_questions)}</p><p className="text-xs text-muted-foreground mt-2">Acertos / questões respondidas pela primeira vez. Repetições não aumentam esta amostra.</p><Comparison previous={summary.previous_new_questions} /></article>
            <article className={panel}><h3 className="font-semibold">Revisões após intervalo</h3><p className="text-xl font-bold mt-2">{result(summary.delayed_reviews)}</p><p className="text-xs text-muted-foreground mt-2">Última revisão elegível por questão no período, após ao menos {data.method.delayed_review_hours}h desde a resposta anterior. Não inclui flashcards.</p><Comparison previous={summary.previous_delayed_reviews} /></article>
            <article className={panel}><h3 className="font-semibold">Correções em acompanhamento</h3><p className="text-xl font-bold mt-2">{summary.pending_checks} aguardam verificação</p><p className="text-sm mt-3">{summary.retained_corrections} com acerto após intervalo desde o último erro.</p><p className="text-xs text-muted-foreground mt-2">Um acerto imediato não encerra este acompanhamento. Um novo erro reabre a pendência; um acerto posterior não comprova domínio do tema.</p></article>
          </div>
          <p className="text-xs text-muted-foreground mt-3">Comparação anterior: {data.scope.previous_start} a {data.scope.previous_end}. Amostras pequenas e mudanças nos temas limitam a comparação.</p>
        </section>
      </>}

    <section className={panel} aria-labelledby="workload-title"><h2 id="workload-title" className="text-lg font-bold">Organize o trabalho de hoje</h2><p className="text-sm text-muted-foreground mt-1">Metas de atividade ajudam na rotina; completá-las não mede domínio.</p>
      {hasOverviewError ? <div role="alert" className="mt-4"><p className="text-sm">Não foi possível carregar as contagens de hoje.</p><button className={`${secondary} mt-3`} onClick={() => window.location.reload()}>Recarregar contagens</button></div> : <div className="grid gap-4 sm:grid-cols-3 mt-4">
        <div><h3 className="text-sm font-semibold">Questões praticadas</h3><p className="text-2xl font-bold mt-1">{today}/{target}</p><p className="text-xs text-muted-foreground mt-1">Questões distintas hoje, incluindo revisões.</p><progress className="w-full h-2 mt-3 accent-primary" value={Math.min(today, target)} max={target} aria-label="Questões distintas praticadas hoje" /><Link href={`/estudar?status=new&limit=${Math.min(10, Math.max(1, remaining))}`} className={`${secondary} mt-3`}>{remaining ? "Praticar inéditas" : "Prática extra opcional"}</Link></div>
        <div><h3 className="text-sm font-semibold">Revisões de questões</h3><p className="text-2xl font-bold mt-1">{stats.srs_due_count ?? 0} vencidas</p><p className="text-xs text-muted-foreground mt-1">Faça uma sessão de até 10. O restante continua pendente.</p>{(stats.srs_due_count ?? 0) > 0 && <Link href="/estudar?status=srs_due&limit=10" className={`${secondary} mt-3`}>Revisar questões</Link>}</div>
        <div><h3 className="text-sm font-semibold">Revisões de flashcards</h3><p className="text-2xl font-bold mt-1">{stats.flashcards_due_count ?? 0} vencidos</p><p className="text-xs text-muted-foreground mt-1">Fila separada das questões; escolha seu ritmo na revisão ativa.</p>{(stats.flashcards_due_count ?? 0) > 0 && <Link href="/revisao-ativa" className={`${secondary} mt-3`}>Abrir revisão ativa</Link>}</div>
      </div>}
      <div className="mt-5 pt-4 border-t border-border text-sm">{hasPlannerError ? <p role="alert">Seu planejamento está temporariamente indisponível. <Link className="text-primary underline" href="/planner">Abrir Planner</Link></p> : isPlanCompleted ? <p>Itens do cronograma concluídos. As evidências de aprendizagem continuam acima. <Link href="/planner" className="text-primary underline">Ver plano</Link></p> : suggestedPlannerTopic ? <p>Próximo item não concluído no Planner{currentPlannerWeek ? ` · semana ${currentPlannerWeek.week}` : ""}: <strong>{suggestedPlannerTopic.subtema}</strong> · {remainingPlannerMetas} metas restantes nessa semana. <Link href={`/estudar?${new URLSearchParams({ subtema: suggestedPlannerTopic.subtema, area: suggestedPlannerTopic.area || "", status: "new", limit: "10" })}`} className="text-primary underline">Praticar esse tema</Link></p> : <Link href="/planner" className="text-primary underline">Definir seu plano e a data da prova</Link>}</div>
    </section>

    <nav aria-label="Ferramentas de estudo" className="flex flex-wrap gap-2"><Link href="/analise" className={secondary}>Análise detalhada</Link><Link href="/cobertura" className={secondary}>Explorar cobertura</Link><Link href="/planner" className={secondary}>Planner</Link><button onClick={() => setOfflineOpen(true)} className={secondary}>Modo Plantão</button></nav>
    <OfflineModal isOpen={offlineOpen} onClose={() => setOfflineOpen(false)} />
  </div>;
}
