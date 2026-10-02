"use client";

import React from "react";
import { CheckCircle2, Maximize, Minimize, Heart } from "lucide-react";
import clsx from "clsx";
import { QuizTimer, QuizTimerHandle } from "@/components/QuizTimer";

export interface QuizHeaderProps {
  onBackToFilters: () => void;
  completedCount: number;
  totalCount: number;
  onRequestFinish: () => void;
  zenMode: boolean;
  onToggleZenMode: () => void;
  quizTimerRef: React.RefObject<QuizTimerHandle | null>;
  isTimerRunning: boolean;
  initialTime: number;
  hasQuestion: boolean;
  isFavorite?: boolean;
  onToggleFavorite?: () => void;
}

export const QuizHeader: React.FC<QuizHeaderProps> = ({
  onBackToFilters,
  completedCount,
  totalCount,
  onRequestFinish,
  zenMode,
  onToggleZenMode,
  quizTimerRef,
  isTimerRunning,
  initialTime,
  hasQuestion,
  isFavorite = false,
  onToggleFavorite,
}) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 bg-card border border-border shadow-1 rounded-xl p-4">
      <div className="flex items-center gap-4">
        <button 
          onClick={onBackToFilters}
          className="flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer min-h-[44px] px-2 -ml-2 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          ← Voltar
        </button>
        <div className="h-6 w-px bg-border hidden sm:block" />
        <div className="text-sm font-semibold text-foreground" aria-live="polite">
          Respondidas {completedCount}/{totalCount}
        </div>
        <div className="hidden xl:flex items-center gap-2 ml-4 px-3 py-1 bg-muted/50 rounded-full text-xs text-muted-foreground font-medium">
          <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">A-E</kbd> ou <kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">1-5</kbd> Alternativas</span>
          <span className="w-1 h-1 rounded-full bg-border" />
          <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">Shift+A-E</kbd> ou ✂️ Riscar</span>
          <span className="w-1 h-1 rounded-full bg-border" />
          <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">Enter</kbd> Confirmar</span>
          <span className="w-1 h-1 rounded-full bg-border" />
          <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">Ctrl + ➔</kbd> Navegar</span>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        <button 
          type="button"
          onClick={onRequestFinish}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 rounded-lg transition-colors text-xs font-bold cursor-pointer shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          title="Finalizar sessão agora e ver seu desempenho"
        >
          <CheckCircle2 size={15} />
          <span className="hidden sm:inline">Finalizar Sessão</span>
          <span className="sm:hidden">Finalizar</span>
        </button>

        <button 
          onClick={onToggleZenMode}
          className="flex items-center gap-2 px-3 py-1.5 bg-muted hover:bg-muted/80 text-muted-foreground rounded-lg transition-colors border border-border text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          title={zenMode ? "Sair do Modo Zen" : "Entrar no Modo Zen (Foco Absoluto)"}
          aria-label={zenMode ? "Sair do Modo Zen" : "Entrar no Modo Zen"}
        >
          {zenMode ? (
            <>
              <Minimize size={14} /> Sair do Modo Zen
            </>
          ) : (
            <>
              <Maximize size={14} /> Modo Zen
            </>
          )}
        </button>
        <QuizTimer 
          ref={quizTimerRef}
          isRunning={isTimerRunning}
          initialTime={initialTime}
          className="text-sm font-medium w-16 text-muted-foreground"
        />
        {hasQuestion && onToggleFavorite && (
          <button 
            onClick={onToggleFavorite}
            className={clsx(
              "p-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-background cursor-pointer", 
              isFavorite ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            )}
            title={isFavorite ? "Remover dos Favoritos" : "Favoritar"}
            aria-label={isFavorite ? "Remover dos Favoritos" : "Adicionar aos Favoritos"}
            aria-pressed={isFavorite}
          >
            <Heart size={18} fill={isFavorite ? "currentColor" : "none"} aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
};
