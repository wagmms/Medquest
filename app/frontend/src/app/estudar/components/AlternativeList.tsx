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
    <div className="flex flex-col gap-2.5" role="region" aria-label="Alternativas da questão">
      {alternatives.map((alt) => {
        const isSelected = selectedLetter === alt.letter;
        const isCorrect =
          attemptResult?.correct_letter === alt.letter ||
          (attemptResult && isSelected && attemptResult.is_correct);
        const isWrong = attemptResult && isSelected && !attemptResult.is_correct;
        const isEliminated = eliminatedLetters.includes(alt.letter);

        let altClass =
          "bg-surface border-line-subtle hover:bg-elevated/50 hover:border-line-strong cursor-pointer shadow-xs";
        if (isSelected && !attemptResult) {
          altClass = "bg-accent/10 border-accent text-ink cursor-pointer shadow-xs ring-1 ring-accent/30";
        }
        if (isEliminated && !attemptResult && !isSelected) {
          altClass = "bg-canvas/40 border-line-subtle/50 opacity-50 hover:opacity-80 cursor-pointer shadow-none";
        }
        if (attemptResult) {
          if (isCorrect) {
            altClass = "bg-normal/10 border-normal/50 text-ink shadow-xs cursor-default ring-1 ring-normal/30";
          } else if (isWrong) {
            altClass = "bg-critical/10 border-critical/50 text-ink shadow-xs cursor-default ring-1 ring-critical/30";
          } else {
            altClass = "bg-surface border-line-subtle opacity-40 cursor-default";
          }
        }

        const altAriaStatus = [
          isEliminated ? "riscada" : "",
          isSelected ? "selecionada" : "",
          attemptResult && isCorrect ? "gabarito correto" : "",
          attemptResult && isWrong ? "resposta incorreta" : "",
        ].filter(Boolean).join(", ");

        const altAriaLabel = `Alternativa ${alt.letter}: ${alt.text.replace(/\s+/g, " ").trim()}${altAriaStatus ? ` (${altAriaStatus})` : ""}`;

        return (
          <motion.div
            role="button"
            tabIndex={attemptResult || submitting ? -1 : 0}
            whileTap={!attemptResult && !submitting ? { scale: 0.995 } : {}}
            animate={
              attemptResult && isWrong
                ? { x: [-3, 3, -3, 3, 0], transition: { duration: 0.3 } }
                : attemptResult && isCorrect
                ? { scale: [1, 1.01, 1], transition: { duration: 0.3 } }
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
              "group relative text-left p-3 sm:p-3.5 rounded-sm border transition-all flex items-start gap-2.5 sm:gap-3 w-full focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent select-none",
              altClass
            )}
            aria-label={altAriaLabel}
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
                  "w-6 h-7 shrink-0 flex items-center justify-center rounded-xs transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent",
                  isEliminated
                    ? "opacity-100 text-critical hover:scale-105"
                    : "opacity-0 group-hover:opacity-70 hover:opacity-100 hover:text-accent max-md:opacity-40 text-ink-muted"
                )}
              >
                <Scissors
                  size={14}
                  aria-hidden="true"
                  className={clsx("transition-transform duration-150", isEliminated && "rotate-45")}
                />
              </button>
            ) : (
              <div className="w-6 h-7 shrink-0 flex items-center justify-center text-ink-muted/30" aria-hidden="true">
                {isEliminated && !isCorrect && (
                  <Scissors size={12} aria-hidden="true" className="opacity-40 rotate-45 text-critical" />
                )}
              </div>
            )}

            {/* Badge da Letra */}
            <div
              aria-hidden="true"
              className={clsx(
                "w-7 h-7 shrink-0 flex items-center justify-center rounded-xs font-mono-lab font-bold text-xs transition-colors border",
                isSelected && !attemptResult
                  ? "bg-accent text-white border-accent"
                  : isCorrect
                  ? "bg-normal text-white border-normal"
                  : isWrong
                  ? "bg-critical text-white border-critical"
                  : isEliminated && !attemptResult
                  ? "bg-canvas text-ink-muted/50 border-line-subtle/50"
                  : "bg-canvas text-ink-muted border-line-subtle"
              )}
            >
              {submitting && isSelected ? (
                <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                alt.letter
              )}
            </div>

            {/* Texto da Alternativa */}
            <div
              aria-hidden="true"
              className={clsx(
                "pt-0.5 text-ink leading-relaxed flex-1 text-sm md:text-base transition-all",
                isEliminated && !isCorrect && "line-through text-ink-muted/70 decoration-ink-muted/50"
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
