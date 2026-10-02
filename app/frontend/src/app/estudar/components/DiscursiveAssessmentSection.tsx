"use client";

import React from "react";
import { CheckCircle2, XCircle, RotateCcw } from "lucide-react";

export interface DiscursiveAssessmentSectionProps {
  onReviewFSRS: (confidence: "certeza" | "duvida" | "chutei", isCorrect: boolean) => void;
}

export const DiscursiveAssessmentSection: React.FC<DiscursiveAssessmentSectionProps> = ({
  onReviewFSRS,
}) => {
  return (
    <div className="mt-8 pt-6 border-t border-border flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[20px]">how_to_reg</span>
          <span className="text-base font-bold text-foreground">
            Autoavaliação da Resposta Discursiva
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          Compare sua hipótese com o padrão acima e declare:
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-1">
        {/* Acertei */}
        <div className="bg-success/5 border border-success/30 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 font-bold text-success text-sm">
            <CheckCircle2 size={18} /> Acertei a Questão
          </div>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => onReviewFSRS("certeza", true)}
              className="w-full text-left bg-card hover:bg-success/15 border border-success/30 hover:border-success text-foreground font-semibold px-3.5 py-2.5 rounded-lg text-xs flex items-center justify-between transition-colors shadow-sm cursor-pointer"
            >
              <span>🎯 Domino o Conteúdo</span>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded font-normal">+76 dias • Atalho: 3</span>
            </button>
            <button
              type="button"
              onClick={() => onReviewFSRS("duvida", true)}
              className="w-full text-left bg-card hover:bg-success/15 border border-success/30 hover:border-success text-foreground font-semibold px-3.5 py-2.5 rounded-lg text-xs flex items-center justify-between transition-colors shadow-sm cursor-pointer"
            >
              <span>👍 Acertei com Esforço</span>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded font-normal">+34 dias • Atalho: 2</span>
            </button>
            <button
              type="button"
              onClick={() => onReviewFSRS("chutei", true)}
              className="w-full text-left bg-card hover:bg-success/15 border border-success/30 hover:border-success text-foreground font-semibold px-3.5 py-2.5 rounded-lg text-xs flex items-center justify-between transition-colors shadow-sm cursor-pointer"
            >
              <span>🎲 Chutei / Inseguro</span>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded font-normal">+15 dias • Atalho: 1</span>
            </button>
          </div>
        </div>

        {/* Errei */}
        <div className="bg-destructive/5 border border-destructive/30 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 font-bold text-destructive text-sm">
            <XCircle size={18} /> Errei a Questão
          </div>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => onReviewFSRS("duvida", false)}
              className="w-full text-left bg-card hover:bg-destructive/15 border border-destructive/30 hover:border-destructive text-foreground font-semibold px-3.5 py-2.5 rounded-lg text-xs flex items-center justify-between transition-colors shadow-sm cursor-pointer"
            >
              <span className="flex items-center gap-1.5">
                <RotateCcw size={14} />
                <span>Revisar na Próxima Semana</span>
              </span>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded font-normal">em 7 dias • Atalho: E</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
