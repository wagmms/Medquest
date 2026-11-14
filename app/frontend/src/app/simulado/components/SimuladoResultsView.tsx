"use client";

import React from "react";
import { Trophy, BookOpen } from "lucide-react";
import clsx from "clsx";
import { QuestionListItem, BatchAttemptResultItem } from "@/types/api";
import { SimuladoTriScorecard } from "./SimuladoTriScorecard";

export interface AreaSummaryRow {
  area: string;
  correct: number;
  total: number;
}

export interface SimuladoResultsViewProps {
  resultsMap: Record<number, BatchAttemptResultItem>;
  queue: QuestionListItem[];
  answers: Record<number, string>;
  areaSummary: AreaSummaryRow[];
  onStartReview: () => void;
  initialInstitution?: string;
}

export const SimuladoResultsView: React.FC<SimuladoResultsViewProps> = ({
  resultsMap,
  queue,
  areaSummary,
  onStartReview,
  initialInstitution = "ENARE",
}) => {
  const correctCount = Object.values(resultsMap).filter(r => r.is_correct).length;
  const percentage = queue.length > 0 ? Math.round((correctCount / queue.length) * 100) : 0;

  return (
    <div className="bg-card border border-border shadow-1 rounded-xl p-8 flex-1 flex flex-col items-center justify-center animate-in zoom-in-95 duration-500 overflow-y-auto">
      <div className="w-24 h-24 bg-success/20 text-success rounded-full flex items-center justify-center mb-6">
        <Trophy size={48} className="text-success" />
      </div>
      <h2 className="text-3xl font-black text-foreground mb-2">Simulado Finalizado!</h2>
      <p className="text-muted-foreground text-lg mb-8 text-center max-w-md">
        Você acertou <strong className="text-foreground">{correctCount}</strong> de <strong className="text-foreground">{queue.length}</strong> questões.
        O que representa um desempenho de <strong className="text-primary">{percentage}%</strong>.
      </p>

      <div className="w-full max-w-3xl bg-muted/30 rounded-xl p-6 border border-border mb-8">
        <h3 className="text-lg font-bold text-foreground mb-4">Desempenho por Área</h3>
        <div className="flex flex-col gap-4">
          {areaSummary.map(row => {
            const rowPct = row.total > 0 ? Math.round((row.correct / row.total) * 100) : 0;
            return (
              <div key={row.area}>
                <div className="flex justify-between text-sm font-medium mb-1">
                  <span>{row.area}</span>
                  <span className="text-muted-foreground">{row.correct} / {row.total} ({rowPct}%)</span>
                </div>
                <div className="w-full bg-border h-2 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      "h-full rounded-full transition-all duration-500",
                      rowPct >= 80 ? "bg-success" : rowPct >= 60 ? "bg-warning" : "bg-destructive"
                    )}
                    style={{ width: `${rowPct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Scorecard TRI & Termômetro de Corte */}
      <SimuladoTriScorecard
        queue={queue}
        resultsMap={resultsMap}
        initialInstitution={initialInstitution}
      />

      <button
        onClick={onStartReview}
        className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3 px-8 rounded-lg transition-all shadow-lg hover:-translate-y-0.5 flex items-center gap-2 cursor-pointer"
      >
        <BookOpen size={20} /> Iniciar Revisão Detalhada
      </button>
    </div>
  );
};
