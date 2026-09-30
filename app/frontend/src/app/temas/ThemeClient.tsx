"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  CheckCircle2,
  Clock,
  Layers,
  RotateCcw,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import type { LearningProfileTopic, ThemeProgress } from "@/types/api";
import { getThemeUrls } from "@/lib/themeJourney";

export function ThemeClient({
  subtema,
  group,
  theme,
  topic,
  initialProgress,
}: {
  subtema: string;
  group: { area: string };
  theme: { highYield: boolean; details: string[] };
  topic?: LearningProfileTopic;
  initialProgress: ThemeProgress;
}) {
  const [practiceLimit, setPracticeLimit] = useState<10 | 20 | 30>(20);
  const urls = getThemeUrls(subtema);

  const available = topic?.available ?? 0;
  const answered = topic?.answered ?? 0;
  const attempts = topic?.attempts ?? 0;
  const correct = topic?.correct ?? 0;
  const accuracy = topic?.accuracy ?? null;
  const retrievability = topic?.retrievability ?? null;
  const dueCount = topic?.due_count ?? 0;

  const coveragePct = available > 0 ? Math.min(100, Math.round((answered / available) * 100)) : 0;
  const flashcardsTotal = initialProgress?.flashcards_total ?? 0;
  const flashcardsDue = initialProgress?.flashcards_due ?? 0;

  return (
    <div className="max-w-5xl mx-auto w-full flex flex-col gap-6 pb-12">
      {/* Navegação de retorno */}
      <Link
        href="/cobertura"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
      >
        <ArrowLeft size={16} /> Todos os temas
      </Link>

      {/* Header do Tema */}
      <section className="rounded-2xl border border-border bg-card p-6 md:p-8 shadow-xs">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-muted text-muted-foreground">
            {group.area}
          </span>
          {theme.highYield && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              <Sparkles size={12} /> Alta incidência USP
            </span>
          )}
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">{subtema}</h1>
        <p className="text-muted-foreground mt-2 text-sm md:text-base">
          Central de Prática e Revisão Espaçada. Acompanhe seu domínio, revise pendências e resolva questões adaptativas.
        </p>

        {theme.details.length > 0 && (
          <div className="mt-5 pt-4 border-t border-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              Pontos-chave do edital:
            </p>
            <ul className="flex flex-wrap gap-2 text-xs">
              {theme.details.map((detail) => (
                <li
                  key={detail}
                  className="px-2.5 py-1 rounded-md bg-muted/60 text-foreground border border-border"
                >
                  {detail}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* 4 KPIs de Desempenho */}
      <section aria-labelledby="kpis-title">
        <h2 id="kpis-title" className="sr-only">Indicadores de desempenho do tema</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* KPI 1: Cobertura */}
          <div className="rounded-xl border border-border bg-card p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-muted-foreground mb-2">
                <span className="text-xs font-medium">Cobertura</span>
                <Target size={16} />
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl font-bold tracking-tight">{answered}</span>
                <span className="text-xs text-muted-foreground">/ {available} q</span>
                <span className="ml-auto text-xs font-semibold px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                  {coveragePct}%
                </span>
              </div>
              <div className="w-full bg-muted rounded-full h-1.5 mt-3 overflow-hidden">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${coveragePct}%` }}
                />
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">
              {attempts} {attempts === 1 ? "tentativa total" : "tentativas no total"}
            </p>
          </div>

          {/* KPI 2: Acurácia Geral */}
          <div className="rounded-xl border border-border bg-card p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-muted-foreground mb-2">
                <span className="text-xs font-medium">Acurácia Geral</span>
                <Zap size={16} />
              </div>
              <p className="text-2xl font-bold tracking-tight">
                {accuracy != null ? `${Math.round(accuracy * 100)}%` : "—"}
              </p>
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">
              {attempts > 0 ? `${correct} acertos em ${attempts} tentativas` : "Nenhuma resposta registrada"}
            </p>
          </div>

          {/* KPI 3: Retenção FSRS */}
          <div className="rounded-xl border border-border bg-card p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-muted-foreground mb-2">
                <span className="text-xs font-medium">Retenção FSRS</span>
                <Brain size={16} />
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl font-bold tracking-tight">
                  {retrievability != null ? `${Math.round(retrievability * 100)}%` : "—"}
                </span>
                {retrievability != null && (
                  <span className="text-xs text-muted-foreground">est.</span>
                )}
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">
              {retrievability != null
                ? "Probabilidade de recordação estimada"
                : "Estimada após revisões FSRS"}
            </p>
          </div>

          {/* KPI 4: Fila de Revisões */}
          <div
            className={`rounded-xl border p-4 flex flex-col justify-between transition-colors ${
              dueCount > 0
                ? "border-amber-500/40 bg-amber-500/5 dark:bg-amber-500/10"
                : "border-border bg-card"
            }`}
          >
            <div>
              <div className="flex items-center justify-between text-muted-foreground mb-2">
                <span className="text-xs font-medium">FSRS Vencidas</span>
                <Clock
                  size={16}
                  className={dueCount > 0 ? "text-amber-600 dark:text-amber-400" : ""}
                />
              </div>
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-2xl font-bold tracking-tight ${
                    dueCount > 0 ? "text-amber-600 dark:text-amber-400" : ""
                  }`}
                >
                  {dueCount}
                </span>
                <span
                  className={`text-xs font-medium ${
                    dueCount > 0
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  {dueCount > 0 ? "urgentes" : "em dia"}
                </span>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">
              {dueCount > 0
                ? "Aguardando repetição espaçada"
                : "Nenhuma questão vencida agora"}
            </p>
          </div>
        </div>
      </section>

      {/* Ações Rápidas de Estudo */}
      <section aria-labelledby="actions-title" className="flex flex-col gap-4">
        <div>
          <h2 id="actions-title" className="text-lg font-semibold tracking-tight text-foreground">
            Ações de Estudo
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Escolha como prefere praticar ou revisar este tema hoje.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {/* Card 1: Revisar Questões Vencidas (FSRS) */}
          <div
            className={`rounded-xl border p-5 flex flex-col justify-between transition-all ${
              dueCount > 0
                ? "border-amber-500/40 bg-card shadow-xs ring-1 ring-amber-500/20"
                : "border-border bg-card"
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div
                  className={`p-2 rounded-lg ${
                    dueCount > 0
                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  <RotateCcw size={20} />
                </div>
                {dueCount > 0 ? (
                  <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
                    {dueCount} {dueCount === 1 ? "vencida" : "vencidas"}
                  </span>
                ) : (
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                    0 pendentes
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-base text-foreground">Revisar Vencidas (FSRS)</h3>
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                Repita as questões no intervalo ideal calculado pelo algoritmo para evitar o esquecimento
                e fortalecer a retenção de longo prazo.
              </p>
            </div>

            <div className="mt-6">
              {dueCount > 0 ? (
                <Link
                  href={urls.review}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-sm transition-colors shadow-xs"
                >
                  Revisar Agora ({dueCount}) <ArrowRight size={16} />
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-muted text-muted-foreground font-medium text-xs cursor-not-allowed"
                >
                  <CheckCircle2 size={15} className="text-emerald-500" />
                  Nenhuma revisão pendente
                </button>
              )}
            </div>
          </div>

          {/* Card 2: Praticar Adaptativo (Card Principal) */}
          <div className="rounded-xl border-2 border-primary/30 bg-card p-5 flex flex-col justify-between shadow-xs relative">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Zap size={20} />
                </div>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                  Recomendado
                </span>
              </div>
              <h3 className="font-semibold text-base text-foreground">Praticar Adaptativo</h3>
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                Sessão com priorização inteligente: dá preferência a questões inéditas e conceitos com
                menor retenção neste assunto.
              </p>

              {/* Seletor rápido de quantidade de questões */}
              <div className="mt-4 pt-3 border-t border-border">
                <label className="block text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Tamanho da sessão:
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {([10, 20, 30] as const).map((count) => (
                    <button
                      key={count}
                      type="button"
                      onClick={() => setPracticeLimit(count)}
                      className={`py-1.5 px-2 rounded-lg text-xs font-semibold border transition-all ${
                        practiceLimit === count
                          ? "bg-primary text-primary-foreground border-primary shadow-xs"
                          : "bg-muted/40 text-muted-foreground border-border hover:border-foreground/20 hover:text-foreground"
                      }`}
                    >
                      {count} questões
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6">
              {available > 0 ? (
                <Link
                  href={urls.practice(practiceLimit)}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-sm transition-colors shadow-xs"
                >
                  Iniciar Prática ({practiceLimit} q) <ArrowRight size={16} />
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-muted text-muted-foreground font-medium text-xs cursor-not-allowed"
                >
                  Sem questões disponíveis
                </button>
              )}
            </div>
          </div>

          {/* Card 3: Flashcards do Tema */}
          <div className="rounded-xl border border-border bg-card p-5 flex flex-col justify-between shadow-xs">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Layers size={20} />
                </div>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                  {flashcardsTotal > 0
                    ? `${flashcardsDue} pendentes / ${flashcardsTotal} total`
                    : "0 flashcards"}
                </span>
              </div>
              <h3 className="font-semibold text-base text-foreground">Flashcards do Tema</h3>
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                {flashcardsTotal > 0
                  ? "Revise os cartões atômicos vinculados a este tema para consolidar critérios diagnósticos, condutas e doses."
                  : "Você ainda não possui flashcards salvos para este tema. Você pode gerá-los a partir dos seus erros ao resolver questões."}
              </p>
            </div>

            <div className="mt-6">
              {flashcardsTotal > 0 ? (
                <Link
                  href={urls.flashcards}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg border border-primary/30 hover:bg-primary/10 text-primary font-semibold text-sm transition-colors"
                >
                  Revisar Flashcards <ArrowRight size={16} />
                </Link>
              ) : (
                <Link
                  href="/revisao-ativa"
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg border border-border hover:bg-muted/40 text-muted-foreground font-medium text-xs transition-colors"
                >
                  Abrir Revisão Geral <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Links de Apoio */}
      <footer className="pt-4 flex flex-wrap items-center justify-between gap-4 border-t border-border text-xs text-muted-foreground">
        <div className="flex items-center gap-4">
          <Link href="/planner" className="hover:text-primary transition-colors">
            Ver planejamento semanal no Planner →
          </Link>
          <Link href="/cobertura" className="hover:text-primary transition-colors">
            Ver mapa de cobertura completo →
          </Link>
        </div>
        <p>MedQuest · Aprendizado Adaptativo</p>
      </footer>
    </div>
  );
}
