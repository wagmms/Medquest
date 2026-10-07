"use client";

import React, { useState } from "react";
import { OfficialExam, OfficialExamEdition } from "@/types/api";
import { Play, Download, Clock, BookOpen, Sparkles, Building2, Layers } from "lucide-react";
import clsx from "clsx";

interface SimuladoOfficialExamsProps {
  exams: OfficialExam[];
  isLoading: boolean;
  onStartExam: (institution: string, year: number, durationMinutes: number, questionsCount: number) => void;
  onDownloadExam?: (institution: string, year: number, durationMinutes: number, questionsCount: number) => void;
  isOffline: boolean;
  isDownloading: boolean;
}

const INSTITUTION_STYLING: Record<string, { bg: string; border: string; text: string; badge: string; desc: string }> = {
  "USP-SP": {
    bg: "from-blue-500/10 via-blue-500/5 to-transparent",
    border: "border-blue-500/30",
    text: "text-blue-600 dark:text-blue-400",
    badge: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30",
    desc: "120 questões · Prova longa com enunciados complexos e raciocínio fisiopatológico aprofundado.",
  },
  "USP-RP": {
    bg: "from-indigo-500/10 via-indigo-500/5 to-transparent",
    border: "border-indigo-500/30",
    text: "text-indigo-600 dark:text-indigo-400",
    badge: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-500/30",
    desc: "100 questões · Casos clínicos minuciosos, condutas práticas e forte apelo propedêutico.",
  },
  "UNICAMP": {
    bg: "from-rose-500/10 via-rose-500/5 to-transparent",
    border: "border-rose-500/30",
    text: "text-rose-600 dark:text-rose-400",
    badge: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30",
    desc: "80-100 questões · Casos clínicos integrados, interpretação de imagens e saúde pública contemporânea.",
  },
  "UNIFESP": {
    bg: "from-cyan-500/10 via-cyan-500/5 to-transparent",
    border: "border-cyan-500/30",
    text: "text-cyan-600 dark:text-cyan-400",
    badge: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border-cyan-500/30",
    desc: "100 questões · Tradicional Escola Paulista: propedêutica refinada e raciocínio semiológico estrito.",
  },
  "SUS-SP": {
    bg: "from-emerald-500/10 via-emerald-500/5 to-transparent",
    border: "border-emerald-500/30",
    text: "text-emerald-600 dark:text-emerald-400",
    badge: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
    desc: "100 questões · Maior processo seletivo do país: foco em condutas de emergência, APS e protocolos do SUS.",
  },
};

export const SimuladoOfficialExams: React.FC<SimuladoOfficialExamsProps> = ({
  exams,
  isLoading,
  onStartExam,
  onDownloadExam,
  isOffline,
  isDownloading,
}) => {
  const [selectedInst, setSelectedInst] = useState<string>("USP-SP");

  const currentExam = exams.find((e) => e.institution_code === selectedInst) || exams[0];
  const styling = INSTITUTION_STYLING[selectedInst] || INSTITUTION_STYLING["USP-SP"];

  return (
    <div className="w-full flex flex-col gap-6">
      {/* Institution Tabs Selector */}
      <div className="flex flex-wrap items-center gap-2 p-1.5 bg-muted/40 border border-border rounded-2xl">
        {exams.map((exam) => {
          const isSelected = exam.institution_code === selectedInst;
          const style = INSTITUTION_STYLING[exam.institution_code] || INSTITUTION_STYLING["USP-SP"];
          const editionsCount = exam.editions.length;

          return (
            <button
              key={exam.institution_code}
              type="button"
              onClick={() => setSelectedInst(exam.institution_code)}
              className={clsx(
                "flex-1 min-w-[130px] sm:min-w-[150px] py-2.5 px-3 rounded-xl font-bold text-xs sm:text-sm transition-all flex items-center justify-center gap-2 cursor-pointer",
                isSelected
                  ? "bg-background text-foreground shadow-xs border border-border/80"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
              )}
            >
              <Building2 size={16} className={isSelected ? style.text : "text-muted-foreground"} />
              <span>{exam.name}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted font-mono font-medium">
                {editionsCount}
              </span>
            </button>
          );
        })}
      </div>

      {/* Selected Institution Banner */}
      {currentExam && (
        <div
          className={clsx(
            "p-5 md:p-6 rounded-2xl border bg-linear-to-r flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-all duration-300",
            styling.border,
            styling.bg
          )}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className={clsx("text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md border", styling.badge)}>
                Prova Canônica
              </span>
              <span className="text-xs text-muted-foreground font-semibold">{currentExam.editions.length} edições catalogadas</span>
            </div>
            <h2 className="text-xl md:text-2xl font-bold text-foreground">{currentExam.full_name}</h2>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-2xl">{styling.desc}</p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-muted-foreground font-medium flex items-center gap-1.5 bg-background/80 px-3 py-1.5 rounded-xl border border-border">
              <Clock size={14} className={styling.text} />
              Tempo Padrão: {Math.floor((currentExam.editions[0]?.duration_minutes || 240) / 60)}h
            </span>
          </div>
        </div>
      )}

      {/* Editions Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-44 rounded-2xl bg-muted/30 border border-border animate-pulse" />
          ))}
        </div>
      ) : currentExam && currentExam.editions.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {currentExam.editions.map((edition: OfficialExamEdition) => {
            const hours = Math.floor(edition.duration_minutes / 60);
            const minutes = edition.duration_minutes % 60;
            const formattedTime = minutes > 0 ? `${hours}h${minutes}min` : `${hours}h00`;

            return (
              <div
                key={edition.year}
                className="group relative bg-card border border-border hover:border-primary/50 rounded-2xl p-5 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between gap-5"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="text-2xl font-black text-foreground tracking-tight group-hover:text-primary transition-colors">
                      {edition.year}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                      <Sparkles size={11} /> Prova Oficial
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-muted-foreground">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <BookOpen size={13} className="text-primary" /> Questões no Caderno:
                      </span>
                      <span className="font-bold text-foreground">{edition.recommended_questions} questões</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Clock size={13} className="text-primary" /> Duração Sugerida:
                      </span>
                      <span className="font-bold text-foreground">{formattedTime}</span>
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-border/40">
                      <span className="flex items-center gap-1.5">
                        <Layers size={13} /> Acervo Completo:
                      </span>
                      <span className="font-semibold text-muted-foreground">{edition.total_available} Qs</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-border/60">
                  <button
                    type="button"
                    onClick={() =>
                      onStartExam(
                        currentExam.institution_code,
                        edition.year,
                        edition.duration_minutes,
                        edition.recommended_questions
                      )
                    }
                    className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs sm:text-sm py-2.5 px-3 rounded-xl transition-all flex items-center justify-center gap-1.5 shadow-xs hover:shadow-sm cursor-pointer"
                  >
                    <Play size={15} fill="currentColor" /> Iniciar Prova Real
                  </button>

                  {!isOffline && onDownloadExam && (
                    <button
                      type="button"
                      title="Baixar esta prova para realizar offline"
                      onClick={() =>
                        onDownloadExam(
                          currentExam.institution_code,
                          edition.year,
                          edition.duration_minutes,
                          edition.recommended_questions
                        )
                      }
                      disabled={isDownloading}
                      className="p-2.5 rounded-xl border border-border bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Download size={16} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-muted/20 border border-border rounded-2xl p-10 text-center text-muted-foreground">
          <BookOpen className="mx-auto w-10 h-10 mb-2 opacity-50" />
          <p className="font-medium text-sm">Nenhuma edição disponível no banco para esta banca no momento.</p>
        </div>
      )}
    </div>
  );
};
