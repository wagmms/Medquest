"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, BookOpen, Brain, Target, TrendingUp } from "lucide-react";
import type { LearningProfileTopic, ThemeProgress } from "@/types/api";
import { api } from "@/lib/api";
import { themeJourney } from "@/lib/themeJourney";

export function ThemeClient({ subtema, group, theme, topic, initialProgress }: {
  subtema: string;
  group: { area: string };
  theme: { highYield: boolean; details: string[] };
  topic?: LearningProfileTopic;
  initialProgress: ThemeProgress;
}) {
  const [progress, setProgress] = useState(initialProgress);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [saveError, setSaveError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  async function saveProgress(patch: Partial<Pick<ThemeProgress, "study_path" | "theory_completed">>) {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError("");
    setSaveMessage("");
    try {
      const saved = await api.themes.saveProgress(subtema, {
        theory_completed: progress.theory_completed, study_path: progress.study_path, ...patch,
      });
      setProgress(saved);
      setSaveMessage("Progresso salvo.");
    } catch {
      setSaveError("Não foi possível salvar. Confira sua conexão e tente novamente.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }
  const journey = themeJourney(subtema, topic, progress);
  const percent = (value: number) => `${Math.round(value * 100)}%`;
  const evidence = !topic || topic.attempts < 5 ? "Evidência inicial" : topic.attempts < 20 ? "Evidência em formação" : "Histórico em construção";
  const stages = [
    { title: "Diagnosticar", description: "Resolva até cinco questões inéditas. As questões já respondidas neste tema contam como ponto de partida.", status: journey.diagnosticComplete ? "Base inicial registrada" : `${Math.min(journey.answered, journey.diagnosticTarget)} de ${journey.diagnosticTarget} questões`, href: journey.diagnosticComplete ? journey.practice : journey.diagnostic, action: journey.diagnosticComplete ? "Seguir para prática" : "Iniciar diagnóstico", enabled: journey.available > 0 },
    { title: "Estudar", description: "Use suas dificuldades para orientar a leitura ou aula do seu material de referência. Depois, retorne à prática.", status: progress.theory_completed ? "Estudo teórico concluído por você" : "Estudo teórico pendente", href: "#roteiro", action: "Ver orientação de estudo", enabled: true },
    { title: "Praticar", description: "Sessão adaptativa no tamanho do percurso escolhido. Consulte as explicações e transforme os erros em flashcards durante a resolução.", status: `${topic?.attempts ?? 0} tentativas registradas`, href: journey.practice, action: "Praticar este tema", enabled: journey.available > 0 },
    { title: "Revisar", description: "Retome as questões deste tema no momento indicado pelo FSRS. Revise também os flashcards vinculados a este assunto.", status: `${journey.due} questões com revisão vencida`, href: journey.review, action: "Revisar este tema", enabled: journey.due > 0 },
  ];
  return (
    <div className="max-w-5xl mx-auto w-full flex flex-col gap-6 pb-8">
      <Link href="/cobertura" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary"><ArrowLeft size={16} /> Todos os temas</Link>
      <section className="rounded-2xl border border-border bg-card p-6 md:p-8">
        <p className="text-sm text-muted-foreground mb-2">{group.area}{theme.highYield ? " · Alta incidência USP" : ""}</p>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{subtema}</h1>
        <p className="text-muted-foreground mt-3">Seu ponto de encontro para diagnosticar, estudar, praticar e revisar este assunto.</p>
        
        {topic && topic.diag_accuracy != null && topic.prac_accuracy != null && progress.theory_completed && (
          <div className="mt-6 flex gap-4 p-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-emerald-900 dark:text-emerald-100">
             <TrendingUp className="text-emerald-500 shrink-0 mt-0.5" size={20} />
             <div>
               <p className="font-semibold mb-1">Delta de Aprendizado</p>
               <p className="text-sm">Seu desempenho no diagnóstico inicial foi de <strong>{Math.round(topic.diag_accuracy * 100)}%</strong>. Após o estudo teórico, sua prática alcançou <strong>{Math.round(topic.prac_accuracy * 100)}%</strong>. {(topic.prac_accuracy > topic.diag_accuracy) ? 'Excelente evolução!' : 'Continue praticando para fixar o conceito.'}</p>
             </div>
          </div>
        )}

        <div className="mt-6 rounded-xl bg-primary/5 border border-primary/20 p-5">
          <p className="font-semibold flex items-center gap-2"><Target size={18} /> Próximo passo</p>
          <p className="text-sm text-muted-foreground mt-2">{journey.next.reason}</p>
          <Link href={journey.next.href} className="inline-flex items-center gap-2 mt-4 bg-primary text-primary-foreground rounded-lg px-4 py-2 text-sm font-semibold">
            {journey.next.label}<ArrowRight size={16} />
          </Link>
        </div>
      </section>
      <section className="rounded-xl border border-border bg-card p-5">
        <fieldset disabled={saving}>
          <legend className="font-semibold mb-3">Seu percurso neste tema</legend>
          <div className="grid sm:grid-cols-2 gap-3">
            {([{ value: "essential", name: "Essencial", text: "Prática de até 10 questões e estudo dirigido às lacunas." }, { value: "complete", name: "Completo", text: "Prática de até 20 questões e estudo integral do assunto." }] as const).map(path => (
              <label key={path.value} className="flex gap-3 border border-border rounded-lg p-4 cursor-pointer has-checked:border-primary has-checked:bg-primary/5">
                <input type="radio" name="study-path" value={path.value} checked={progress.study_path === path.value} onChange={() => saveProgress({ study_path: path.value })} />
                <span><span className="block font-semibold text-sm">{path.name}</span><span className="text-xs text-muted-foreground">{path.text}</span></span>
              </label>
            ))}
          </div>
        </fieldset>
        <p className="text-xs text-muted-foreground mt-3">As revisões vencidas têm prioridade nos dois percursos. Você pode trocar a qualquer momento.</p>
        <p role="status" className="text-sm mt-2">{saving ? "Salvando…" : saveMessage}</p>
        {saveError && <p role="alert" className="text-sm text-destructive mt-2">{saveError}</p>}
      </section>
      <div className="grid md:grid-cols-2 gap-4">
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="font-semibold flex items-center gap-2"><BookOpen size={18} /> Atividade registrada</h2>
          <p className="text-3xl font-bold mt-4">{journey.answered}<span className="text-base font-normal text-muted-foreground"> / {journey.available} questões</span></p>
          <p className="text-sm text-muted-foreground mt-2">Questões distintas respondidas · {topic?.attempts ?? 0} tentativas no total.</p>
          <p className="text-xs text-muted-foreground mt-3">{progress.theory_completed ? "Estudo teórico marcado como concluído por você." : "Estudo teórico ainda não marcado como concluído."}</p>
        </section>
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="font-semibold flex items-center gap-2"><Brain size={18} /> Aprendizado</h2>
          <p className="text-3xl font-bold mt-4">{topic?.accuracy != null ? percent(topic.accuracy) : "Sem respostas"}<span className="text-base font-normal text-muted-foreground">{topic?.accuracy != null ? " de acertos" : ""}</span></p>
          <p className="text-sm text-muted-foreground mt-2">{evidence} · acertos sobre todas as tentativas.</p>
          <p className="text-xs text-muted-foreground mt-3">{topic?.retrievability != null ? `Menor retenção estimada entre as questões acompanhadas: ${percent(topic.retrievability)}.` : "Retenção ainda sem estimativa FSRS."} Concluir atividades não comprova domínio.</p>
        </section>
      </div>
      <section aria-labelledby="journey-title">
        <h2 id="journey-title" className="text-lg font-semibold mb-4">Sua jornada neste tema</h2>
        <ol className="grid md:grid-cols-2 gap-4">
          {stages.map((stage, index) => <li key={stage.title} className="rounded-xl border border-border bg-card p-5 flex flex-col gap-3">
            <h3 className="font-semibold"><span className="text-primary mr-2">{index + 1}.</span>{stage.title}</h3>
            <p className="text-sm text-muted-foreground flex-1">{stage.description}</p>
            <p className="text-xs font-medium">{stage.status}</p>
            {stage.title === "Revisar" && <Link href={journey.flashcards} className="text-sm font-semibold text-primary hover:underline">Flashcards do tema: {progress.flashcards_due} pendentes / {progress.flashcards_total} no total →</Link>}
            {stage.enabled ? <Link href={stage.href} className="text-sm font-semibold text-primary hover:underline">{stage.action} →</Link> : <p className="text-sm text-muted-foreground">{stage.title === "Revisar" ? "Nenhuma questão pendente agora" : "Aguardando questões neste tema"}</p>}
          </li>)}
        </ol>
      </section>
      <section id="roteiro" className="rounded-xl border border-border bg-card p-5 scroll-mt-6">
        <h2 className="font-semibold mb-3">Orientação de estudo</h2>
        <p className="text-sm text-muted-foreground">Revise os conceitos que geraram dúvida ou erro no diagnóstico. Consulte seu material de referência e use as explicações das questões para aprofundar o raciocínio.</p>
        <label className="flex items-center gap-3 my-4 text-sm font-medium cursor-pointer">
          <input type="checkbox" checked={progress.theory_completed} disabled={saving} onChange={event => saveProgress({ theory_completed: event.target.checked })} />
          Concluí o estudo teórico deste tema
        </label>
        <p className="text-xs text-muted-foreground">Este registro é pessoal e não altera seus acertos nem a estimativa de retenção.</p>
        {theme.details.length > 0 && <ul className="list-disc pl-5 mt-3 text-sm space-y-2">{theme.details.map(detail => <li key={detail}>{detail}</li>)}</ul>}
        <div className="flex flex-wrap gap-4 mt-4 text-sm font-semibold text-primary"><Link href="/planner">Ver meu planejamento →</Link><Link href={journey.flashcards}>Revisar flashcards deste tema →</Link></div>
      </section>
    </div>
  );
}
