"use client";

import React, { useState } from "react";
import Link from "next/link";
import { 
  Sparkles, Target, AlertTriangle, ArrowRight, 
  RotateCcw, Brain, CheckCircle2, ChevronRight, X, ExternalLink
} from "lucide-react";
import { BottleneckTopic, PreceptorFocusResponse } from "@/types/api";
import { api } from "@/lib/api";
import { FormattedContent } from "@/components/FormattedContent";

interface PreceptorFocusCardProps {
  initialBottlenecks?: BottleneckTopic[];
  srsDueCount?: number;
  overallAccuracy?: number | null;
  totalAttempts?: number;
}

export function PreceptorFocusCard({
  initialBottlenecks = [],
  srsDueCount = 0,
  overallAccuracy,
  totalAttempts = 0,
}: PreceptorFocusCardProps) {
  const [isOpenModal, setIsOpenModal] = useState(false);
  const [loadingAi, setLoadingAi] = useState(false);
  const [focusData, setFocusData] = useState<PreceptorFocusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Tópico prioritário imediato (baseado nos gargalos já carregados)
  const topBottleneck = initialBottlenecks.length > 0 ? initialBottlenecks[0] : null;
  const currentSubtema = focusData?.recommended_topic?.subtema || topBottleneck?.subtema || "Síndromes Coronarianas Agudas";
  const currentArea = focusData?.recommended_topic?.area || topBottleneck?.area || "Clínica Médica";
  const practiceUrl = focusData?.recommended_topic?.practice_url || 
    (topBottleneck ? topBottleneck.practice_url : `/estudar?subtema=${encodeURIComponent(currentSubtema)}&limit=15`);

  const handleOpenAiDiagnosis = async (forceRefresh = false) => {
    setIsOpenModal(true);
    if (focusData?.analysis_markdown && !forceRefresh) {
      return;
    }

    setLoadingAi(true);
    setErrorMsg(null);
    try {
      const data = await api.ai.getPreceptorFocus({ generateAi: true, forceRefresh });
      setFocusData(data);
    } catch (err: unknown) {
      console.error("Falha ao obter foco do Preceptor IA:", err);
      const msg = err instanceof Error ? err.message : "Não foi possível carregar o diagnóstico da IA no momento.";
      setErrorMsg(msg);
    } finally {
      setLoadingAi(false);
    }
  };

  return (
    <>
      {/* CARD PRINCIPAL NO DASHBOARD */}
      <section 
        aria-label="Plano de Ataque do Preceptor IA"
        className="shrink-0 relative overflow-hidden rounded-2xl sm:rounded-3xl border border-purple-500/30 bg-gradient-to-br from-purple-950/20 via-card to-card p-4 sm:p-6 shadow-sm transition-all hover:border-purple-500/50 group"
      >
        {/* Glow decorativo de fundo */}
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-purple-500/10 blur-3xl" />
        
        <div className="relative z-10 flex flex-col gap-4">
          {/* Header do Card */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-500/15 text-purple-600 dark:text-purple-400 ring-1 ring-purple-500/30">
                <Brain className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-purple-600 dark:text-purple-400">
                    Preceptor IA
                  </span>
                  <span className="rounded bg-purple-500/10 px-1.5 py-0.2 text-[10px] font-bold text-purple-600 dark:text-purple-400">
                    Adaptativo
                  </span>
                </div>
                <h3 className="text-sm sm:text-base font-bold text-foreground">
                  Plano de Ataque do Dia
                </h3>
              </div>
            </div>

            <button
              onClick={() => handleOpenAiDiagnosis(false)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-xs font-bold text-purple-600 dark:text-purple-400 transition-all hover:bg-purple-500/20 active:scale-95"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Raio-X Completo da IA</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Grid de Métricas Diagnósticas */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
            {/* Bloco 1: Tema Vulnerável Prioritário */}
            <div className="flex flex-col justify-between rounded-xl sm:rounded-2xl border border-border/50 bg-muted/20 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  <span>Subtema Prioritário de Retificação</span>
                </div>
                <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-bold text-muted-foreground shrink-0">
                  {currentArea}
                </span>
              </div>

              <div className="mt-2">
                <h4 className="text-sm sm:text-base font-bold text-foreground line-clamp-1" title={currentSubtema}>
                  {currentSubtema}
                </h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {topBottleneck ? (
                    <>
                      <strong className="text-rose-600 dark:text-rose-400 font-semibold">{topBottleneck.unresolved_count ?? topBottleneck.wrong_count} erros</strong> pendentes ({topBottleneck.accuracy_pct}% de acerto)
                    </>
                  ) : (
                    "Tema estratégico com alto peso nas bancas paulistas e nacionais."
                  )}
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-border/30 flex items-center justify-between">
                <span className="text-[11px] text-muted-foreground">Meta sugerida: 15 Qs</span>
                <Link
                  href={practiceUrl}
                  className="text-xs font-bold text-primary hover:underline inline-flex items-center gap-1"
                >
                  Praticar este tema <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>

            {/* Bloco 2: Curva de Esquecimento (FSRS) */}
            <div className="flex flex-col justify-between rounded-xl sm:rounded-2xl border border-border/50 bg-muted/20 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-purple-600 dark:text-purple-400">
                  <Target className="h-3.5 w-3.5 shrink-0" />
                  <span>Repetição Espaçada (FSRS v6)</span>
                </div>
                <span className="rounded-md bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-bold text-purple-600 dark:text-purple-400 shrink-0">
                  Curva de Retenção
                </span>
              </div>

              <div className="mt-2">
                <h4 className="text-sm sm:text-base font-bold text-foreground">
                  {srsDueCount > 0 ? (
                    <span className="text-purple-600 dark:text-purple-400">
                      {srsDueCount} {srsDueCount === 1 ? "revisão pronta hoje" : "revisões prontas hoje"}
                    </span>
                  ) : (
                    <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4" /> Todas as revisões em dia!
                    </span>
                  )}
                </h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {srsDueCount > 0 
                    ? "Revise antes de fazer questões novas para garantir retenção > 85%."
                    : "Sua retenção de longo prazo está blindada para este ciclo."
                  }
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-border/30 flex items-center justify-between">
                <span className="text-[11px] text-muted-foreground">
                  {overallAccuracy != null 
                    ? `${Math.round(overallAccuracy)}% acerto (${totalAttempts} Qs)` 
                    : `${totalAttempts} Qs feitas`}
                </span>
                {srsDueCount > 0 ? (
                  <Link
                    href="/estudar?status=srs_due&limit=100"
                    className="text-xs font-bold text-purple-600 dark:text-purple-400 hover:underline inline-flex items-center gap-1"
                  >
                    Revisar agora <ArrowRight className="h-3 w-3" />
                  </Link>
                ) : (
                  <Link
                    href="/revisao-ativa"
                    className="text-xs font-bold text-primary hover:underline inline-flex items-center gap-1"
                  >
                    Ver flashcards <ArrowRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            </div>
          </div>

          {/* Barra de Ação Rápida */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <div className="text-xs text-muted-foreground flex items-center gap-2 self-start sm:self-auto">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Algoritmo calibrado com base no seu histórico real de tentativas</span>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => handleOpenAiDiagnosis(false)}
                className="flex-1 sm:flex-none px-4 py-2 rounded-xl border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 font-bold text-xs transition-colors flex items-center justify-center gap-1.5"
              >
                <Brain className="h-4 w-4" />
                <span>Ver Análise Clínica</span>
              </button>
              
              <Link
                href={practiceUrl}
                className="flex-1 sm:flex-none px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs transition-colors flex items-center justify-center gap-1.5 shadow-sm"
              >
                <span>Iniciar Bateria do Foco (15 Qs)</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* MODAL / GAVETA DO PARECER COMPLETO DA IA */}
      {isOpenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col rounded-3xl border border-border/80 bg-card shadow-2xl overflow-hidden">
            {/* Header do Modal */}
            <div className="flex items-center justify-between border-b border-border/60 p-4 sm:p-5 bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-purple-500/15 text-purple-600 dark:text-purple-400 ring-1 ring-purple-500/30">
                  <Brain className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-purple-600 dark:text-purple-400">
                      Preceptor Socrático
                    </span>
                    <span className="text-[10px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 px-2 py-0.5 rounded-full border border-purple-500/20">
                      Diagnóstico de Alto Rendimento
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-foreground">
                    Raio-X de Desempenho & Diretriz do Dia
                  </h3>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => handleOpenAiDiagnosis(true)}
                  disabled={loadingAi}
                  title="Atualizar diagnóstico com IA"
                  className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl transition-colors disabled:opacity-50"
                >
                  <RotateCcw className={`h-4 w-4 ${loadingAi ? "animate-spin" : ""}`} />
                </button>
                <button
                  type="button"
                  onClick={() => setIsOpenModal(false)}
                  className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Conteúdo do Modal */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
              {loadingAi ? (
                <div className="flex flex-col items-center justify-center py-12 text-center space-y-4">
                  <div className="relative flex items-center justify-center">
                    <div className="h-14 w-14 rounded-full border-2 border-purple-500/20 border-t-purple-600 animate-spin" />
                    <Brain className="h-6 w-6 text-purple-600 dark:text-purple-400 absolute" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">
                      O Preceptor IA está avaliando seu perfil...
                    </h4>
                    <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                      Cruzando suas tentativas e erros com as armadilhas mais recorrentes das grandes bancas (USP, ENARE, UNIFESP e SUS-SP).
                    </p>
                  </div>
                </div>
              ) : errorMsg ? (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-center">
                  <AlertTriangle className="h-6 w-6 text-rose-500 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-rose-600 dark:text-rose-400">{errorMsg}</p>
                  <button
                    onClick={() => handleOpenAiDiagnosis(true)}
                    className="mt-3 px-4 py-1.5 bg-rose-600 text-white rounded-xl text-xs font-bold hover:bg-rose-700 transition-colors"
                  >
                    Tentar novamente
                  </button>
                </div>
              ) : focusData?.analysis_markdown ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <FormattedContent content={focusData.analysis_markdown} />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Clique no botão para gerar seu parecer com o Preceptor IA.
                </p>
              )}
            </div>

            {/* Rodapé do Modal */}
            <div className="border-t border-border/60 p-4 bg-muted/20 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground text-center sm:text-left">
                Plano direcionado para bancas paulistas e nacionais.
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={() => setIsOpenModal(false)}
                  className="flex-1 sm:flex-none px-4 py-2 rounded-xl border border-border/70 hover:bg-muted text-xs font-semibold transition-colors"
                >
                  Fechar
                </button>
                <Link
                  href={practiceUrl}
                  onClick={() => setIsOpenModal(false)}
                  className="flex-1 sm:flex-none px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs transition-colors flex items-center justify-center gap-1.5 shadow-sm"
                >
                  <span>Iniciar Bateria (15 Qs)</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
