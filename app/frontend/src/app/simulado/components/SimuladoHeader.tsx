"use client";

import React from "react";
import { ChevronLeft, ChevronRight, Flag } from "lucide-react";
import clsx from "clsx";

export interface SimuladoHeaderProps {
  currentIndex: number;
  totalCount: number;
  answeredCount: number;
  isReview: boolean;
  isFlagged: boolean;
  onToggleFlag: () => void;
  onNavigatePrev: () => void;
  onNavigateNext: () => void;
}

export const SimuladoHeader: React.FC<SimuladoHeaderProps> = ({
  currentIndex,
  totalCount,
  answeredCount,
  isReview,
  isFlagged,
  onToggleFlag,
  onNavigatePrev,
  onNavigateNext,
}) => {
  const progressPercent = totalCount > 0 ? (answeredCount / totalCount) * 100 : 0;

  return (
    <>
      <div className="flex items-center justify-between bg-card border border-border shadow-sm rounded-xl p-3 shrink-0 relative overflow-hidden">
        <div
          className="absolute bottom-0 left-0 h-1 bg-primary transition-all duration-300 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
        <button
          type="button"
          onClick={onNavigatePrev}
          disabled={currentIndex === 0}
          className="flex items-center gap-1 px-3 py-1.5 rounded hover:bg-muted disabled:opacity-50 text-sm font-medium z-10 cursor-pointer disabled:cursor-not-allowed"
        >
          <ChevronLeft size={16} /> Anterior
        </button>
        <div className="flex items-center gap-2 z-10">
          <span className="font-bold text-foreground">
            Questão {currentIndex + 1} de {totalCount}
          </span>
          {!isReview && (
            <button
              type="button"
              onClick={onToggleFlag}
              className={clsx(
                "p-1.5 rounded transition-colors cursor-pointer",
                isFlagged
                  ? "text-warning bg-warning/10"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
              title={isFlagged ? "Desmarcar revisão" : "Marcar para revisar"}
            >
              <Flag size={16} fill={isFlagged ? "currentColor" : "none"} />
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={onNavigateNext}
          disabled={currentIndex === totalCount - 1}
          className="flex items-center gap-1 px-3 py-1.5 rounded hover:bg-muted disabled:opacity-50 text-sm font-medium z-10 cursor-pointer disabled:cursor-not-allowed"
        >
          Próxima <ChevronRight size={16} />
        </button>
      </div>

      <div className="hidden xl:flex items-center justify-center gap-2 px-3 py-1 bg-muted/50 rounded-full text-xs text-muted-foreground font-medium self-center">
        <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">A-E</kbd> ou <kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">1-5</kbd> Selecionar</span>
        <span className="w-1 h-1 rounded-full bg-border" />
        <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">Shift+A-E</kbd> ou ✂️ Riscar</span>
        <span className="w-1 h-1 rounded-full bg-border" />
        <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">F</kbd> Marcar p/ Revisão</span>
        <span className="w-1 h-1 rounded-full bg-border" />
        <span className="flex items-center gap-1"><kbd className="bg-background border border-border px-1.5 py-0.5 rounded text-[10px]">➔</kbd> Navegar</span>
      </div>
    </>
  );
};
