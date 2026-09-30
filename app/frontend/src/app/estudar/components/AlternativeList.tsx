"use client";

import React from "react";
import { motion } from "framer-motion";
import { Scissors } from "lucide-react";
import clsx from "clsx";
import { AttemptResult } from "@/types/api";

export interface AlternativeItem {
  letter: string;
  text: string;
  is_correct?: boolean;
}

export interface AlternativeListProps {
  alternatives: AlternativeItem[];
  selectedLetter: string | null;
  attemptResult: AttemptResult | null;
  eliminatedLetters: string[];
  submitting: boolean;
  onSelectAlternative: (letter: string) => void;
  onToggleEliminate: (letter: string) => void;
}

export const AlternativeList: React.FC<AlternativeListProps> = ({
  alternatives,
  selectedLetter,
  attemptResult,
  eliminatedLetters,
  submitting,
  onSelectAlternative,
  onToggleEliminate,
}) => {
  return (
    <div className="flex flex-col gap-3">
      {alternatives.map((alt) => {
        const isSelected = selectedLetter === alt.letter;
        const isCorrect =
          attemptResult?.correct_letter === alt.letter ||
          (attemptResult && isSelected && attemptResult.is_correct);
        const isWrong = attemptResult && isSelected && !attemptResult.is_correct;
        const isEliminated = eliminatedLetters.includes(alt.letter);

        let altClass =
          "bg-card border-border hover:bg-muted/50 hover:border-primary/30 cursor-pointer shadow-sm hover:shadow";
        if (isSelected && !attemptResult) {
          altClass = "bg-primary/5 border-primary/50 cursor-pointer shadow ring-1 ring-primary/20";
        }
        if (isEliminated && !attemptResult && !isSelected) {
          altClass = "bg-muted/20 border-border/60 opacity-60 hover:opacity-85 cursor-pointer shadow-none";
        }
        if (attemptResult) {
          if (isCorrect) {
            altClass = "bg-success/10 border-success/50 shadow-sm cursor-default ring-1 ring-success/20";
          } else if (isWrong) {
            altClass = "bg-destructive/10 border-destructive/50 shadow-sm cursor-default ring-1 ring-destructive/20";
          } else {
            altClass = "bg-card border-border opacity-40 cursor-default";
          }
        }

        return (
          <motion.div
            role="button"
            tabIndex={attemptResult || submitting ? -1 : 0}
            whileTap={!attemptResult && !submitting ? { scale: 0.99 } : {}}
            animate={
              attemptResult && isWrong
                ? { x: [-5, 5, -5, 5, 0], transition: { duration: 0.4 } }
                : attemptResult && isCorrect
                ? { scale: [1, 1.02, 1], transition: { duration: 0.4 } }
                : {}
            }
            key={alt.letter}
            onClick={() => onSelectAlternative(alt.letter)}
            onKeyDown={(e) => {
              if (attemptResult || submitting) return;
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelectAlternative(alt.letter);
              }
            }}
            onContextMenu={(e) => {
              if (!attemptResult && !submitting) {
                e.preventDefault();
                onToggleEliminate(alt.letter);
              }
            }}
            className={clsx(
              "group relative text-left p-3.5 sm:p-4 rounded-xl border transition-all flex items-start gap-2.5 sm:gap-3 w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 select-none",
              altClass
            )}
            aria-pressed={isSelected}
            aria-disabled={!!attemptResult || submitting}
          >
            {/* Botão de Risco / Tesoura */}
            {!attemptResult ? (
              <button
                type="button"
                title={
                  isEliminated
                    ? `Restaurar alternativa ${alt.letter}`
                    : `Riscar alternativa ${alt.letter} (Shift+${alt.letter} ou botão direito)`
                }
                aria-label={
                  isEliminated
                    ? `Restaurar alternativa ${alt.letter}`
                    : `Riscar alternativa ${alt.letter}`
                }
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleEliminate(alt.letter);
                }}
                disabled={submitting}
                className={clsx(
                  "w-6 h-8 shrink-0 flex items-center justify-center rounded-md transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary",
                  isEliminated
                    ? "opacity-100 text-destructive hover:scale-110"
                    : "opacity-0 group-hover:opacity-80 hover:opacity-100 hover:text-primary max-md:opacity-40 text-muted-foreground"
                )}
              >
                <Scissors
                  size={15}
                  className={clsx("transition-transform duration-150", isEliminated && "rotate-45")}
                />
              </button>
            ) : (
              <div className="w-6 h-8 shrink-0 flex items-center justify-center text-muted-foreground/40">
                {isEliminated && !isCorrect && (
                  <Scissors size={13} className="opacity-40 rotate-45 text-destructive" />
                )}
              </div>
            )}

            {/* Badge da Letra */}
            <div
              className={clsx(
                "w-8 h-8 shrink-0 flex items-center justify-center rounded-lg font-bold text-sm transition-colors",
                isSelected && !attemptResult
                  ? "bg-primary text-primary-foreground"
                  : isCorrect
                  ? "bg-success text-success-foreground"
                  : isWrong
                  ? "bg-destructive text-destructive-foreground"
                  : isEliminated && !attemptResult
                  ? "bg-muted/40 text-muted-foreground/60 border border-border/50"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {submitting && isSelected ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                alt.letter
              )}
            </div>

            {/* Texto da Alternativa */}
            <div
              className={clsx(
                "pt-1 text-foreground leading-relaxed flex-1 transition-all",
                isEliminated && !isCorrect && "line-through text-muted-foreground/75 decoration-muted-foreground/60"
              )}
            >
              {alt.text}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
};
