"use client";

import React from "react";
import { Sliders, Building2, Calendar, Download, RefreshCw, CheckCircle2, Play } from "lucide-react";
import clsx from "clsx";
import { CustomConfig } from "./SimuladoStartScreen";

interface SimuladoCustomBuilderProps {
  customConfig: CustomConfig;
  setCustomConfig: React.Dispatch<React.SetStateAction<CustomConfig>>;
  groupedInstitutions: Array<{ base: string; codes: string[]; n: number }>;
  metaYears: number[];
  feedbackMode: "exam" | "practice";
  setFeedbackMode: (mode: "exam" | "practice") => void;
  onStartSimulado: () => void;
  onDownloadOfflineSimulado: () => void;
  isDownloadingPackage: boolean;
  downloadStatus: string;
  downloadProgress: number;
  isOffline: boolean;
}

const CANONICAL_SP_INSTITUTIONS = ["USP-SP", "USP-RP", "UNICAMP", "UNIFESP", "SUS-SP"];

export const SimuladoCustomBuilder: React.FC<SimuladoCustomBuilderProps> = ({
  customConfig,
  setCustomConfig,
  groupedInstitutions,
  metaYears,
  feedbackMode,
  setFeedbackMode,
  onStartSimulado,
  onDownloadOfflineSimulado,
  isDownloadingPackage,
  downloadStatus,
  downloadProgress,
  isOffline,
}) => {
  const totalQuestions = (customConfig.questions_per_area || 20) * 5;
  const hours = Math.floor(customConfig.duration_minutes / 60);
  const minutes = customConfig.duration_minutes % 60;
  const formattedDuration = minutes > 0 ? `${hours}h ${minutes}min` : `${hours}h00`;

  const handleSelectAllSP = () => {
    // Coleta todos os codes das 5 bancas
    const spCodes: string[] = [];
    groupedInstitutions.forEach((group) => {
      if (CANONICAL_SP_INSTITUTIONS.includes(group.base)) {
        spCodes.push(...group.codes);
      }
    });
    setCustomConfig((prev) => ({
      ...prev,
      institutions: Array.from(new Set(spCodes)),
    }));
  };

  const handleClearInstitutions = () => {
    setCustomConfig((prev) => ({ ...prev, institutions: [] }));
  };

  const handleSelectRecentYears = (count: number) => {
    const sorted = [...(metaYears || [])].sort((a, b) => b - a).slice(0, count).map(String);
    setCustomConfig((prev) => ({ ...prev, years: sorted }));
  };

  const handleClearYears = () => {
    setCustomConfig((prev) => ({ ...prev, years: [] }));
  };

  return (
    <div className="w-full bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-xs space-y-8">
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase tracking-wider mb-2">
          <Sliders size={13} /> Construtor Avançado
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-foreground">Monte seu Simulado Sob Medida</h2>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Filtre as instituições de interesse, anos de prova, ritmo de resolução e formato pedagógico.
        </p>
      </div>

      {/* 1. Modo de Feedback e Resolução */}
      <div className="space-y-3">
        <label className="block text-sm font-bold text-foreground">
          Modo de Resolução & Feedback
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            role="button"
            tabIndex={0}
            onClick={() => setFeedbackMode("exam")}
            className={clsx(
              "p-5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between gap-3 text-left",
              feedbackMode === "exam"
                ? "bg-primary/10 border-primary ring-1 ring-primary shadow-xs"
                : "bg-muted/20 border-border hover:bg-muted/40"
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className={clsx("w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm", feedbackMode === "exam" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")}>
                  🎯
                </div>
                <div>
                  <h4 className="text-sm font-bold text-foreground">Modo Exame Realista</h4>
                  <p className="text-[11px] text-muted-foreground">Pressão e sigilo de prova oficial</p>
                </div>
              </div>
              {feedbackMode === "exam" && <CheckCircle2 size={18} className="text-primary shrink-0" />}
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Cronômetro regressivo contínuo, sem gabarito ou comentários durante a resolução. A nota TRI e o raio-x completo são revelados apenas ao entregar o caderno.
            </p>
          </div>

          <div
            role="button"
            tabIndex={0}
            onClick={() => setFeedbackMode("practice")}
            className={clsx(
              "p-5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between gap-3 text-left",
              feedbackMode === "practice"
                ? "bg-primary/10 border-primary ring-1 ring-primary shadow-xs"
                : "bg-muted/20 border-border hover:bg-muted/40"
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className={clsx("w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm", feedbackMode === "practice" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")}>
                  💡
                </div>
                <div>
                  <h4 className="text-sm font-bold text-foreground">Modo Treino / Aprendizado</h4>
                  <p className="text-[11px] text-muted-foreground">Feedback pedagógico imediato</p>
                </div>
              </div>
              {feedbackMode === "practice" && <CheckCircle2 size={18} className="text-primary shrink-0" />}
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Veja se acertou ou errou logo após responder cada questão. O comentário e a explicação detalhada do professor ficam liberados imediatamente para estudo ativo.
            </p>
          </div>
        </div>
      </div>

      {/* 2. Seleção de Bancas */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <label className="text-sm font-bold text-foreground flex items-center gap-2">
            <Building2 size={16} className="text-primary" />
            Bancas e Instituições
            <span className="text-xs font-normal text-muted-foreground">
              ({customConfig.institutions.length === 0 ? "Todas de SP" : `${customConfig.institutions.length} selecionadas`})
            </span>
          </label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSelectAllSP}
              className="text-xs font-bold text-primary hover:underline cursor-pointer"
            >
              Marcar 5 Bancas de SP
            </button>
            <span className="text-muted-foreground text-xs">·</span>
            <button
              type="button"
              onClick={handleClearInstitutions}
              className="text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer"
            >
              Limpar
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto pr-1">
          {groupedInstitutions.map((instGroup) => {
            const isSelected = customConfig.institutions.some((c) => instGroup.codes.includes(c));
            const isSP = CANONICAL_SP_INSTITUTIONS.includes(instGroup.base);

            return (
              <label
                key={instGroup.base}
                className={clsx(
                  "inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-all",
                  isSelected
                    ? "bg-primary text-primary-foreground border-primary shadow-xs"
                    : isSP
                    ? "bg-background border-border/80 hover:border-primary/40 text-foreground"
                    : "bg-muted/30 border-border text-muted-foreground hover:bg-muted/60"
                )}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => {
                    setCustomConfig((prev) => {
                      let newInsts = [...prev.institutions];
                      if (e.target.checked) {
                        newInsts.push(...instGroup.codes);
                        newInsts = Array.from(new Set(newInsts));
                      } else {
                        newInsts = newInsts.filter((c) => !instGroup.codes.includes(c));
                      }
                      return { ...prev, institutions: newInsts };
                    });
                  }}
                  className="hidden"
                />
                <span>{instGroup.base}</span>
                {instGroup.n > 0 && (
                  <span
                    className={clsx(
                      "text-[10px] px-1.5 py-0.5 rounded-md font-mono",
                      isSelected ? "bg-primary-foreground/20 text-primary-foreground" : "bg-muted text-muted-foreground"
                    )}
                  >
                    {instGroup.n}
                  </span>
                )}
              </label>
            );
          })}
        </div>
      </div>

      {/* 3. Seleção de Anos */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <label className="text-sm font-bold text-foreground flex items-center gap-2">
            <Calendar size={16} className="text-primary" />
            Anos das Questões
            <span className="text-xs font-normal text-muted-foreground">
              ({customConfig.years.length === 0 ? "Todos os anos" : `${customConfig.years.length} anos`})
            </span>
          </label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleSelectRecentYears(3)}
              className="text-xs font-bold text-primary hover:underline cursor-pointer"
            >
              Últimos 3 Anos
            </button>
            <span className="text-muted-foreground text-xs">·</span>
            <button
              type="button"
              onClick={handleClearYears}
              className="text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer"
            >
              Todos
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {(metaYears || []).map(String).map((year) => {
            const isSelected = customConfig.years.includes(year);
            return (
              <label
                key={year}
                className={clsx(
                  "inline-flex items-center px-3.5 py-1.5 rounded-xl text-xs font-bold cursor-pointer border transition-all",
                  isSelected
                    ? "bg-primary text-primary-foreground border-primary shadow-xs"
                    : "bg-background border-border text-foreground hover:bg-muted/60"
                )}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) =>
                    setCustomConfig((prev) => ({
                      ...prev,
                      years: e.target.checked ? [...prev.years, year] : prev.years.filter((item) => item !== year),
                    }))
                  }
                  className="hidden"
                />
                {year}
              </label>
            );
          })}
        </div>
      </div>

      {/* 4. Quantidade e Duração */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-2">
        <div className="space-y-2">
          <label className="block text-sm font-bold text-foreground">
            Questões por Área Curricular: <span className="text-primary">{customConfig.questions_per_area}</span>
          </label>
          <input
            type="range"
            min="5"
            max="25"
            step="1"
            value={customConfig.questions_per_area}
            onChange={(e) =>
              setCustomConfig((prev) => ({ ...prev, questions_per_area: parseInt(e.target.value) || 20 }))
            }
            className="w-full accent-primary cursor-pointer"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
            <span>5 Qs (25 total)</span>
            <span className="font-bold text-foreground">Total: {totalQuestions} questões</span>
            <span>25 Qs (125 total)</span>
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-bold text-foreground">
            Duração do Simulado: <span className="text-primary">{formattedDuration}</span>
          </label>
          <input
            type="range"
            min="30"
            max="360"
            step="15"
            value={customConfig.duration_minutes}
            onChange={(e) =>
              setCustomConfig((prev) => ({ ...prev, duration_minutes: parseInt(e.target.value) || 180 }))
            }
            className="w-full accent-primary cursor-pointer"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
            <span>30 min</span>
            <span className="font-bold text-foreground">~{Math.round((customConfig.duration_minutes / totalQuestions) * 60)}s por questão</span>
            <span>6 horas</span>
          </div>
        </div>
      </div>

      {/* 5. Opção de 4 alternativas */}
      <div className="pt-2">
        <label className="flex items-center gap-3 text-sm text-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            checked={customConfig.force_4_options}
            onChange={(e) => setCustomConfig((prev) => ({ ...prev, force_4_options: e.target.checked }))}
            className="w-4 h-4 rounded text-primary focus:ring-primary cursor-pointer"
          />
          <span>Adaptar questões para 4 alternativas quando tecnicamente possível</span>
        </label>
      </div>

      {/* 6. Botões de Ação */}
      <div className="flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-border">
        <button
          type="button"
          onClick={onStartSimulado}
          className="w-full sm:flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-sm sm:text-base py-3.5 px-6 rounded-2xl transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-md cursor-pointer"
        >
          <Play size={18} fill="currentColor" /> Iniciar Simulado ({totalQuestions} Qs · {formattedDuration})
        </button>

        {!isOffline && (
          <button
            type="button"
            onClick={onDownloadOfflineSimulado}
            disabled={isDownloadingPackage || isOffline}
            className="w-full sm:w-auto py-3.5 px-5 rounded-2xl border border-border bg-muted/40 hover:bg-muted text-foreground font-semibold text-sm transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {isDownloadingPackage ? (
              <>
                <RefreshCw className="animate-spin text-primary" size={16} />
                <span>{downloadStatus || "Baixando..."} ({downloadProgress}%)</span>
              </>
            ) : (
              <>
                <Download size={16} className="text-primary" />
                <span>Baixar Offline</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
