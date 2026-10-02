"use client";

import React from "react";
import Link from "next/link";
import { Trophy, Sparkles, CheckCircle2, BookOpen } from "lucide-react";
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
  batchFlashcardsResult: { count: number } | null;
  generatingBatchFlashcards: boolean;
  onGenerateBatchFlashcards: () => void;
  onStartReview: () => void;
  initialInstitution?: string;
}

export const SimuladoResultsView: React.FC<SimuladoResultsViewProps> = ({
  resultsMap,
  queue,
  answers,
  areaSummary,
  batchFlashcardsResult,
  generatingBatchFlashcards,
  onGenerateBatchFlashcards,
  onStartReview,
  initialInstitution = "ENARE",
}) => {
  const correctCount = Object.values(resultsMap).filter(r => r.is_correct).length;
  const percentage = queue.length > 0 ? Math.round((correctCount / queue.length) * 100) : 0;
  const wrongQuestions = queue.filter(q => resultsMap[q.id] && !resultsMap[q.id].is_correct && answers[q.id]);

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

      {wrongQuestions.length > 0 && (
        <div className="w-full max-w-2xl bg-purple-500/10 border border-purple-500/25 rounded-xl p-6 mb-8 text-left animate-in slide-in-from-bottom-2">
          <div className="flex items-center gap-2 text-purple-600 font-bold text-base mb-2">
            <Sparkles size={20} />
            Revisão Ativa & Flashcards das Erradas
          </div>
          <p className="text-sm text-foreground/80 leading-relaxed mb-4">
            Você errou <strong className="text-foreground">{wrongQuestions.length}</strong> questões neste simulado. Converta seus erros em flashcards com 1 clique para praticar repetição espaçada (FSRS).
          </p>

          {batchFlashcardsResult ? (
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="flex-1 bg-success/15 border border-success/30 text-success font-semibold px-4 py-2.5 rounded-xl text-sm flex items-center gap-2">
                <CheckCircle2 size={18} /> {batchFlashcardsResult.count} flashcard(s) adicionado(s) à Revisão Ativa!
              </div>
              <Link
                href="/revisao-ativa"
                className="bg-purple-600 hover:bg-purple-700 text-white font-bold px-5 py-2.5 rounded-xl text-sm transition-all shadow-sm flex items-center gap-2 shrink-0"
              >
                <Sparkles size={16} /> Praticar Flashcards
              </Link>
            </div>
          ) : (
            <button
              onClick={onGenerateBatchFlashcards}
              disabled={generatingBatchFlashcards}
              className="w-full sm:w-auto bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-3 px-6 rounded-xl transition-all shadow-md flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer text-sm"
            >
              {generatingBatchFlashcards ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Gerando Flashcards dos seus Erros...
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  Gerar Flashcards de Todas as Erradas ({wrongQuestions.length})
                </>
              )}
            </button>
          )}
        </div>
      )}

      <button
        onClick={onStartReview}
        className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3 px-8 rounded-lg transition-all shadow-lg hover:-translate-y-0.5 flex items-center gap-2 cursor-pointer"
      >
        <BookOpen size={20} /> Iniciar Revisão Detalhada
      </button>
    </div>
  );
};
