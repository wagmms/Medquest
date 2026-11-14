"use client";

import React, { useEffect, useRef, useState } from "react";
import { Clock } from "lucide-react";
import clsx from "clsx";

export function formatDurationSeconds(
  totalSeconds: number,
  format: "hhmmss" | "mmss" = "hhmmss"
): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  if (format === "mmss") {
    const m = Math.floor(safe / 60);
    const s = safe % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export interface SessionTimerProps {
  /** Timestamp em milissegundos no qual a contagem regressiva termina. */
  deadlineAt: number;
  /** Segundos iniciais exibidos antes da ativação do cronômetro. */
  fallbackSeconds?: number;
  active: boolean;
  format?: "hhmmss" | "mmss";
  variant?: "simulado" | "osce";
  onExpire?: () => void;
  /** Callbacks acionados uma única vez por marco restante (ex: 180s, 60s). */
  milestones?: Record<number, () => void>;
}

/**
 * Cronômetro isolado para provas longas (Simulado / OSCE).
 * Mantém o estado de 1 segundo encapsulado localmente para evitar
 * re-renderizações em toda a árvore de questões e componentes filhos.
 */
export const SessionTimer: React.FC<SessionTimerProps> = React.memo(({
  deadlineAt,
  fallbackSeconds = 0,
  active,
  format = "hhmmss",
  variant = "simulado",
  onExpire,
  milestones,
}) => {
  const [secondsLeft, setSecondsLeft] = useState<number>(() =>
    deadlineAt > 0
      ? Math.max(0, Math.ceil((deadlineAt - Date.now()) / 1000))
      : Math.max(0, Math.floor(fallbackSeconds))
  );

  const onExpireRef = useRef(onExpire);
  const milestonesRef = useRef(milestones);
  const firedMilestonesRef = useRef<Set<number>>(new Set());
  const expiredFiredRef = useRef(false);

  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    milestonesRef.current = milestones;
  }, [milestones]);

  useEffect(() => {
    firedMilestonesRef.current.clear();
    expiredFiredRef.current = false;

    const syncClock = () => {
      const remaining = deadlineAt > 0
        ? Math.max(0, Math.ceil((deadlineAt - Date.now()) / 1000))
        : Math.max(0, Math.floor(fallbackSeconds));
      setSecondsLeft(remaining);

      if (!active || deadlineAt <= 0) return;

      const currentMilestones = milestonesRef.current;
      if (currentMilestones) {
        for (const key of Object.keys(currentMilestones)) {
          const threshold = Number(key);
          if (
            !Number.isNaN(threshold) &&
            remaining <= threshold &&
            remaining > 0 &&
            !firedMilestonesRef.current.has(threshold)
          ) {
            firedMilestonesRef.current.add(threshold);
            currentMilestones[threshold]?.();
          }
        }
      }

      if (remaining === 0 && !expiredFiredRef.current) {
        expiredFiredRef.current = true;
        onExpireRef.current?.();
      }
    };

    const initialTimer = setTimeout(syncClock, 0);
    if (!active || deadlineAt <= 0) {
      return () => clearTimeout(initialTimer);
    }

    const intervalId = setInterval(syncClock, 1000);
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        syncClock();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearTimeout(initialTimer);
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [active, deadlineAt, fallbackSeconds]);

  const formatted = formatDurationSeconds(secondsLeft, format);

  if (variant === "osce") {
    return (
      <div
        className={clsx(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-mono text-base font-black border",
          secondsLeft < 60
            ? "bg-rose-500/10 text-rose-500 border-rose-500/30 animate-pulse"
            : secondsLeft < 180
            ? "bg-amber-500/10 text-amber-500 border-amber-500/30"
            : "bg-emerald-500/10 text-emerald-500 border-emerald-500/30"
        )}
      >
        <Clock className="w-4 h-4" />
        <span>{formatted}</span>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        "text-2xl lg:text-3xl font-black font-mono",
        secondsLeft < 1800 ? "text-destructive animate-pulse" : "text-foreground"
      )}
    >
      {formatted}
    </div>
  );
});

SessionTimer.displayName = "SessionTimer";
