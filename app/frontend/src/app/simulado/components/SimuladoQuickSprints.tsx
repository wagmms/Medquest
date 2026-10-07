"use client";

import React from "react";
import { Zap, Clock, Trophy, Flame, ArrowRight } from "lucide-react";
import clsx from "clsx";

interface SimuladoQuickSprintsProps {
  onStartSprint: (questionsPerArea: number, durationMinutes: number, name: string) => void;
}

const SPRINTS = [
  {
    id: "sprint_25",
    name: "Sprint Expresso",
    badge: "Alta Velocidade",
    questionsTotal: 25,
    questionsPerArea: 5,
    durationMinutes: 45,
    icon: Zap,
    color: "amber",
    bgGradient: "from-amber-500/10 via-amber-500/5 to-transparent",
    borderClass: "border-amber-500/30 hover:border-amber-500/60",
    textClass: "text-amber-600 dark:text-amber-400",
    badgeClass: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
    desc: "5 questões por área. Ideal para treinar ritmo rápido e raciocínio imediato em intervalos ou pós-plantão.",
  },
  {
    id: "half_50",
    name: "Meio Simulado",
    badge: "Mais Popular",
    questionsTotal: 50,
    questionsPerArea: 10,
    durationMinutes: 90,
    icon: Clock,
    color: "blue",
    bgGradient: "from-blue-500/10 via-blue-500/5 to-transparent",
    borderClass: "border-blue-500/30 hover:border-blue-500/60",
    textClass: "text-blue-600 dark:text-blue-400",
    badgeClass: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30",
    desc: "10 questões por área. Equilíbrio ideal entre resistência cognitiva e tempo para debriefing aprofundado.",
  },
  {
    id: "full_100",
    name: "Simulado Geral SP",
    badge: "Padrão Oficial",
    questionsTotal: 100,
    questionsPerArea: 20,
    durationMinutes: 180,
    icon: Trophy,
    color: "emerald",
    bgGradient: "from-emerald-500/10 via-emerald-500/5 to-transparent",
    borderClass: "border-emerald-500/30 hover:border-emerald-500/60",
    textClass: "text-emerald-600 dark:text-emerald-400",
    badgeClass: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
    desc: "20 questões por área. Amostragem representativa das 5 bancas paulistas com 3 horas de prova cronometrada.",
  },
  {
    id: "marathon_120",
    name: "Maratona USP-SP",
    badge: "Resistência Máxima",
    questionsTotal: 120,
    questionsPerArea: 24,
    durationMinutes: 300,
    icon: Flame,
    color: "rose",
    bgGradient: "from-rose-500/10 via-rose-500/5 to-transparent",
    borderClass: "border-rose-500/30 hover:border-rose-500/60",
    textClass: "text-rose-600 dark:text-rose-400",
    badgeClass: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30",
    desc: "24 questões por área e 5 horas de prova. Simulação rigorosa da fadiga mental e do volume cognitivo da USP Capital.",
  },
];

export const SimuladoQuickSprints: React.FC<SimuladoQuickSprintsProps> = ({ onStartSprint }) => {
  return (
    <div className="w-full space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-bold text-foreground">Modos de Treino Rápido & Sprints</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Inicie um bloco de treino cronometrado sem precisar configurar filtros manuais.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {SPRINTS.map((sprint) => {
          const IconComponent = sprint.icon;
          const hours = Math.floor(sprint.durationMinutes / 60);
          const minutes = sprint.durationMinutes % 60;
          const timeLabel = hours > 0 ? (minutes > 0 ? `${hours}h ${minutes}min` : `${hours}h`) : `${minutes} min`;

          return (
            <div
              key={sprint.id}
              className={clsx(
                "group relative bg-card border rounded-3xl p-6 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between gap-6",
                sprint.borderClass
              )}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-4">
                  <div className="flex items-center gap-3">
                    <div className={clsx("w-12 h-12 rounded-2xl flex items-center justify-center bg-muted/50", sprint.textClass)}>
                      <IconComponent size={24} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                        {sprint.name}
                      </h3>
                      <p className="text-xs text-muted-foreground font-semibold">
                        {sprint.questionsTotal} questões · {timeLabel}
                      </p>
                    </div>
                  </div>

                  <span className={clsx("text-[10px] uppercase font-extrabold px-2.5 py-1 rounded-full border", sprint.badgeClass)}>
                    {sprint.badge}
                  </span>
                </div>

                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                  {sprint.desc}
                </p>

                <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Estrutura Curricular:</span>
                  <span className="font-bold text-foreground">{sprint.questionsPerArea} Qs por Especialidade</span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => onStartSprint(sprint.questionsPerArea, sprint.durationMinutes, sprint.name)}
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-sm py-3 px-4 rounded-xl transition-all flex items-center justify-center gap-2 shadow-xs hover:shadow-sm cursor-pointer"
              >
                <span>Iniciar {sprint.name}</span>
                <ArrowRight size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
