"use client";

import React from "react";
import Link from "next/link";
import { Sparkles, Brain, Pencil, BookOpen } from "lucide-react";
import { FlashcardGenerateResponse } from "@/types/api";

export interface QuizFlashcardSectionProps {
  isWrong: boolean;
  autoGeneratingFlashcard: boolean;
  autoFsrsOnWrong: boolean;
  onToggleAutoFsrs: () => void;
  flashcardResult: FlashcardGenerateResponse | null;
  draftFlashcard: { front: string; back: string; context: string } | null;
  savingFlashcard: boolean;
  generatingFlashcard: boolean;
  onQuickSaveFlashcard: () => void;
  onGenerateFlashcard: () => void;
  onSaveFlashcard: () => void;
  onCancelDraft: () => void;
  onChangeDraft: (draft: { front: string; back: string; context: string }) => void;
  onEditSavedFlashcard: () => void;
}

export const QuizFlashcardSection: React.FC<QuizFlashcardSectionProps> = ({
  isWrong,
  autoGeneratingFlashcard,
  autoFsrsOnWrong,
  onToggleAutoFsrs,
  flashcardResult,
  draftFlashcard,
  savingFlashcard,
  generatingFlashcard,
  onQuickSaveFlashcard,
  onGenerateFlashcard,
  onSaveFlashcard,
  onCancelDraft,
  onChangeDraft,
  onEditSavedFlashcard,
}) => {
  return (
    <>
      {/* 1. Loading do Auto-FSRS em Background */}
      {isWrong && autoGeneratingFlashcard && !flashcardResult && (
        <div className="mt-6 p-4 rounded-2xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-between gap-4 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-600/20 text-purple-600 dark:text-purple-300 flex items-center justify-center shrink-0">
              <Sparkles className="animate-spin text-purple-600 dark:text-purple-300" size={18} />
            </div>
            <div>
              <div className="text-sm font-bold text-purple-700 dark:text-purple-300 flex items-center gap-1.5">
                ⚡ Auto-FSRS Ativado <span className="text-[10px] uppercase tracking-wider bg-purple-500/25 px-2 py-0.5 rounded-full font-bold">Zero Fricção</span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Extraindo Pulo do Gato com IA e agendando para a Revisão Ativa de amanhã...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Botão manual 1-Click quando não estiver gerando e não tiver resultado */}
      {isWrong && !flashcardResult && !draftFlashcard && !autoGeneratingFlashcard && (
        <div className="mt-6 p-4 rounded-2xl bg-purple-500/10 border border-purple-500/25 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in slide-in-from-bottom-2">
          <div>
            <div className="flex items-center gap-2 text-purple-700 dark:text-purple-300 font-bold text-sm">
              <Brain size={18} /> Fixe este aprendizado na memória
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Adicione um flashcard com o Pulo do Gato para revisar no momento ideal (FSRS).
            </p>
            <button
              type="button"
              onClick={onToggleAutoFsrs}
              className="mt-2 text-[11px] text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-1 cursor-pointer font-medium"
            >
              {autoFsrsOnWrong ? "⚡ Auto-FSRS ao errar: Ligado (clique para pausar)" : "⚡ Auto-FSRS ao errar: Desligado (clique para ativar)"}
            </button>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
            <button 
              onClick={onQuickSaveFlashcard}
              disabled={savingFlashcard}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-all disabled:opacity-50 cursor-pointer text-sm"
            >
              {savingFlashcard ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
              {savingFlashcard ? "Salvando..." : "Salvar Flashcard (1-Click)"}
            </button>
            <button 
              onClick={onGenerateFlashcard}
              disabled={generatingFlashcard || savingFlashcard}
              title="Personalizar texto antes de salvar"
              className="px-3 py-2.5 rounded-xl border border-purple-500/30 hover:bg-purple-500/20 text-purple-700 dark:text-purple-300 text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1"
            >
              <Pencil size={15} />
              <span className="hidden md:inline">Editar</span>
            </button>
          </div>
        </div>
      )}

      {/* 3. Editor de Rascunho de Flashcard */}
      {draftFlashcard && (
        <div className="mt-6 bg-purple-500/10 border border-purple-500/25 rounded-2xl p-5 animate-in slide-in-from-bottom-2">
          <div className="flex items-center gap-2 text-purple-700 dark:text-purple-400 font-bold text-sm mb-4">
            <Sparkles size={16} /> Editar Flashcard
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Frente</label>
              <textarea 
                value={draftFlashcard.front}
                onChange={(e) => onChangeDraft({ ...draftFlashcard, front: e.target.value })}
                className="w-full bg-background border border-border rounded-lg p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary min-h-[100px]"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Verso</label>
              <textarea 
                value={draftFlashcard.back}
                onChange={(e) => onChangeDraft({ ...draftFlashcard, back: e.target.value })}
                className="w-full bg-background border border-border rounded-lg p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary min-h-[120px]"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button 
                onClick={onCancelDraft}
                disabled={savingFlashcard}
                className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button 
                onClick={onSaveFlashcard}
                disabled={savingFlashcard}
                className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-5 rounded-lg transition-colors text-sm shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {savingFlashcard ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <BookOpen size={16} />
                )}
                Salvar Flashcard
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Feedback de Flashcard Salvo */}
      {flashcardResult && (
        <div className="mt-6 bg-purple-500/10 border border-purple-500/25 rounded-2xl p-5 animate-in slide-in-from-bottom-2">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
            <div className="flex items-center gap-2 text-purple-700 dark:text-purple-400 font-bold text-sm">
              <Sparkles size={16} /> Flashcard Salvo na Revisão Ativa!
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onEditSavedFlashcard}
                className="text-xs text-purple-700 dark:text-purple-300 hover:underline flex items-center gap-1 cursor-pointer font-medium"
                title="Editar texto gerado"
              >
                <Pencil size={13} />
                <span>Editar</span>
              </button>
              <Link 
                href="/revisao-ativa"
                className="text-xs font-bold text-purple-700 dark:text-purple-400 hover:underline flex items-center gap-1"
              >
                Ir para Revisão Ativa →
              </Link>
            </div>
          </div>
          <div className="text-foreground text-sm space-y-2">
            <div className="font-medium bg-background p-3.5 rounded-lg border border-border leading-relaxed whitespace-pre-line text-sm">
              <span className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Frente:</span>
              {flashcardResult.front}
            </div>
            {flashcardResult.back && (
              <div className="text-muted-foreground bg-background p-3.5 rounded-lg border border-border leading-relaxed whitespace-pre-line text-sm">
                <span className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">Verso:</span>
                {flashcardResult.back}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
