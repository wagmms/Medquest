"use client";

import React from "react";
import { Stethoscope, Sparkles, X } from "lucide-react";
import { FormattedContent } from "@/components/FormattedContent";

export interface PreceptorAnswer {
  answer: string;
  model: string;
  source: string;
}

export interface PreceptorSectionProps {
  preceptorResponse: PreceptorAnswer | null;
  preceptorInput: string;
  askingPreceptor: boolean;
  onChangeInput: (value: string) => void;
  onAskPreceptor: () => void;
  onClearResponse: () => void;
}

export const PreceptorSection: React.FC<PreceptorSectionProps> = ({
  preceptorResponse,
  preceptorInput,
  askingPreceptor,
  onChangeInput,
  onAskPreceptor,
  onClearResponse,
}) => {
  return (
    <div className="mt-8 bg-blue-500/5 border border-blue-500/20 rounded-2xl p-5 md:p-6">
      <h4 className="text-blue-700 dark:text-blue-400 font-bold flex items-center gap-2 mb-3 uppercase tracking-wider text-sm">
        <Stethoscope size={18} /> Perguntar ao Preceptor (IA)
      </h4>
      {!preceptorResponse ? (
        <div className="flex flex-col gap-3">
          <textarea
            className="w-full bg-background border border-border rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[80px]"
            placeholder="Ficou com alguma dúvida sobre esta questão? Pergunte ao preceptor virtual..."
            value={preceptorInput}
            onChange={(e) => onChangeInput(e.target.value)}
          />
          <div className="flex justify-end">
            <button
              onClick={onAskPreceptor}
              disabled={askingPreceptor || !preceptorInput.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-xl shadow-sm transition-all flex items-center gap-2 text-sm cursor-pointer disabled:cursor-not-allowed"
            >
              {askingPreceptor ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
              {askingPreceptor ? "Consultando..." : "Enviar Pergunta"}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="bg-background rounded-xl p-4 border border-border relative">
            <button
              onClick={onClearResponse}
              className="absolute top-2 right-2 text-muted-foreground hover:text-foreground cursor-pointer"
              title="Fechar resposta"
              aria-label="Fechar resposta"
            >
              <X size={16} />
            </button>
            <div className="text-sm md:text-base text-foreground leading-relaxed">
              <FormattedContent content={preceptorResponse.answer} />
            </div>
            <div className="mt-3 text-xs text-muted-foreground font-mono bg-muted/50 w-fit px-2 py-1 rounded">
              Respondido por: {preceptorResponse.model} ({preceptorResponse.source})
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
