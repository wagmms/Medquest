"use client";

import React, { useState, useMemo } from "react";
import { Clock, Flag } from "lucide-react";
import clsx from "clsx";
import { QuestionListItem, BatchAttemptResultItem } from "@/types/api";
import { Grid as FixedSizeGrid, CellComponentProps } from "react-window";
import { AutoSizer } from "react-virtualized-auto-sizer";

export interface SimuladoNavGridProps {
  isReview: boolean;
  resultsMap: Record<number, BatchAttemptResultItem>;
  queue: QuestionListItem[];
  answers: Record<number, string>;
  flagged: Record<number, boolean>;
  currentIndex: number;
  onNavigateTo: (index: number) => void;
  timeLeft: number;
  formatTime: (seconds: number) => string;
  showResultsSummary: boolean;
  onHideResultsSummary: () => void;
  onFinishSimulado: () => void;
}

export const SimuladoNavGrid: React.FC<SimuladoNavGridProps> = ({
  isReview,
  resultsMap,
  queue,
  answers,
  flagged,
  currentIndex,
  onNavigateTo,
  timeLeft,
  formatTime,
  showResultsSummary,
  onHideResultsSummary,
  onFinishSimulado,
}) => {
  const [sidebarFilter, setSidebarFilter] = useState<'all' | 'unanswered' | 'flagged'>('all');

  const filteredIndices = useMemo(() => {
    return queue.map((_, idx) => idx).filter(idx => {
      const q = queue[idx];
      if (sidebarFilter === 'unanswered') return !answers[q.id];
      if (sidebarFilter === 'flagged') return Boolean(flagged[q.id]);
      return true;
    });
  }, [queue, sidebarFilter, answers, flagged]);

  return (
    <div className="w-full lg:w-72 shrink-0 flex flex-col gap-4 order-1 lg:order-1 h-auto lg:h-full lg:sticky lg:top-4 z-10 bg-background/95 lg:bg-transparent backdrop-blur-md lg:backdrop-blur-none p-2 lg:p-0 rounded-xl shadow-sm lg:shadow-none mb-4 lg:mb-0 border lg:border-0 border-border">
      {/* Timer Box */}
      <div className="bg-card border border-border shadow-1 rounded-xl p-4 lg:p-5 flex flex-row lg:flex-col items-center justify-between lg:justify-center gap-2">
        {isReview ? (
          <>
            <span className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Nota Final</span>
            <div className="text-2xl lg:text-4xl font-black text-foreground">
              {Object.values(resultsMap).filter(r => r.is_correct).length} <span className="text-sm lg:text-lg text-muted-foreground">/ {queue.length}</span>
            </div>
            <div className="text-sm font-medium text-primary mt-1">
              {Math.round((Object.values(resultsMap).filter(r => r.is_correct).length / queue.length) * 100)}% de Acerto
            </div>
            {showResultsSummary && (
              <button
                onClick={onHideResultsSummary}
                className="mt-3 bg-primary text-primary-foreground font-bold px-4 py-2 rounded-lg text-sm w-full transition-colors hover:bg-primary/90 cursor-pointer"
              >
                Revisar Questões
              </button>
            )}
          </>
        ) : (
          <>
            <span className="text-sm font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <Clock size={16} /> Tempo
            </span>
            <div className={clsx(
              "text-2xl lg:text-3xl font-black font-mono",
              timeLeft < 1800 ? "text-destructive animate-pulse" : "text-foreground"
            )}>
              {formatTime(timeLeft)}
            </div>
          </>
        )}
      </div>

      {/* Grid Box */}
      <div className="bg-card border border-border shadow-1 rounded-xl flex flex-col h-[200px] lg:h-auto lg:flex-1 overflow-hidden">
        <div className="p-3 lg:p-4 border-b border-border bg-muted/30">
          <h3 className="font-bold text-foreground text-sm">Cartão Resposta</h3>
          {!isReview && (
            <p className="text-xs text-muted-foreground mt-1">
              {Object.keys(answers).length} respondidas, {queue.length - Object.keys(answers).length} em branco.
              {Object.values(flagged).filter(Boolean).length > 0 && (
                <span className="text-warning ml-1">
                  · {Object.values(flagged).filter(Boolean).length} marcada(s)
                </span>
              )}
            </p>
          )}
          {/* Filter buttons */}
          {!isReview && (
            <div className="flex gap-1.5 mt-2">
              {([
                { key: 'all' as const, label: 'Todas' },
                { key: 'unanswered' as const, label: 'Em branco' },
                { key: 'flagged' as const, label: '🚩' },
              ] as const).map(f => (
                <button
                  key={f.key}
                  onClick={() => setSidebarFilter(f.key)}
                  className={clsx(
                    "text-[10px] font-semibold px-2 py-1 rounded transition-colors cursor-pointer",
                    sidebarFilter === f.key
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex-1 overflow-hidden">
          <AutoSizer renderProp={({ height, width }) => {
              if (height === undefined || width === undefined) return null;
              const availableWidth = width;
              let columnCount = 5;
              if (availableWidth > 300) columnCount = 6;
              if (availableWidth > 400) columnCount = 8;
              if (availableWidth > 600) columnCount = 5;

              const gap = 8;
              const columnWidth = (availableWidth - gap * (columnCount - 1)) / columnCount;
              const rowHeight = columnWidth;
              const rowCount = Math.ceil(filteredIndices.length / columnCount);

              const Cell = ({ columnIndex, rowIndex, style, ariaAttributes }: CellComponentProps) => {
                const index = rowIndex * columnCount + columnIndex;
                if (index >= filteredIndices.length) return null;

                const idx = filteredIndices[index];
                const q = queue[idx];
                const isCurrent = idx === currentIndex;
                const answeredLetter = answers[q.id];
                const res = resultsMap[q.id];
                const isFlagged = flagged[q.id];

                let btnClass = "bg-muted text-muted-foreground hover:bg-muted/80";

                if (isReview) {
                  if (res?.is_correct) btnClass = "bg-success text-success-foreground font-bold";
                  else if (res && !res.is_correct) btnClass = "bg-destructive text-destructive-foreground font-bold";
                  else btnClass = "bg-card border border-dashed border-muted-foreground text-muted-foreground";
                } else {
                  if (answeredLetter) btnClass = "bg-primary/20 text-primary font-bold";
                }

                if (isCurrent) {
                  btnClass += " ring-2 ring-foreground ring-offset-2 ring-offset-background";
                }

                const cellStyle = {
                  ...style,
                  left: Number(style.left) + gap / 2,
                  top: Number(style.top) + gap / 2,
                  width: Number(style.width) - gap,
                  height: Number(style.height) - gap
                };

                return (
                  <div {...ariaAttributes} style={cellStyle}>
                    <button
                      key={q.id}
                      onClick={() => onNavigateTo(idx)}
                      aria-label={`Ir para questão ${idx + 1}${answeredLetter ? `, resposta ${answeredLetter}` : ", em branco"}${isFlagged ? ", marcada para revisão" : ""}`}
                      aria-current={isCurrent ? "step" : undefined}
                      className={clsx(
                        "w-full h-full rounded flex flex-col items-center justify-center text-xs transition-all relative cursor-pointer",
                        btnClass
                      )}
                    >
                      {isFlagged && (
                        <span className="absolute -top-0.5 -right-0.5 text-warning">
                          <Flag size={8} fill="currentColor" />
                        </span>
                      )}
                      <span className={clsx(!isReview && answeredLetter ? "text-[10px]" : "text-xs")}>{idx + 1}</span>
                      {!isReview && answeredLetter && <span className="text-[14px] leading-none">{answeredLetter}</span>}
                    </button>
                  </div>
                );
              };

              return (
                <FixedSizeGrid
                  columnCount={columnCount}
                  columnWidth={columnWidth + gap}
                  rowCount={rowCount}
                  rowHeight={rowHeight + gap}
                  cellComponent={Cell}
                  cellProps={{}}
                  style={{ overflowX: "hidden", height, width }}
                />
              );
            }} />
        </div>

        {!isReview && (
          <div className="p-3 lg:p-4 border-t border-border bg-muted/30">
            <button
              onClick={onFinishSimulado}
              className="w-full bg-foreground hover:bg-foreground/90 text-background font-bold py-2.5 lg:py-3 rounded-lg transition-colors text-sm lg:text-base cursor-pointer"
            >
              Finalizar Simulado
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
