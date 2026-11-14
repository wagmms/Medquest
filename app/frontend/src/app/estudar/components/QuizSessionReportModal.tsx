"use client";

import React from "react";
import Link from "next/link";
import { CheckCircle2, Sparkles, BookOpen, RotateCcw, ArrowRight } from "lucide-react";

export interface QuizSessionReportModalProps {
  studyMode: "TUTOR" | "SIMULADO" | "SIMULATED";
  totalAnswered: number;
  correctCount: number;
  accuracy: number;
  wrongItems: Array<{ question_id: number; wrong_letter: string }>;
  onBackToFilters: () => void;
  onRestartSession: () => void;
}

export const QuizSessionReportModal: React.FC<QuizSessionReportModalProps> = ({
  studyMode,
  totalAnswered,
  correctCount,
  accuracy,
  wrongItems,
  onBackToFilters,
  onRestartSession,
}) => {
  return (
    <div className="bg-card border border-border shadow-1 rounded-2xl p-8 md:p-10 max-w-2xl mx-auto w-full text-center flex flex-col items-center animate-in zoom-in-95 duration-300">
      <div className="w-20 h-20 bg-success/20 text-success rounded-full flex items-center justify-center mx-auto mb-6">
        <CheckCircle2 size={40} />
      </div>
      <h2 className="text-2xl md:text-3xl font-black text-foreground mb-3 tracking-tight">
        {studyMode === "TUTOR" ? "Sessão Concluída!" : "Simulado Concluído!"}
      </h2>
      <p className="text-muted-foreground text-base md:text-lg mb-6">
        Você respondeu <strong className="text-foreground">{totalAnswered}</strong> {totalAnswered === 1 ? "questão" : "questões"} com <strong className="text-primary">{accuracy}%</strong> de acerto ({correctCount} acertos).
      </p>

      {wrongItems.length > 0 && (
        <div className="w-full bg-purple-500/10 border border-purple-500/25 rounded-2xl p-6 mb-8 text-left animate-in slide-in-from-bottom-2">
          <div className="flex items-center gap-2.5 text-purple-700 dark:text-purple-400 font-bold text-base mb-2">
            <Sparkles size={20} />
            Repetição Espaçada de Questões (FSRS)
          </div>
          <p className="text-sm text-foreground/80 leading-relaxed mb-4">
            Você errou <strong className="text-foreground">{wrongItems.length}</strong> {wrongItems.length === 1 ? "questão" : "questões"} nesta sessão. Elas foram agendadas automaticamente na sua fila de revisão FSRS para consolidar a retenção de longo prazo.
          </p>
          <Link
            href="/estudar?status=wrong&limit=20"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-bold py-2.5 px-5 rounded-xl text-sm transition-colors shadow-sm cursor-pointer"
          >
            Revisar Caderno de Erros <ArrowRight size={16} />
          </Link>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-4 w-full justify-center">
        <button
          onClick={onBackToFilters}
          className="flex-1 max-w-xs flex items-center justify-center gap-2 bg-primary text-primary-foreground font-bold py-3 px-6 rounded-xl hover:bg-primary/90 transition-colors shadow-md cursor-pointer"
        >
          <BookOpen size={18} /> Novo Bloco de Questões
        </button>
        <button
          onClick={onRestartSession}
          className="flex items-center justify-center gap-2 bg-secondary text-secondary-foreground font-semibold py-3 px-6 rounded-xl hover:bg-secondary/80 transition-colors cursor-pointer border border-border"
        >
          <RotateCcw size={18} /> Reiniciar Esta Sessão
        </button>
      </div>
    </div>
  );
};
