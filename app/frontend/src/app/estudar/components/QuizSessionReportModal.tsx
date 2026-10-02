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
  generatingBatchFlashcards: boolean;
  batchFlashcardsResult: { count: number } | null;
  onGenerateBatchFlashcards: () => void;
  onBackToFilters: () => void;
  onRestartSession: () => void;
}

export const QuizSessionReportModal: React.FC<QuizSessionReportModalProps> = ({
  studyMode,
  totalAnswered,
  correctCount,
  accuracy,
  wrongItems,
  generatingBatchFlashcards,
  batchFlashcardsResult,
  onGenerateBatchFlashcards,
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
        Você respondeu <strong className="text-foreground">{totalAnswered}</strong> {totalAnswered === 1 ? 'questão' : 'questões'} com <strong className="text-primary">{accuracy}%</strong> de acerto ({correctCount} acertos).
      </p>

      {wrongItems.length > 0 && (
        <div className="w-full bg-purple-500/10 border border-purple-500/25 rounded-2xl p-6 mb-8 text-left animate-in slide-in-from-bottom-2">
          <div className="flex items-center gap-2.5 text-purple-700 dark:text-purple-400 font-bold text-base mb-2">
            <Sparkles size={20} />
            Revisão Ativa & Repetição Espaçada (FSRS)
          </div>
          <p className="text-sm text-foreground/80 leading-relaxed mb-5">
            Você errou <strong className="text-foreground">{wrongItems.length}</strong> {wrongItems.length === 1 ? 'questão' : 'questões'} nesta sessão. Transforme seus erros em flashcards com 1 clique para consolidar a memória e não esquecer mais.
          </p>
          
          {batchFlashcardsResult ? (
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="flex-1 bg-success/15 border border-success/30 text-success font-semibold px-4 py-2.5 rounded-xl text-sm flex items-center gap-2">
                <CheckCircle2 size={18} /> {batchFlashcardsResult.count} flashcard(s) adicionado(s) à Revisão Ativa!
              </div>
              <Link 
                href="/revisao-ativa"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-bold py-2.5 px-5 rounded-xl text-sm transition-colors shadow-sm cursor-pointer"
              >
                Praticar Revisão <ArrowRight size={16} />
              </Link>
            </div>
          ) : (
            <button
              onClick={onGenerateBatchFlashcards}
              disabled={generatingBatchFlashcards}
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-3 px-6 rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 text-sm md:text-base"
            >
              {generatingBatchFlashcards ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Gerando Flashcards com IA...</span>
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Gerar Flashcards de Todos os Meus Erros ({wrongItems.length})</span>
                </>
              )}
            </button>
          )}
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
