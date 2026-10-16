"use client";

import React from "react";
import clsx from "clsx";
import { QuizTimer, QuizTimerHandle } from "@/components/QuizTimer";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";

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
    <header className="flex flex-wrap items-center justify-between gap-3 bg-surface/90 backdrop-blur-md border border-line-subtle rounded-sm px-4 py-2.5 shadow-xs">
      <div className="flex items-center gap-3">
        <button 
          onClick={onBackToFilters}
          className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted hover:text-ink transition-colors cursor-pointer min-h-[36px] px-2.5 -ml-1 rounded-sm hover:bg-elevated/60 border border-transparent hover:border-line-subtle focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        >
          <ClinicalIcon name="arrowLeft" size={14} />
          <span>Filtros</span>
        </button>
        <div className="h-4 w-px bg-line-subtle hidden sm:block" />
        <div className="text-xs font-semibold text-ink flex items-center gap-2" aria-live="polite">
          <span className="text-ink-muted uppercase text-[10px] tracking-wider hidden sm:inline">Progresso:</span>
          <span className="font-mono-lab tabular-nums bg-canvas px-2 py-0.5 rounded-xs border border-line-subtle text-accent font-bold">
            {completedCount} / {totalCount}
          </span>
        </div>
        <div className="hidden xl:flex items-center gap-2 ml-3 px-2.5 py-1 bg-canvas/70 border border-line-subtle rounded-xs text-[11px] text-ink-muted font-mono-lab">
          <span className="flex items-center gap-1"><kbd className="bg-surface border border-line-subtle px-1 py-0.2 rounded-xs text-[10px] text-ink">A-E</kbd> Selecionar</span>
          <span className="w-1 h-1 rounded-full bg-line-subtle" />
          <span className="flex items-center gap-1"><kbd className="bg-surface border border-line-subtle px-1 py-0.2 rounded-xs text-[10px] text-ink">Shift+A-E</kbd> Riscar</span>
          <span className="w-1 h-1 rounded-full bg-line-subtle" />
          <span className="flex items-center gap-1"><kbd className="bg-surface border border-line-subtle px-1 py-0.2 rounded-xs text-[10px] text-ink">Enter</kbd> Confirmar</span>
          <span className="w-1 h-1 rounded-full bg-line-subtle" />
          <span className="flex items-center gap-1"><kbd className="bg-surface border border-line-subtle px-1 py-0.2 rounded-xs text-[10px] text-ink">Z</kbd> Modo Zen</span>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <button 
          type="button"
          onClick={onRequestFinish}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/10 hover:bg-accent/20 text-accent border border-accent/30 rounded-sm transition-colors text-xs font-bold cursor-pointer shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          title="Finalizar sessão agora e ver seu desempenho"
        >
          <ClinicalIcon name="checkCircle" size={13} />
          <span className="hidden sm:inline">Finalizar Sessão</span>
          <span className="sm:hidden">Finalizar</span>
        </button>

        <button 
          onClick={onToggleZenMode}
          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-surface hover:bg-elevated text-ink-muted hover:text-ink rounded-sm transition-colors border border-line-subtle text-xs font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          title={zenMode ? "Sair do Modo Zen (Tecla Z)" : "Entrar no Modo Zen - Foco Clínico Máximo (Tecla Z)"}
          aria-label={zenMode ? "Sair do Modo Zen" : "Entrar no Modo Zen"}
        >
          {zenMode ? (
            <>
              <ClinicalIcon name="minimize" size={13} /> <span className="hidden md:inline">Sair Zen</span>
            </>
          ) : (
            <>
              <ClinicalIcon name="maximize" size={13} /> <span className="hidden md:inline">Modo Zen</span>
            </>
          )}
        </button>
        <div className="px-2 py-1 bg-canvas border border-line-subtle rounded-xs">
          <QuizTimer 
            ref={quizTimerRef}
            isRunning={isTimerRunning}
            initialTime={initialTime}
            className="text-xs font-mono-lab tabular-nums font-semibold w-14 text-ink-muted"
          />
        </div>
        {hasQuestion && onToggleFavorite && (
          <button 
            onClick={onToggleFavorite}
            className={clsx(
              "w-8 h-8 flex items-center justify-center rounded-sm transition-colors border cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent", 
              isFavorite 
                ? "bg-critical/10 text-critical border-critical/30" 
                : "bg-surface text-ink-muted hover:text-ink hover:bg-elevated border-line-subtle"
            )}
            title={isFavorite ? "Remover dos Favoritos" : "Favoritar Questão"}
            aria-label={isFavorite ? "Remover dos Favoritos" : "Adicionar aos Favoritos"}
            aria-pressed={isFavorite}
          >
            <ClinicalIcon 
              name="bookmark" 
              size={14} 
              className={isFavorite ? "fill-critical text-critical" : ""} 
            />
          </button>
        )}
      </div>
    </header>
  );
};
