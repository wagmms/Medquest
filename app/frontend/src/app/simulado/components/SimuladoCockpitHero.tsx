"use client";

import React from "react";
import { Award, CheckCircle2, Clock, Zap, WifiOff } from "lucide-react";

interface SimuladoCockpitHeroProps {
  completedCount: number;
  averageAccuracy: number;
  totalTimeHours: number;
  isOffline: boolean;
  hasOfflinePackage: boolean;
}

export const SimuladoCockpitHero: React.FC<SimuladoCockpitHeroProps> = ({
  completedCount,
  averageAccuracy,
  totalTimeHours,
  isOffline,
  hasOfflinePackage,
}) => {
  return (
    <div className="w-full mb-8">
      {/* Top Banner / Heading */}
      <div className="relative overflow-hidden rounded-3xl bg-linear-to-br from-card via-card to-primary/5 border border-border p-6 md:p-8 shadow-xs">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold uppercase tracking-wider">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              Arena de Simulados · R1 São Paulo
            </div>
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-foreground tracking-tight">
              Simulados Oficiais & Treinamento Estratégico
            </h1>
            <p className="text-muted-foreground text-sm sm:text-base leading-relaxed">
              Treine em condições idênticas às grandes bancas de São Paulo (USP-SP, USP-RP, UNICAMP, UNIFESP e SUS-SP) com cronometragem oficial, Teoria de Resposta ao Item (TRI) e cadernos balanceados por especialidade.
            </p>
          </div>

          {/* Quick Offline Status Badge */}
          <div className="flex md:flex-col items-start md:items-end gap-2 shrink-0">
            {isOffline ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-warning/15 text-warning border border-warning/30 text-xs font-bold">
                <WifiOff size={14} /> Modo Plantão Offline
              </span>
            ) : hasOfflinePackage ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-success/15 text-success border border-success/30 text-xs font-bold">
                <CheckCircle2 size={14} /> Pacote Offline Pronto
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary/10 text-primary border border-primary/20 text-xs font-semibold">
                Sincronizado na Nuvem
              </span>
            )}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-6 pt-6 border-t border-border/60">
          <div className="bg-background/80 backdrop-blur-xs border border-border/60 rounded-2xl p-4 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <Award size={20} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium">Simulados Feitos</p>
              <p className="text-xl font-bold text-foreground tracking-tight">{completedCount}</p>
            </div>
          </div>

          <div className="bg-background/80 backdrop-blur-xs border border-border/60 rounded-2xl p-4 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
              <CheckCircle2 size={20} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium">Acurácia Média</p>
              <p className="text-xl font-bold text-foreground tracking-tight">
                {averageAccuracy > 0 ? `${averageAccuracy.toFixed(1)}%` : "—"}
              </p>
            </div>
          </div>

          <div className="bg-background/80 backdrop-blur-xs border border-border/60 rounded-2xl p-4 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
              <Clock size={20} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium">Horas de Prova</p>
              <p className="text-xl font-bold text-foreground tracking-tight">
                {totalTimeHours > 0 ? `${totalTimeHours.toFixed(1)}h` : "0h"}
              </p>
            </div>
          </div>

          <div className="bg-background/80 backdrop-blur-xs border border-border/60 rounded-2xl p-4 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
              <Zap size={20} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium">Foco Curricular</p>
              <p className="text-sm font-bold text-foreground tracking-tight truncate">5 Grandes Áreas</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
