"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Target,
  Zap,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  HelpCircle,
  Activity
} from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { BlindspotsResponse, BlindspotSeverity } from "@/types/api";

export interface BlindspotsRadarSectionProps {
  initialData?: BlindspotsResponse | null;
}

export const BlindspotsRadarSection: React.FC<BlindspotsRadarSectionProps> = ({ initialData }) => {
  const [data, setData] = useState<BlindspotsResponse | null>(initialData || null);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) return;
    const controller = new AbortController();

    api.stats.getBlindspots(6, controller.signal)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          console.error("Erro ao carregar radar de pontos cegos:", err);
          setError("Não foi possível carregar o diagnóstico de pontos cegos.");
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [initialData]);

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-2xl p-6 shadow-sm animate-pulse space-y-4">
        <div className="h-6 w-56 bg-muted rounded-md" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="h-24 bg-muted/60 rounded-xl" />
          <div className="h-24 bg-muted/60 rounded-xl" />
          <div className="h-24 bg-muted/60 rounded-xl" />
        </div>
        <div className="h-44 bg-muted/40 rounded-xl" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-card border border-border rounded-2xl p-6 shadow-sm flex flex-col items-center justify-center text-center gap-3">
        <AlertTriangle className="text-warning w-8 h-8" />
        <p className="text-sm font-medium text-foreground">{error || "Dados não disponíveis no momento."}</p>
        <button
          onClick={() => {
            setLoading(true);
            setError(null);
            api.stats.getBlindspots(6)
              .then(setData)
              .catch(() => setError("Erro ao recarregar dados."))
              .finally(() => setLoading(false));
          }}
          className="text-xs bg-muted hover:bg-muted/80 text-foreground px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
        >
          <RotateCcw size={14} /> Tentar novamente
        </button>
      </div>
    );
  }

  const { summary, blindspots } = data;
  const criticalCount = blindspots.filter((b) => b.severity === "CRITICAL").length;
  const highCount = blindspots.filter((b) => b.severity === "HIGH").length;

  const getSeverityBadge = (severity: BlindspotSeverity) => {
    switch (severity) {
      case "CRITICAL":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30">
            <ShieldAlert size={12} /> Crítico
          </span>
        );
      case "HIGH":
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <AlertTriangle size={12} /> Alta Prioridade
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30">
            <Activity size={12} /> Em Atenção
          </span>
        );
    }
  };

  return (
    <div className="bg-card border border-border shadow-sm rounded-2xl p-6 lg:p-7 space-y-6">
      {/* Header com Ação de Treino */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-rose-500/15 text-rose-600 dark:text-rose-400 flex items-center justify-center">
              <Target size={18} />
            </div>
            <h2 className="text-xl font-black text-foreground tracking-tight">
              Radar de Pontos Cegos & Caderno de Erros
            </h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Diagnóstico multidimensional de vulnerabilidades com treino de retificação ativa.
          </p>
        </div>

        {summary.unresolved_errors_count > 0 && (
          <Link
            href="/estudar?mode=remediation&limit=10"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-gradient-to-r from-rose-600 via-rose-500 to-primary hover:opacity-95 text-white font-bold px-5 py-2.5 rounded-xl shadow-md transition-all hover:scale-[1.02] text-sm shrink-0"
          >
            <Zap size={16} className="fill-white" />
            Iniciar Treino de Recuperação (10 Qs)
          </Link>
        )}
      </div>

      {/* Top Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Card 1: Taxa de Cura */}
        <div className="bg-muted/30 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Taxa de Superação
            </span>
            <CheckCircle2 size={16} className="text-emerald-500" />
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-foreground">
              {summary.healing_rate_pct}%
            </div>
            <div className="w-full bg-border h-1.5 rounded-full overflow-hidden mt-1.5">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, summary.healing_rate_pct)}%` }}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            <strong className="text-foreground">{summary.healed_count}</strong> erros já retificados com sucesso.
          </p>
        </div>

        {/* Card 2: Questões Pendentes */}
        <div className="bg-muted/30 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Aguardando Retificação
            </span>
            <AlertTriangle size={16} className="text-rose-500" />
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-rose-600 dark:text-rose-400">
              {summary.unresolved_errors_count}
            </div>
            <span className="text-xs text-muted-foreground">questões com último status incorreto</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Priorizadas automaticamente no treino ativo.
          </p>
        </div>

        {/* Card 3: Vulnerabilidades Mapeadas */}
        <div className="bg-muted/30 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Pontos Críticos
            </span>
            <ShieldAlert size={16} className="text-amber-500" />
          </div>
          <div className="my-2">
            <div className="text-2xl font-black text-foreground">
              {criticalCount + highCount}{" "}
              <span className="text-xs font-medium text-muted-foreground">de {summary.total_blindspots} subtemas</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              {criticalCount > 0 && (
                <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400">
                  {criticalCount} crítico(s)
                </span>
              )}
              {highCount > 0 && (
                <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400">
                  {highCount} alta prioridade
                </span>
              )}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Baseado em erro recente, distratores e FSRS.
          </p>
        </div>
      </div>

      {/* Lista de Pontos Cegos */}
      {blindspots.length === 0 ? (
        <div className="border border-dashed border-border rounded-xl p-8 text-center space-y-2 bg-muted/10">
          <Sparkles className="mx-auto text-primary w-8 h-8 opacity-80" />
          <h3 className="font-bold text-foreground text-sm">Nenhum ponto cego crítico no momento!</h3>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Excelente aproveitamento. Conforme você resolver novos simulados e questões, o algoritmo mapeará automaticamente qualquer fraqueza conceitual para treino direcionado.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground uppercase tracking-wider px-1">
            <span>Subtemas Mais Vulneráveis</span>
            <span>Ações de Retificação</span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {blindspots.map((item) => (
              <div
                key={item.subtema}
                className={clsx(
                  "border rounded-xl p-4 transition-all hover:shadow-sm bg-card flex flex-col md:flex-row items-start md:items-center justify-between gap-4",
                  item.severity === "CRITICAL"
                    ? "border-rose-500/25 bg-rose-500/[0.02]"
                    : item.severity === "HIGH"
                    ? "border-amber-500/25 bg-amber-500/[0.02]"
                    : "border-border"
                )}
              >
                {/* Informações do Ponto Cego */}
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {getSeverityBadge(item.severity)}
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-muted text-muted-foreground">
                      {item.area}
                    </span>
                    <h4 className="font-bold text-foreground text-sm truncate" title={item.subtema}>
                      {item.subtema}
                    </h4>
                  </div>

                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {item.clinical_insight}
                  </p>

                  {/* Badges de Apoio */}
                  <div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
                    <span className="font-semibold text-foreground">
                      Acurácia:{" "}
                      <span
                        className={clsx(
                          item.accuracy_pct >= 70
                            ? "text-emerald-500"
                            : item.accuracy_pct >= 50
                            ? "text-amber-500"
                            : "text-rose-500"
                        )}
                      >
                        {item.accuracy_pct}%
                      </span>{" "}
                      <span className="text-muted-foreground font-normal">({item.correct}/{item.attempts})</span>
                    </span>

                    {item.unresolved_count > 0 && (
                      <span className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400 font-semibold bg-rose-500/10 px-2 py-0.5 rounded">
                        <AlertTriangle size={11} /> {item.unresolved_count} a retificar
                      </span>
                    )}

                    {item.frequent_distractor && (
                      <span className="inline-flex items-center gap-1 text-muted-foreground bg-muted px-2 py-0.5 rounded">
                        <HelpCircle size={11} /> Pegadinha freq.: Letra {item.frequent_distractor.letter} ({item.frequent_distractor.count}x)
                      </span>
                    )}
                  </div>
                </div>

                {/* Botão de Treino Específico */}
                <div className="w-full md:w-auto shrink-0 flex items-center justify-end">
                  <Link
                    href={item.workout_url}
                    className="w-full md:w-auto inline-flex items-center justify-center gap-1.5 bg-foreground hover:bg-foreground/90 text-background font-bold text-xs px-4 py-2 rounded-lg transition-colors cursor-pointer"
                  >
                    Treinar Ponto Cego (10 Qs)
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
