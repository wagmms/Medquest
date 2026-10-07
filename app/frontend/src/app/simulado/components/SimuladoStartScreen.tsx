"use client";

import React, { useState, useEffect } from "react";
import {
  FileSignature,
  Play,
  RotateCcw,
  AlertTriangle,
  Zap,
  Sliders,
  History,
  GraduationCap
} from "lucide-react";
import { SimuladoPackage, isPackageValid } from "@/lib/db";
import { OfficialExam, SimuladoSessionItem } from "@/types/api";
import { api } from "@/lib/api";
import clsx from "clsx";
import { SimuladoCockpitHero } from "./SimuladoCockpitHero";
import { SimuladoOfficialExams } from "./SimuladoOfficialExams";
import { SimuladoQuickSprints } from "./SimuladoQuickSprints";
import { SimuladoCustomBuilder } from "./SimuladoCustomBuilder";
import { SimuladoHistoryView } from "./SimuladoHistoryView";

export interface CustomConfig {
  institutions: string[];
  years: string[];
  questions_per_area: number;
  duration_minutes: number;
  force_4_options: boolean;
}

export interface SimuladoStartScreenProps {
  hasCustomFilters: boolean;
  groupedInstitutions: Array<{ base: string; codes: string[]; n: number }>;
  metaYears: number[];
  customConfig: CustomConfig;
  setCustomConfig: React.Dispatch<React.SetStateAction<CustomConfig>>;
  offlinePackage: SimuladoPackage | null;
  isOffline: boolean;
  isDownloadingPackage: boolean;
  downloadStatus: string;
  downloadProgress: number;
  onDownloadOfflineSimulado: () => void;
  hasSavedState: boolean;
  clientReady: boolean;
  onResumeSimulado: () => void;
  onStartSimulado: () => void;
  feedbackMode?: "exam" | "practice";
  setFeedbackMode?: (mode: "exam" | "practice") => void;
}

type TabKey = "official" | "sprints" | "builder" | "history";

export const SimuladoStartScreen: React.FC<SimuladoStartScreenProps> = ({
  hasCustomFilters,
  groupedInstitutions,
  metaYears,
  customConfig,
  setCustomConfig,
  offlinePackage,
  isOffline,
  isDownloadingPackage,
  downloadStatus,
  downloadProgress,
  onDownloadOfflineSimulado,
  hasSavedState,
  clientReady,
  onResumeSimulado,
  onStartSimulado,
  feedbackMode = "exam",
  setFeedbackMode = () => {},
}) => {
  const [activeTab, setActiveTab] = useState<TabKey>("official");
  const [officialExams, setOfficialExams] = useState<OfficialExam[]>([]);
  const [loadingExams, setLoadingExams] = useState(true);
  const [sessions, setSessions] = useState<SimuladoSessionItem[]>([]);

  // Carrega Provas Oficiais e Histórico para o Cockpit
  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      try {
        const [examsRes, sessionsRes] = await Promise.allSettled([
          api.questions.getOfficialExams(),
          api.questions.getSimuladoSessions(),
        ]);

        if (isMounted) {
          if (examsRes.status === "fulfilled") {
            setOfficialExams(examsRes.value.exams || []);
          }
          if (sessionsRes.status === "fulfilled") {
            setSessions(sessionsRes.value.sessions || []);
          }
        }
      } finally {
        if (isMounted) setLoadingExams(false);
      }
    };

    void loadData();
    return () => {
      isMounted = false;
    };
  }, []);

  // Métricas do Hero Cockpit
  const completedCount = sessions.length;
  const averageAccuracy =
    completedCount > 0
      ? sessions.reduce((acc, s) => acc + (s.accuracy_percent || 0), 0) / completedCount
      : 0;
  const totalTimeHours =
    sessions.reduce((acc, s) => acc + (s.elapsed_seconds || 0), 0) / 3600;

  // Handlers diretos de Provas Oficiais e Sprints
  const handleStartOfficialExam = (
    institution: string,
    year: number,
    durationMinutes: number,
    questionsCount: number
  ) => {
    const questionsPerArea = Math.max(1, Math.round(questionsCount / 5));
    setCustomConfig({
      institutions: [institution],
      years: [String(year)],
      questions_per_area: questionsPerArea,
      duration_minutes: durationMinutes,
      force_4_options: false,
    });
    // Inicia imediatamente
    setTimeout(() => {
      onStartSimulado();
    }, 50);
  };

  const handleStartSprint = (
    questionsPerArea: number,
    durationMinutes: number
  ) => {
    setCustomConfig({
      institutions: ["USP-SP", "USP-RP", "UNICAMP", "UNIFESP", "SUS-SP"],
      years: [],
      questions_per_area: questionsPerArea,
      duration_minutes: durationMinutes,
      force_4_options: false,
    });
    // Inicia imediatamente
    setTimeout(() => {
      onStartSimulado();
    }, 50);
  };

  // Se veio de filtros específicos da URL, exibe o cartão simplificado e direto
  if (hasCustomFilters) {
    return (
      <div className="bg-card border border-border shadow-xs rounded-3xl p-6 md:p-8 max-w-3xl mx-auto w-full flex flex-col items-center animate-in fade-in duration-300">
        <div className="w-16 h-16 bg-primary/10 text-primary rounded-2xl flex items-center justify-center mb-6 ring-1 ring-primary/20">
          <FileSignature size={32} />
        </div>
        <h2 className="text-2xl sm:text-3xl font-extrabold text-foreground mb-3 text-center tracking-tight">
          Simulado Personalizado
        </h2>
        <p className="text-muted-foreground text-sm sm:text-base mb-8 max-w-lg text-center leading-relaxed">
          Esta prova irá simular as condições oficiais de exame usando o caderno de filtros que você selecionou.
        </p>

        <div className="bg-warning/10 text-warning-foreground border border-warning/20 rounded-2xl p-4 flex items-start gap-3 w-full max-w-lg mb-8 text-left text-sm shadow-xs">
          <AlertTriangle size={20} className="shrink-0 mt-0.5 text-warning" />
          <p className="font-medium text-warning-foreground/90 leading-relaxed text-xs sm:text-sm">
            Este é um bloco de prova cronometrado. O feedback e o cálculo do seu desempenho TRI serão consolidados após a entrega final.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 w-full max-w-lg">
          {hasSavedState && (
            <button
              onClick={onResumeSimulado}
              disabled={!clientReady}
              aria-label="Continuar Simulado em Andamento"
              className="flex-1 bg-secondary hover:bg-secondary/90 text-secondary-foreground font-bold py-3.5 px-6 rounded-xl transition-all flex items-center justify-center gap-2 shadow-xs cursor-pointer disabled:opacity-60"
            >
              <RotateCcw size={18} />
              Continuar Andamento
            </button>
          )}
          <button
            onClick={onStartSimulado}
            disabled={!clientReady}
            className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3.5 px-6 rounded-xl transition-all flex items-center justify-center gap-2 shadow-xs hover:shadow-md cursor-pointer disabled:opacity-60"
          >
            <Play size={18} fill="currentColor" />
            Iniciar Agora
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl mx-auto flex flex-col items-center pb-12 animate-in fade-in duration-300">
      {/* Cockpit Hero Banner with Live KPIs */}
      <SimuladoCockpitHero
        completedCount={completedCount}
        averageAccuracy={averageAccuracy}
        totalTimeHours={totalTimeHours}
        isOffline={isOffline}
        hasOfflinePackage={Boolean(offlinePackage && isPackageValid(offlinePackage).valid)}
      />

      {/* Banner de Simulado em Andamento (Salvo) */}
      {hasSavedState && (
        <div className="w-full mb-8 p-5 rounded-2xl bg-primary/10 border border-primary/30 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xs animate-in slide-in-from-top-4">
          <div className="flex items-center gap-3.5 text-left">
            <div className="w-10 h-10 rounded-xl bg-primary text-primary-foreground flex items-center justify-center shrink-0">
              <RotateCcw size={20} />
            </div>
            <div>
              <h4 className="text-sm font-bold text-foreground">Você tem um simulado em andamento!</h4>
              <p className="text-xs text-muted-foreground">
                Suas respostas e o cronômetro foram salvos com segurança. Você pode retomar exatamente de onde parou.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onResumeSimulado}
            disabled={!clientReady}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground text-xs sm:text-sm font-bold transition-all shadow-xs cursor-pointer flex items-center justify-center gap-2"
          >
            <Play size={15} fill="currentColor" /> Retomar Simulado
          </button>
        </div>
      )}

      {/* Cockpit Navigation Tabs */}
      <div className="w-full flex items-center justify-start sm:justify-center border-b border-border/80 mb-8 overflow-x-auto no-scrollbar gap-1 sm:gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("official")}
          className={clsx(
            "flex items-center gap-2 py-3 px-4 font-bold text-xs sm:text-sm border-b-2 transition-all cursor-pointer whitespace-nowrap",
            activeTab === "official"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
          )}
        >
          <GraduationCap size={18} />
          <span>Provas na Íntegra (Oficiais)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("sprints")}
          className={clsx(
            "flex items-center gap-2 py-3 px-4 font-bold text-xs sm:text-sm border-b-2 transition-all cursor-pointer whitespace-nowrap",
            activeTab === "sprints"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
          )}
        >
          <Zap size={18} />
          <span>Modos Rápidos & Sprints</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("builder")}
          className={clsx(
            "flex items-center gap-2 py-3 px-4 font-bold text-xs sm:text-sm border-b-2 transition-all cursor-pointer whitespace-nowrap",
            activeTab === "builder"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
          )}
        >
          <Sliders size={18} />
          <span>Construtor Sob Medida</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("history")}
          className={clsx(
            "flex items-center gap-2 py-3 px-4 font-bold text-xs sm:text-sm border-b-2 transition-all cursor-pointer whitespace-nowrap",
            activeTab === "history"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
          )}
        >
          <History size={18} />
          <span>Histórico & Caderno</span>
          {completedCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-muted font-mono">
              {completedCount}
            </span>
          )}
        </button>
      </div>

      {/* Tab Panels */}
      <div className="w-full">
        {activeTab === "official" && (
          <SimuladoOfficialExams
            exams={officialExams}
            isLoading={loadingExams}
            onStartExam={handleStartOfficialExam}
            onDownloadExam={onDownloadOfflineSimulado}
            isOffline={isOffline}
            isDownloading={isDownloadingPackage}
          />
        )}

        {activeTab === "sprints" && (
          <SimuladoQuickSprints onStartSprint={handleStartSprint} />
        )}

        {activeTab === "builder" && (
          <SimuladoCustomBuilder
            customConfig={customConfig}
            setCustomConfig={setCustomConfig}
            groupedInstitutions={groupedInstitutions}
            metaYears={metaYears}
            feedbackMode={feedbackMode}
            setFeedbackMode={setFeedbackMode}
            onStartSimulado={onStartSimulado}
            onDownloadOfflineSimulado={onDownloadOfflineSimulado}
            isDownloadingPackage={isDownloadingPackage}
            downloadStatus={downloadStatus}
            downloadProgress={downloadProgress}
            isOffline={isOffline}
          />
        )}

        {activeTab === "history" && (
          <SimuladoHistoryView />
        )}
      </div>
    </div>
  );
};
