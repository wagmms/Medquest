"use client";

import React from "react";
import { FileSignature, Play, RotateCcw, AlertTriangle, CloudOff, Download, RefreshCw, Database, Info } from "lucide-react";
import { SimuladoPackage, isPackageValid } from "@/lib/db";

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
}

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
}) => {
  return (
    <div className="bg-card border border-border shadow-1 rounded-2xl p-6 md:p-8 max-w-4xl mx-auto w-full flex flex-col items-center">
      <div className="w-16 h-16 bg-primary/10 text-primary rounded-2xl flex items-center justify-center mb-6 ring-1 ring-primary/20">
        <FileSignature size={32} />
      </div>
      <h2 className="text-3xl font-bold text-foreground mb-3 text-center tracking-tight">
        {hasCustomFilters ? "Simulado Personalizado" : "Novo Simulado"}
      </h2>
      <p className="text-muted-foreground text-base mb-8 max-w-lg text-center">
        {hasCustomFilters
          ? "Esta prova irá simular as condições reais de exame usando os filtros que você escolheu."
          : "Crie um simulado com as suas próprias configurações."}
      </p>

      {!hasCustomFilters && (
        <div className="w-full mb-8 bg-muted/30 p-6 rounded-2xl border border-border text-left flex flex-col gap-5 animate-in slide-in-from-top-4 fade-in duration-300">
          <div>
            <label className="block text-sm font-bold text-foreground mb-2">Bancas Incluídas (deixe vazio para todas)</label>
            <div className="flex flex-wrap gap-2">
              {groupedInstitutions.map(instGroup => (
                <label key={instGroup.base} className="flex items-center gap-1.5 bg-background border border-border px-3 py-1.5 rounded-lg text-sm cursor-pointer hover:bg-muted transition-colors">
                  <input
                    type="checkbox"
                    checked={customConfig.institutions.some(c => instGroup.codes.includes(c))}
                    onChange={(e) => {
                      setCustomConfig(prev => {
                        let newInsts = [...prev.institutions];
                        if (e.target.checked) {
                          newInsts.push(...instGroup.codes);
                          newInsts = Array.from(new Set(newInsts));
                        } else {
                          newInsts = newInsts.filter(c => !instGroup.codes.includes(c));
                        }
                        return { ...prev, institutions: newInsts };
                      });
                    }}
                    className="rounded text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                  />
                  {instGroup.base} {instGroup.n > 0 ? `(${instGroup.n})` : ''}
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-bold text-foreground mb-2">Anos (deixe vazio para todos)</label>
            <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto pr-2 custom-scrollbar">
              {(metaYears || []).map(year => String(year)).map(year => (
                <label key={year} className="flex items-center gap-1.5 bg-background border border-border px-3 py-1.5 rounded-lg text-sm cursor-pointer hover:bg-muted transition-colors">
                  <input
                    type="checkbox"
                    checked={customConfig.years.includes(year)}
                    onChange={(event) => setCustomConfig(prev => ({
                      ...prev,
                      years: event.target.checked ? [...prev.years, year] : prev.years.filter(item => item !== year),
                    }))}
                    className="rounded text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                  />
                  {year}
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-5">
            <div className="flex-1">
              <label className="block text-sm font-bold text-foreground mb-2">Questões por Área</label>
              <div className="relative">
                <input
                  type="number"
                  min="5" max="30"
                  value={customConfig.questions_per_area}
                  onChange={(e) => setCustomConfig(prev => ({ ...prev, questions_per_area: parseInt(e.target.value) || 20 }))}
                  className="w-full bg-background border border-border rounded-xl p-3 text-foreground focus:ring-2 focus:ring-primary/50 transition-shadow outline-none"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1.5 font-medium flex items-center gap-1.5">
                <Info size={14} className="shrink-0 text-muted-foreground" />
                Multiplicado por 5 grandes áreas
              </p>
            </div>
            <div className="flex-1">
              <label className="block text-sm font-bold text-foreground mb-2">Duração (minutos)</label>
              <div className="relative">
                <input
                  type="number"
                  min="15" max="600" step="15"
                  value={customConfig.duration_minutes}
                  onChange={(event) => setCustomConfig(prev => ({ ...prev, duration_minutes: Math.max(15, Math.min(600, parseInt(event.target.value) || 180)) }))}
                  className="w-full bg-background border border-border rounded-xl p-3 text-foreground focus:ring-2 focus:ring-primary/50 transition-shadow outline-none"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1.5 font-medium flex items-center gap-1.5">
                <Info size={14} className="shrink-0 text-muted-foreground" />
                Entre 15 min e 10 horas
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { questions: 25, minutes: 75, label: "25 · 75 min" },
              { questions: 50, minutes: 150, label: "50 · 150 min" },
              { questions: 100, minutes: 300, label: "100 · 300 min" }
            ].map(preset => (
              <button 
                key={preset.label} 
                type="button" 
                onClick={() => setCustomConfig(prev => ({ ...prev, questions_per_area: preset.questions / 5, duration_minutes: preset.minutes }))} 
                className="rounded-lg border border-border bg-background px-3.5 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted min-h-[36px] transition-colors cursor-pointer"
              >
                {preset.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
            <input 
              type="checkbox" 
              checked={customConfig.force_4_options} 
              onChange={event => setCustomConfig(prev => ({ ...prev, force_4_options: event.target.checked }))} 
              className="rounded text-primary focus:ring-primary cursor-pointer" 
            />
            Adaptar questões para 4 alternativas quando possível
          </label>
        </div>
      )}

      {/* Banner de status offline / pacote pronto */}
      {offlinePackage && isPackageValid(offlinePackage).valid && (
        <div className="w-full max-w-lg mb-6 p-4 rounded-xl bg-success/10 border border-success/30 flex items-center justify-between gap-3 text-left animate-in fade-in">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-success/20 text-success flex items-center justify-center shrink-0">
              <Database size={18} />
            </div>
            <div>
              <p className="text-xs font-bold text-foreground">{offlinePackage.name}</p>
              <p className="text-[11px] text-muted-foreground">
                {offlinePackage.details_count} questões disponíveis · Válido até {new Date(offlinePackage.expires_at).toLocaleDateString("pt-BR")}
              </p>
            </div>
          </div>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-success/20 text-success shrink-0">
            Pronto Offline
          </span>
        </div>
      )}

      {isOffline && (!offlinePackage || !isPackageValid(offlinePackage).valid) && (
        <div className="w-full max-w-lg mb-6 p-4 rounded-xl bg-warning/10 border border-warning/30 flex items-center gap-3 text-left animate-in fade-in text-warning-foreground">
          <CloudOff size={20} className="text-warning shrink-0" />
          <p className="text-xs font-medium">
            Você está desconectado e não possui um pacote offline válido. Conecte-se à internet para baixar um simulado.
          </p>
        </div>
      )}

      {!hasCustomFilters && !isOffline && (
        <div className="w-full max-w-lg mb-6 flex flex-col gap-2">
          <button
            type="button"
            onClick={onDownloadOfflineSimulado}
            disabled={isDownloadingPackage || isOffline}
            className="w-full py-2.5 px-4 rounded-xl border border-border bg-muted/40 hover:bg-muted text-foreground font-semibold text-xs transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {isDownloadingPackage ? (
              <><RefreshCw className="animate-spin" size={15} /> {downloadStatus || "Baixando..."} ({downloadProgress}%)</>
            ) : (
              <><Download size={15} className="text-primary" /> Baixar este Simulado para Uso Offline</>
            )}
          </button>
          {isDownloadingPackage && (
            <div className="w-full bg-muted h-1.5 rounded-full overflow-hidden">
              <div className="bg-primary h-full transition-all duration-300" style={{ width: `${downloadProgress}%` }} />
            </div>
          )}
        </div>
      )}

      <div className="bg-warning/10 text-warning-foreground border border-warning/20 rounded-xl p-4 flex items-start gap-3 w-full max-w-lg mb-8 text-left text-sm shadow-sm">
        <AlertTriangle size={20} className="shrink-0 mt-0.5 text-warning" />
        <p className="font-medium text-warning-foreground/90">
          Este é um bloco cronometrado de treino. Você não receberá feedback imediato; resultado e comentários aparecem apenas ao entregar.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 w-full max-w-lg">
        {hasSavedState && (
          <button
            onClick={onResumeSimulado}
            disabled={!clientReady}
            aria-label="Continuar Simulado em Andamento"
            className="flex-1 bg-secondary hover:bg-secondary/90 text-secondary-foreground font-bold py-3.5 px-6 rounded-xl transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-md disabled:opacity-60 cursor-pointer"
          >
            <RotateCcw size={20} />
            Continuar Andamento
          </button>
        )}
        <button
          onClick={onStartSimulado}
          disabled={!clientReady}
          className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3.5 px-6 rounded-xl transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-md disabled:opacity-60 cursor-pointer"
        >
          <Play size={20} fill="currentColor" />
          {hasSavedState
            ? (hasCustomFilters ? "Novo Personalizado" : "Novo Simulado")
            : (isOffline ? "Iniciar Simulado Offline" : "Iniciar Simulado")}
        </button>
      </div>
    </div>
  );
};
