import React from "react";
import { CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";

export interface DiscursiveAssessmentSectionProps {
  onReviewFSRS: (confidence: "certeza" | "duvida" | "chutei", isCorrect: boolean) => void;
}

export const DiscursiveAssessmentSection: React.FC<DiscursiveAssessmentSectionProps> = ({
  onReviewFSRS,
}) => {
  return (
    <div className="pt-4 border-t border-line-subtle flex flex-col gap-3.5 animate-in fade-in slide-in-from-bottom-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <ClinicalIcon name="notes" size={16} className="text-accent" />
          <span className="text-xs font-bold text-ink uppercase tracking-wider font-mono-lab">
            Autoavaliação da Resposta Discursiva
          </span>
        </div>
        <span className="text-[11px] text-ink-muted">
          Compare sua hipótese com o padrão acima e declare:
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-0.5">
        {/* Acertei */}
        <div className="bg-normal/5 border border-normal/25 rounded-sm p-3.5 flex flex-col gap-2.5">
          <div className="flex items-center gap-2 font-bold text-normal text-xs uppercase tracking-wider font-mono-lab">
            <CheckCircle2 size={16} /> Acertei a Questão
          </div>
          <div className="flex flex-col gap-1.5">
            <button
              type="button"
              onClick={() => onReviewFSRS("certeza", true)}
              className="w-full text-left bg-surface hover:bg-normal/10 border border-line-subtle hover:border-normal/40 text-ink font-semibold px-3 py-2 rounded-xs text-xs flex items-center justify-between transition-colors shadow-xs cursor-pointer font-mono-lab"
            >
              <span>🎯 Domino o Conteúdo</span>
              <span className="text-[10px] text-normal bg-normal/10 px-1.5 py-0.5 rounded-xs font-normal">+76 dias • [3]</span>
            </button>
            <button
              type="button"
              onClick={() => onReviewFSRS("duvida", true)}
              className="w-full text-left bg-surface hover:bg-normal/10 border border-line-subtle hover:border-normal/40 text-ink font-semibold px-3 py-2 rounded-xs text-xs flex items-center justify-between transition-colors shadow-xs cursor-pointer font-mono-lab"
            >
              <span>👍 Com Esforço</span>
              <span className="text-[10px] text-accent bg-accent/10 px-1.5 py-0.5 rounded-xs font-normal">+34 dias • [2]</span>
            </button>
            <button
              type="button"
              onClick={() => onReviewFSRS("chutei", true)}
              className="w-full text-left bg-surface hover:bg-normal/10 border border-line-subtle hover:border-normal/40 text-ink font-semibold px-3 py-2 rounded-xs text-xs flex items-center justify-between transition-colors shadow-xs cursor-pointer font-mono-lab"
            >
              <span>🎲 Chutei / Inseguro</span>
              <span className="text-[10px] text-ink-muted bg-canvas px-1.5 py-0.5 rounded-xs font-normal">+15 dias • [1]</span>
            </button>
          </div>
        </div>

        {/* Errei */}
        <div className="bg-critical/5 border border-critical/25 rounded-sm p-3.5 flex flex-col gap-2.5">
          <div className="flex items-center gap-2 font-bold text-critical text-xs uppercase tracking-wider font-mono-lab">
            <XCircle size={16} /> Errei a Questão
          </div>
          <div className="flex flex-col gap-1.5">
            <button
              type="button"
              onClick={() => onReviewFSRS("duvida", false)}
              className="w-full text-left bg-surface hover:bg-critical/10 border border-line-subtle hover:border-critical/40 text-ink font-semibold px-3 py-2 rounded-xs text-xs flex items-center justify-between transition-colors shadow-xs cursor-pointer font-mono-lab"
            >
              <span className="flex items-center gap-1.5">
                <RotateCcw size={13} className="text-critical" />
                <span>Revisar na Próxima Semana</span>
              </span>
              <span className="text-[10px] text-critical bg-critical/10 px-1.5 py-0.5 rounded-xs font-normal">D+7 • [E]</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
