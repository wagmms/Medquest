"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, RefreshCw, Target, BookOpen, Clock, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ExamReadiness, LearningAnalysis, LearningAnalysisFilters, LearningMeasure, LearningTopic } from "@/types/api";
import { InstitutionRadarSection } from "@/components/analytics/InstitutionRadarSection";

const panel = "rounded-2xl border border-border bg-card p-5 md:p-6";
const control = "min-h-11 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground";
const action = "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90";
const secondaryAction = "inline-flex min-h-11 items-center justify-center rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-muted";
const reasons: Record<LearningTopic["reason"], string> = {
  unresolved: "Erros ainda pendentes", reviews_due: "Revisões vencidas", low_accuracy: "Investigar dificuldade",
  needs_assessment: "Avaliar com questões novas", follow_up: "Conferir retenção depois", monitor: "Acompanhar",
};
const followUp: Record<LearningTopic["follow_up"], string> = {
  needs_work: "Ainda há erros pendentes", delayed_check_pending: "Correção praticada · conferência posterior pendente",
  retention_observed: "Acerto posterior observado", needs_assessment: "Ainda não avaliado", monitor: "Em acompanhamento",
};
const percent = (value: number | null | undefined) => value == null ? "—" : `${Math.round(value * 100)}%`;
const date = (value: string) => value.split("T")[0].split("-").reverse().join("/");
const topicKey = (t: LearningTopic) => JSON.stringify([t.area, t.topic, t.legacy_topic]);

function Result({ measure }: { measure: LearningMeasure }) {
  return <span>{percent(measure.accuracy)} <span className="text-muted-foreground text-xs">({measure.correct}/{measure.total})</span></span>;
}

function TopicActions({ topic }: { topic: LearningTopic }) {
  return <div className="flex flex-wrap gap-2 mt-4">
    {topic.actions.errors && <Link href={topic.actions.errors} className={action}>Rever erros <ArrowRight size={14} /></Link>}
    {topic.actions.reviews && <Link href={topic.actions.reviews} className={secondaryAction}>Revisar vencidas ({topic.due})</Link>}
    {topic.actions.new && <Link href={topic.actions.new} className={secondaryAction}>Testar questões novas</Link>}
    {!topic.unseen && <p className="text-xs text-muted-foreground w-full">Não há questões inéditas disponíveis neste tema e escopo.</p>}
    {topic.pending_checks > 0 && !topic.due && <p className="text-xs text-muted-foreground w-full">Ainda falta uma resposta após intervalo. Consulte sua fila de revisões para planejar a conferência.</p>}
  </div>;
}

function Comparison({ current, previous, minimum }: { current: LearningMeasure; previous: LearningMeasure; minimum: number }) {
  const enough = current.total >= minimum && previous.total >= minimum;
  const delta = enough ? Math.round(((current.accuracy ?? 0) - (previous.accuracy ?? 0)) * 100) : null;
  return <p className="text-xs text-muted-foreground mt-3">
    Anterior: <Result measure={previous} />.
    {delta !== null ? ` Variação observada: ${delta > 0 ? "+" : ""}${delta} p.p.; as questões podem ter dificuldades diferentes.`
      : ` Ainda não comparamos: mínimo descritivo de ${minimum} questões em cada período.`}
  </p>;
}

// This optional detail deliberately uses lifetime first attempts, with its scope
// stated explicitly. The parent remounts it when the institution changes.
function InstitutionDetails({ institution, options }: { institution: string; options: LearningAnalysis["options"]["institutions"] }) {
  const [readiness, setReadiness] = useState<ExamReadiness | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.stats.getExamReadiness(institution || undefined, controller.signal).then(result => {
      if (!controller.signal.aborted) setReadiness(result);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [institution, retry]);
  return <div className="mt-5 space-y-5">
    <p className="text-sm text-muted-foreground">Detalhe histórico: primeira resposta de cada questão, em todo o histórico da banca. Os filtros de período, área e tema acima não se aplicam a esta comparação.</p>
    {error ? <div role="alert">Não foi possível carregar o perfil. <button className={secondaryAction} onClick={() => { setError(false); setRetry(n => n + 1); }}>Tentar novamente</button></div>
      : !readiness ? <p role="status">Carregando perfil…</p> : <section className={panel} aria-label="Perfil por área">
        <h3 className="font-bold">Desempenho por área · {readiness.institution_label || "Todas as bancas"}</h3>
        <p className="text-sm text-muted-foreground mt-2">{readiness.edital_profile?.status === "validated" ? "Perfil curricular validado" : "Perfil experimental: pesos provisórios, sem validação documental do edital"}. Estes resultados não são uma previsão de aprovação.</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 mt-4">
          {readiness.areas.map(a => <div key={a.area} className="rounded-xl border border-border p-3">
            <h4 className="font-medium text-sm">{a.area}</h4>
            <p className="text-2xl font-bold mt-2">{a.attempts ? percent(a.accuracy) : "—"}</p>
            <p className="text-xs text-muted-foreground">{a.attempts ? `${a.correct ?? 0}/${a.attempts} primeiras respostas` : "Ainda não avaliada"}</p>
            {a.attempts > 0 && <p className="text-xs text-muted-foreground mt-2">Estimativa suavizada: {percent(a.posterior_mean)} · intervalo de 95%: {percent(a.ci_lower)}–{percent(a.ci_upper)}</p>}
            {a.available > a.answered ? <Link className="inline-flex min-h-11 items-center text-primary text-sm mt-2" href={a.action}>Praticar inéditas</Link> : <p className="text-xs text-muted-foreground mt-2">Sem inéditas neste escopo.</p>}
          </div>)}
        </div>
      </section>}
    {options.length > 0 && <InstitutionRadarSection institutionOptions={options} defaultInstitution={institution || options[0].key} lockInstitution={!!institution} showPriorities={false} />}
  </div>;
}

export function AnalysisClient() {
  const [filters, setFilters] = useState<LearningAnalysisFilters>({ days: 30, institution: "", area: "", subtema: "", tz_offset: -180 });
  const [data, setData] = useState<LearningAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [visibleTopics, setVisibleTopics] = useState(15);
  const [institutionOpen, setInstitutionOpen] = useState(false);
  const [view, setView] = useState<"new_questions" | "delayed_reviews">("new_questions");

  useEffect(() => {
    const controller = new AbortController();
    const requestFilters = { ...filters, tz_offset: -new Date().getTimezoneOffset() };
    api.stats.getLearningAnalysis(requestFilters, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setData(result); setError(null); } })
      .catch(() => { if (!controller.signal.aborted) setError("Não foi possível carregar sua análise. Nenhuma conclusão foi gerada com dados ausentes."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [filters, retry]);

  function change(next: Partial<LearningAnalysisFilters>) {
    setLoading(true); setError(null); setVisibleTopics(15);
    setFilters(old => ({ ...old, ...next }));
  }
  function refresh() { setLoading(true); setError(null); setRetry(n => n + 1); }
  const summary = data?.summary;
  const options = data?.options;

  return <div className="space-y-6">
    <section className={panel} aria-label="Filtros da análise">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm font-medium">Período<select className={`${control} mt-1`} value={filters.days} onChange={e => change({ days: Number(e.target.value) })}>
          <option value={14}>Últimos 14 dias</option><option value={30}>Últimos 30 dias</option><option value={90}>Últimos 90 dias</option>
        </select></label>
        <label className="text-sm font-medium">Banca<select className={`${control} mt-1`} value={filters.institution} onChange={e => change({ institution: e.target.value, area: "", subtema: "" })}>
          <option value="">Todas as bancas</option>{options?.institutions.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select></label>
        <label className="text-sm font-medium">Área<select className={`${control} mt-1`} value={filters.area} onChange={e => change({ area: e.target.value, subtema: "" })}>
          <option value="">Todas as áreas</option>{options?.areas.map(a => <option key={a}>{a}</option>)}
        </select></label>
        <label className="text-sm font-medium">Tema<select className={`${control} mt-1`} value={filters.subtema} onChange={e => change({ subtema: e.target.value })}>
          <option value="">Todos os temas</option>{options?.subtemas.map(t => <option key={t}>{t}</option>)}
        </select></label>
      </div>
      <div className="flex items-center justify-between gap-3 mt-3">
        <p className="text-xs text-muted-foreground">Resultados no período; erros pendentes e revisões mostram a situação atual. As sessões de estudo preservam banca, área e tema.</p>
        <button type="button" className={secondaryAction} disabled={loading} onClick={refresh} aria-label="Atualizar análise"><RefreshCw size={16} /></button>
      </div>
    </section>

    {loading ? <div role="status" aria-live="polite" className={`${panel} text-muted-foreground`}>Atualizando evidências de aprendizagem…</div>
      : error ? <div role="alert" className={`${panel} border-destructive/40`}><p>{error}</p><button type="button" onClick={refresh} className={`${action} mt-4`}>Tentar novamente</button></div>
      : data && summary && <>
        <p className="text-xs text-muted-foreground">{date(data.scope.start)}–{date(data.scope.end)} (inclui hoje) · comparação com {date(data.scope.previous_start)}–{date(data.scope.previous_end)} · horário local UTC{data.scope.tz_offset >= 0 ? "+" : ""}{data.scope.tz_offset / 60}.</p>

        <section aria-labelledby="priorities-title" className={panel}>
          <div className="flex items-start gap-3"><Target className="text-primary shrink-0 mt-1" size={22} /><div>
            <h2 id="priorities-title" className="text-xl font-bold">Suas próximas prioridades</h2>
            <p className="text-sm text-muted-foreground mt-1">Até 3 prioridades de correção e revisão, com espaço separado para avaliar temas pouco explorados.</p>
          </div></div>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mt-5">
            {data.priorities.map(t => <article key={topicKey(t)} className="rounded-xl border border-border p-4 flex flex-col" aria-label={t.topic}>
              <span className={`text-xs font-semibold ${t.reason === "unresolved" ? "text-destructive" : "text-primary"}`}>{reasons[t.reason]}</span>
              <p className="text-xs text-muted-foreground mt-3">{t.area}</p><h3 className="font-bold mt-1">{t.topic}</h3>
              <p className="text-sm mt-3">{t.new_questions.total ? <>{t.new_questions.correct}/{t.new_questions.total} acertos em questões novas no período.</> : "Sem primeiras respostas neste período; isso não demonstra uma dificuldade."}</p>
              <p className="text-xs text-muted-foreground mt-2">{t.unresolved} erros pendentes · {t.due} revisões vencidas · {t.unseen} inéditas disponíveis</p>
              <div className="mt-auto"><TopicActions topic={t} /></div>
            </article>)}
          </div>
          {data.priorities.length === 0 && <p className="text-sm text-muted-foreground mt-4">{summary.available ? "Nenhuma prioridade pelos critérios atuais. Confira a evolução e os temas abaixo; isso não comprova domínio." : "Não há questões disponíveis neste escopo. Experimente ampliar os filtros."}</p>}
          <p className="text-xs text-muted-foreground mt-5 border-t border-border pt-4">Planejamento no escopo: até {data.goal.questions} questões, incluindo até {data.goal.reviews} revisões vencidas. Capacidade estimada de {data.goal.capacity} questões em {data.goal.hours}h; ajuste ao seu ritmo.{data.goal.pending > 0 ? ` ${data.goal.pending} revisões continuam pendentes; não foram reagendadas.` : ""}</p>
        </section>

        <section aria-labelledby="evidence-title">
          <h2 id="evidence-title" className="text-xl font-bold mb-4">Como está sua aprendizagem?</h2>
          <div className="grid md:grid-cols-3 gap-4">
            <article className={panel}><BookOpen size={20} className="text-primary" /><h3 className="font-semibold mt-3">Questões novas</h3><p className="text-3xl font-bold mt-2"><Result measure={summary.new_questions} /></p><p className="text-xs text-muted-foreground mt-2">Só a primeira resposta de cada questão no período.</p><Comparison current={summary.new_questions} previous={summary.previous_new_questions} minimum={data.method.comparison_minimum} /></article>
            <article className={panel}><Clock size={20} className="text-primary" /><h3 className="font-semibold mt-3">Revisões após intervalo</h3><p className="text-3xl font-bold mt-2"><Result measure={summary.delayed_reviews} /></p><p className="text-xs text-muted-foreground mt-2">Última revisão elegível por questão no período, após ao menos {data.method.delayed_review_hours}h sem responder à mesma questão.</p><Comparison current={summary.delayed_reviews} previous={summary.previous_delayed_reviews} minimum={data.method.comparison_minimum} /></article>
            <article className={panel}><Target size={20} className="text-destructive" /><h3 className="font-semibold mt-3">Erros ainda pendentes</h3><p className="text-3xl font-bold mt-2">{summary.unresolved}</p><p className="text-xs text-muted-foreground mt-2">Questões cuja última resposta registrada está errada, em todo o histórico do escopo. {summary.recurring} têm mais de um erro registrado.</p><p className="text-xs text-muted-foreground mt-3">{summary.corrected} questões antes erradas tiveram a última resposta registrada correta; {summary.pending_checks} ainda sem acerto posterior após intervalo.</p></article>
          </div>
        </section>

        <section className={panel} aria-labelledby="followup-title">
          <h2 id="followup-title" className="text-xl font-bold flex items-center gap-2"><CheckCircle2 size={22} className="text-primary" />A correção permaneceu?</h2>
          <p className="text-sm text-muted-foreground mt-2">Histórico do escopo: {summary.corrected} questões corrigidas, das quais {summary.retained_corrections} tiveram um acerto após intervalo desde o último erro. {summary.pending_checks} aguardam essa evidência. Esses acertos não comprovam domínio de todo o tema.</p>
          <div className="mt-4 space-y-3">
            {data.topics.filter(t => t.corrected > 0).slice(0, 5).map(t => <div key={topicKey(t)} className="border-t border-border pt-3">
              <p className="font-medium text-sm">{t.topic} <span className="text-xs text-muted-foreground">· {t.area}</span></p>
              <p className="text-xs text-muted-foreground mt-1">{followUp[t.follow_up]} · {t.corrected} corrigidas · {t.retained_corrections} com acerto posterior · {t.pending_checks} pendentes</p>
              {t.change_pp !== null && <p className="text-xs mt-1">Questões novas: <Result measure={t.previous_new_questions} /> → <Result measure={t.new_questions} />. Variação de {t.change_pp > 0 ? "+" : ""}{t.change_pp} p.p., sem ajuste de dificuldade.</p>}
              <TopicActions topic={t} />
            </div>)}
            {!summary.corrected && <p className="text-sm text-muted-foreground">Ainda não há correções registradas para acompanhar neste escopo.</p>}
          </div>
        </section>

        <section className={panel} aria-labelledby="memory-title">
          <h2 id="memory-title" className="text-xl font-bold">Revisões e risco estimado</h2>
          <p className="text-sm text-muted-foreground mt-2">{summary.due} revisões vencidas. {summary.tracked ? `${summary.at_risk} de ${summary.tracked} questões acompanhadas estão abaixo de ${Math.round(data.method.retention_target * 100)}% de retenção estimada pelo FSRS.` : "Ainda não há estimativas de memória disponíveis neste escopo."}</p>
          {summary.tracked > 0 && !summary.at_risk && <p className="text-xs text-muted-foreground mt-2">Nenhuma questão acompanhada abaixo do limiar agora. Temas não acompanhados continuam sem avaliação de memória.</p>}
          <div className="grid md:grid-cols-2 gap-3 mt-4">{data.topics.filter(t => t.at_risk || t.due).sort((a, b) => b.due - a.due || b.at_risk - a.at_risk).slice(0, 6).map(t => <div key={topicKey(t)} className="rounded-xl border border-border p-4">
            <h3 className="font-semibold text-sm">{t.topic}</h3><p className="text-xs text-muted-foreground mt-1">{t.at_risk} abaixo do limiar · {t.due} vencidas{t.min_retrievability !== null ? ` · menor estimativa: ${percent(t.min_retrievability)}` : ""}</p>
            {t.actions.reviews ? <Link className={`${secondaryAction} mt-3`} href={t.actions.reviews}>Revisar vencidas ({t.due})</Link> : <p className="text-xs text-muted-foreground mt-3">Sem revisão vencida neste tema. O risco estimado e a data agendada são sinais diferentes.</p>}
          </div>)}</div>
        </section>

        <section className={panel} aria-labelledby="topics-title">
          <h2 id="topics-title" className="text-xl font-bold">Evidências por tema</h2><p className="text-sm text-muted-foreground mt-2">Amostras pequenas pedem investigação. Temas sem respostas não são classificados como fracos.</p>
          <div className="overflow-x-auto mt-4" role="region" aria-label="Tabela de evidências por tema" tabIndex={0}>
            <table className="w-full text-sm text-left min-w-[700px]"><caption className="sr-only">Resultados no período e acompanhamento atual por tema</caption><thead><tr className="border-b border-border text-muted-foreground"><th scope="col" className="p-3">Tema</th><th scope="col" className="p-3">Novas (acertos/total)</th><th scope="col" className="p-3">Revisões após intervalo</th><th scope="col" className="p-3">Pendentes</th><th scope="col" className="p-3">Próximo passo</th></tr></thead><tbody>
              {data.topics.slice(0, visibleTopics).map(t => <tr key={topicKey(t)} className="border-b border-border last:border-0"><th scope="row" className="p-3 font-medium"><span className="block text-xs text-muted-foreground font-normal">{t.area}</span>{t.topic}<span className="block text-xs text-muted-foreground font-normal mt-1">{followUp[t.follow_up]}</span></th><td className="p-3"><Result measure={t.new_questions} />{t.new_questions.total < 5 && <span className="block text-xs text-muted-foreground">{t.new_questions.total ? "Amostra pequena" : "Sem dados no período"}</span>}</td><td className="p-3"><Result measure={t.delayed_reviews} /></td><td className="p-3">{t.unresolved} erros<br /><span className="text-xs text-muted-foreground">{t.due} revisões</span></td><td className="p-3"><TopicActions topic={t} /></td></tr>)}
            </tbody></table>
          </div>
          {!data.topics.length && <p className="text-sm text-muted-foreground mt-4">Nenhum tema disponível para estes filtros.</p>}
          {data.topics.length > visibleTopics && <button className={`${secondaryAction} mt-4`} onClick={() => setVisibleTopics(n => n + 15)}>Mostrar mais temas ({data.topics.length - visibleTopics})</button>}
        </section>

        <details className={panel}><summary className="cursor-pointer font-semibold min-h-11">Evolução por semana</summary>
          <label className="block text-sm mt-3">Tipo de evidência<select className={`${control} mt-1 max-w-sm`} value={view} onChange={e => setView(e.target.value as typeof view)}><option value="new_questions">Questões novas</option><option value="delayed_reviews">Revisões após intervalo</option></select></label>
          <p className="text-xs text-muted-foreground mt-3">Blocos de 7 dias a partir do início do período; o último pode ser parcial. Cada questão revisada entra apenas no bloco da sua última revisão elegível do período.</p>
          <ul className="mt-4 space-y-3">{data.weeks.map(w => <li key={w.start} className="flex gap-3 items-center text-sm"><span className="shrink-0">{date(w.start)}</span><div className="h-2 rounded-full bg-muted flex-1" aria-hidden="true"><div className="h-2 rounded-full bg-primary" style={{ width: percent(w[view].accuracy ?? 0) }} /></div><span className="w-32 text-right"><Result measure={w[view]} /></span></li>)}</ul>
        </details>

        <details className={panel} open={institutionOpen} onToggle={e => setInstitutionOpen(e.currentTarget.open)}><summary className="cursor-pointer font-semibold min-h-11">Detalhes e comparação por banca</summary>
          {institutionOpen && <InstitutionDetails key={filters.institution} institution={filters.institution} options={data.options.institutions} />}
        </details>

        <details className={panel}><summary className="cursor-pointer font-semibold min-h-11">Como interpretar estes dados</summary><ul className="list-disc pl-5 text-sm text-muted-foreground space-y-2 mt-3">
          <li>Questões novas usam a primeira resposta de todo o seu histórico. Repetir uma questão não aumenta essa amostra.</li>
          <li>Revisões usam a última resposta por questão no período após pelo menos {data.method.delayed_review_hours}h desde a resposta anterior. Esse intervalo define o relatório; não muda seu agendamento.</li>
          <li>A comparação de períodos exige {data.method.comparison_minimum} questões em cada amostra apenas para reduzir ruído. Isso não é um critério validado de domínio. Hoje está incompleto, e a dificuldade e os temas podem variar.</li>
          <li>Correções são reconstruídas do histórico. Acertar logo após errar registra prática; um acerto posterior após intervalo acrescenta evidência de retenção da questão, sem provar transferência para todo o tema.</li>
          <li>Revisões vencidas, erros pendentes e correções consideram todo o histórico do escopo, inclusive fora do período selecionado.</li>
          <li>Confiança histórica pode ter sido registrada depois do gabarito ou preenchida automaticamente. Ela não é usada aqui para inferir convicção antes da resposta ou o motivo do erro.</li>
          <li>As prioridades são regras de organização: erros, revisões e desempenho inicial abaixo de 70% com ao menos 5 questões. Não são diagnósticos definitivos nem previsões de aprovação.</li>
        </ul></details>
      </>}
  </div>;
}
