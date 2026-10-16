"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  OscePhysiologyVitals,
  OscePhysiologyEngineConfig,
  OsceInterventionModifier,
} from "@/types/api";

export interface ActiveInterventionItem {
  id: string;
  key: string;
  label: string;
  appliedAtElapsed: number;
  modifier: OsceInterventionModifier;
  active: boolean;
}

export interface VitalAlarm {
  id: string;
  level: "red" | "yellow";
  message: string;
}

export interface DisplayedNibp {
  sbp: number;
  dbp: number;
  pam: number;
  measuredAtElapsed: number;
}

export interface UseVitalStateEngineProps {
  initialConfig?: OscePhysiologyEngineConfig | null;
  fallbackVitals?: Record<string, string> | null;
  durationSeconds: number;
  timeLeft: number;
  isActive: boolean;
}

function parseFallbackVitals(vitals?: Record<string, string> | null): OscePhysiologyVitals {
  if (!vitals) {
    return {
      hr: 78,
      sbp: 120,
      dbp: 80,
      spo2: 98,
      rr: 16,
      temp: 36.5,
      gcs: 15,
      rhythm: "NORMAL_SINUS",
      etco2: 38,
      perfusion_index: 2.5,
    };
  }

  const fcMatch = vitals.fc?.match(/\b(\d{2,3})\b/);
  const hr = fcMatch ? parseInt(fcMatch[1], 10) : 78;

  const paMatch = vitals.pa?.match(/(\d{2,3})\s*[xX/]\s*(\d{2,3})/);
  const sbp = paMatch ? parseInt(paMatch[1], 10) : 120;
  const dbp = paMatch ? parseInt(paMatch[2], 10) : 80;

  const satMatch = vitals.sato2?.match(/(\d{2,3})%/);
  const spo2 = satMatch ? parseInt(satMatch[1], 10) : 97;

  const frMatch = vitals.fr?.match(/\b(\d{1,2})\b/);
  const rr = frMatch ? parseInt(frMatch[1], 10) : 16;

  const tempMatch = vitals.temp?.match(/(\d{2}[.,]\d)/);
  const temp = tempMatch ? parseFloat(tempMatch[1].replace(",", ".")) : 36.5;

  let rhythm = "NORMAL_SINUS";
  if (hr > 150) rhythm = "UNSTABLE_SVT";
  else if (hr >= 100) rhythm = "SINUS_TACHYCARDIA";
  else if (hr < 50) rhythm = "SINUS_BRADYCARDIA";

  return {
    hr,
    sbp,
    dbp,
    spo2,
    rr,
    temp,
    gcs: sbp >= 90 ? 15 : 13,
    rhythm,
    etco2: 36,
    perfusion_index: sbp >= 90 ? 2.2 : 0.8,
  };
}

export function useVitalStateEngine({
  initialConfig,
  fallbackVitals,
  durationSeconds,
  timeLeft,
  isActive,
}: UseVitalStateEngineProps) {
  // Estado base inicial
  const baseVitals = useMemo<OscePhysiologyVitals>(() => {
    if (initialConfig?.initial_state) {
      return { ...initialConfig.initial_state };
    }
    return parseFallbackVitals(fallbackVitals);
  }, [initialConfig, fallbackVitals]);

  // Vitals dinâmicos reativos em tempo real
  const [vitals, setVitals] = useState<OscePhysiologyVitals>(baseVitals);
  
  // Sensores monitorados
  const [isMonitored, setIsMonitored] = useState<{
    ecg: boolean;
    spo2: boolean;
    nibp: boolean;
    capno: boolean;
  }>({
    ecg: false,
    spo2: false,
    nibp: false,
    capno: false,
  });

  // Aferição NIBP beira-leito
  const [displayedNibp, setDisplayedNibp] = useState<DisplayedNibp | null>(null);
  const [isMeasuringNibp, setIsMeasuringNibp] = useState(false);

  // Lista de intervenções clínicas ativas
  const [interventions, setInterventions] = useState<ActiveInterventionItem[]>([]);
  const [iatrogenicAlerts, setIatrogenicAlerts] = useState<string[]>([]);

  // Alarmes sonoros e silenciamento
  const [isAlarmSilenced, setIsAlarmSilenced] = useState(false);
  const [isAudioMuted, setIsAudioMuted] = useState(false);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Histórico para pós-morte
  const [vitalsHistory, setVitalsHistory] = useState<
    Array<{ elapsed: number; hr: number; sbp: number; dbp: number; pam: number; spo2: number; rhythm: string }>
  >([]);

  // Sincroniza estado base caso baseVitals mude (padrão oficial React 19 para ajuste de estado baseado em prop)
  const [prevBase, setPrevBase] = useState(baseVitals);
  if (baseVitals !== prevBase) {
    setPrevBase(baseVitals);
    setVitals(baseVitals);
  }

  const elapsedSeconds = Math.max(0, durationSeconds - timeLeft);

  // Aferir PNI sob demanda
  const measureNibp = useCallback(() => {
    if (isMeasuringNibp) return;
    setIsMeasuringNibp(true);

    setTimeout(() => {
      setVitals((curr) => {
        const pam = Math.round((curr.sbp + 2 * curr.dbp) / 3);
        setDisplayedNibp({
          sbp: curr.sbp,
          dbp: curr.dbp,
          pam,
          measuredAtElapsed: elapsedSeconds,
        });
        return curr;
      });
      setIsMeasuringNibp(false);
    }, 2800);
  }, [isMeasuringNibp, elapsedSeconds]);

  // Conectar sensores beira-leito
  const connectSensors = useCallback(
    (sensors: ("all" | "ecg" | "spo2" | "nibp" | "capno")[] = ["all"]) => {
      setIsMonitored((prev) => {
        if (sensors.includes("all")) {
          return { ecg: true, spo2: true, nibp: true, capno: true };
        }
        return {
          ecg: sensors.includes("ecg") ? true : prev.ecg,
          spo2: sensors.includes("spo2") ? true : prev.spo2,
          nibp: sensors.includes("nibp") ? true : prev.nibp,
          capno: sensors.includes("capno") ? true : prev.capno,
        };
      });

      // Auto-aferição inicial de PNI
      if (!displayedNibp) {
        measureNibp();
      }
    },
    [displayedNibp, measureNibp]
  );

  // Silenciar alarmes por 120s
  const silenceAlarms = useCallback((seconds = 120) => {
    setIsAlarmSilenced(true);
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = setTimeout(() => {
      setIsAlarmSilenced(false);
    }, seconds * 1000);
  }, []);

  // Alternar mudo geral de áudio
  const toggleAudio = useCallback(() => {
    setIsAudioMuted((prev) => !prev);
  }, []);

  // Aplicar intervenção farmacológica ou clínica
  const applyIntervention = useCallback(
    (key: string, label: string) => {
      const modifier = initialConfig?.intervention_modifiers?.[key] || {
        onset_seconds: 10,
        duration_seconds: 60,
      };

      const newItem: ActiveInterventionItem = {
        id: `interv-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        key,
        label,
        appliedAtElapsed: elapsedSeconds,
        modifier,
        active: true,
      };

      setInterventions((prev) => [...prev, newItem]);

      // Aplicação instantânea se for procedimento ou choque
      if (modifier.instant && modifier.target_vitals) {
        setVitals((curr) => ({
          ...curr,
          ...modifier.target_vitals,
        }));
      }

      // Alerta de Iatrogenia
      if (modifier.iatrogenic_alert) {
        setIatrogenicAlerts((prev) => [...prev, modifier.iatrogenic_alert!]);
      }
    },
    [initialConfig, elapsedSeconds]
  );

  // Executar cardioversão elétrica / desfibrilação
  const executeCardioversion = useCallback(
    (synchronized: boolean, joules: number) => {
      const isTV = vitals.rhythm === "VENTRICULAR_TACHYCARDIA" || vitals.rhythm === "UNSTABLE_SVT";

      if (isTV) {
        if (synchronized) {
          // Reversão de sucesso para Ritmo Sinusal
          applyIntervention("cardioversion_sync", `Cardioversão Elétrica Sincronizada (${joules}J)`);
          setVitals((curr) => ({
            ...curr,
            hr: 82,
            sbp: 116,
            dbp: 72,
            spo2: 97,
            rr: 18,
            gcs: 15,
            rhythm: "NORMAL_SINUS",
          }));
        } else {
          // Iatrogenia R sobre T: induz Fibrilação Ventricular
          applyIntervention("cardioversion_unsync", `Choque Desincronizado ${joules}J (R sobre T)`);
          setVitals((curr) => ({
            ...curr,
            hr: 250,
            sbp: 0,
            dbp: 0,
            spo2: 0,
            rr: 0,
            gcs: 3,
            rhythm: "VENTRICULAR_FIBRILLATION",
          }));
        }
      } else if (vitals.rhythm === "VENTRICULAR_FIBRILLATION") {
        // Desfibrilação da FV
        applyIntervention("defibrillation", `Desfibrilação Bifásica ${joules}J`);
        setVitals((curr) => ({
          ...curr,
          hr: 92,
          sbp: 104,
          dbp: 68,
          spo2: 95,
          rr: 16,
          gcs: 14,
          rhythm: "NORMAL_SINUS",
        }));
      }
    },
    [vitals.rhythm, applyIntervention]
  );

  // Ciclo fisiológico dinâmico rodando a cada segundo
  useEffect(() => {
    if (!isActive) return;

    const interval = setInterval(() => {
      setVitals((curr) => {
        let updated = { ...curr };

        // 1. Aplica modificadores de intervenções ativas (farmacocinética)
        interventions.forEach((item) => {
          const deltaT = elapsedSeconds - item.appliedAtElapsed;
          const onset = item.modifier.onset_seconds || 10;
          const duration = item.modifier.duration_seconds || 60;

          if (deltaT >= onset && deltaT <= onset + duration) {
            const dv = item.modifier.delta_vitals;
            if (dv) {
              if (dv.sbp) updated.sbp = Math.min(200, Math.max(0, updated.sbp + dv.sbp * 0.05));
              if (dv.dbp) updated.dbp = Math.min(130, Math.max(0, updated.dbp + (dv.dbp || 0) * 0.05));
              if (dv.hr) updated.hr = Math.min(220, Math.max(0, updated.hr + dv.hr * 0.05));
              if (dv.spo2) updated.spo2 = Math.min(100, Math.max(0, updated.spo2 + (dv.spo2 || 0) * 0.05));
            }
          }
        });

        // 2. Aplica progressão natural (deterioração se sem intervenção)
        if (initialConfig?.natural_progression) {
          const appliedKeys = interventions.map((i) => i.key);
          initialConfig.natural_progression.forEach((rule) => {
            const conditionMet =
              (rule.condition.includes("time_elapsed > 120") && elapsedSeconds > 120) ||
              (rule.condition.includes("time_elapsed > 180") && elapsedSeconds > 180) ||
              (rule.condition.includes("sbp < 55") && updated.sbp < 55);

            const hasCounterIntervention = appliedKeys.some((k) => rule.condition.includes(k));

            if (conditionMet && !hasCounterIntervention) {
              if (rule.effects_per_minute) {
                const em = rule.effects_per_minute;
                if (em.sbp) updated.sbp = Math.max(0, updated.sbp + em.sbp / 60);
                if (em.dbp) updated.dbp = Math.max(0, updated.dbp + em.dbp / 60);
                if (em.hr) updated.hr = Math.min(240, updated.hr + (em.hr || 0) / 60);
                if (em.spo2) updated.spo2 = Math.max(0, updated.spo2 + (em.spo2 || 0) / 60);
                if (em.gcs && updated.gcs) updated.gcs = Math.max(3, updated.gcs + (em.gcs || 0) / 60);
              }

              if (rule.override_vitals && updated.sbp <= 50) {
                updated = { ...updated, ...rule.override_vitals };
              }
            }
          });
        }

        // 3. Jitter Fisiológico Estocástico (pequena flutuação realista ±1%)
        const jitter = (Math.random() - 0.5) * 1.2;
        if (updated.sbp > 30) {
          updated.sbp = Math.round(updated.sbp + jitter);
          updated.dbp = Math.round(updated.dbp + jitter * 0.5);
          updated.hr = Math.round(updated.hr + jitter * 0.8);
        }

        // Arredondamentos e travas
        updated.sbp = Math.max(0, Math.min(240, Math.round(updated.sbp)));
        updated.dbp = Math.max(0, Math.min(140, Math.round(updated.dbp)));
        updated.hr = Math.max(0, Math.min(260, Math.round(updated.hr)));
        updated.spo2 = Math.max(0, Math.min(100, Math.round(updated.spo2)));

        return updated;
      });

      // Grava no histórico a cada 5 segundos
      if (elapsedSeconds % 5 === 0) {
        setVitalsHistory((prev) => [
          ...prev,
          {
            elapsed: elapsedSeconds,
            hr: vitals.hr,
            sbp: vitals.sbp,
            dbp: vitals.dbp,
            pam: Math.round((vitals.sbp + 2 * vitals.dbp) / 3),
            spo2: vitals.spo2,
            rhythm: vitals.rhythm,
          },
        ]);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive, elapsedSeconds, interventions, initialConfig, vitals]);

  // Lista de alarmes ativos
  const activeAlarms = useMemo<VitalAlarm[]>(() => {
    const list: VitalAlarm[] = [];

    if (!isMonitored.ecg && !isMonitored.spo2) {
      list.push({ id: "sensors_disconnected", level: "yellow", message: "CABOS DE MONITORIZAÇÃO DESCONECTADOS" });
      return list;
    }

    if (vitals.rhythm === "VENTRICULAR_FIBRILLATION") {
      list.push({ id: "vf", level: "red", message: "🚨 FIBRILAÇÃO VENTRICULAR / PCR" });
    } else if (vitals.rhythm === "VENTRICULAR_TACHYCARDIA") {
      list.push({ id: "tv", level: "red", message: "🚨 TAQUICARDIA VENTRICULAR MONOMÓRFICA" });
    } else if (vitals.sbp <= 0 || vitals.hr <= 35) {
      list.push({ id: "arrest", level: "red", message: "🚨 COLAPSO HEMODINÂMICO / AESP" });
    } else if (vitals.sbp < 75) {
      list.push({ id: "hypotension", level: "red", message: `🚨 HIPOTENSÃO CRÍTICA (PAS ${vitals.sbp} mmHg)` });
    } else if (vitals.spo2 < 85) {
      list.push({ id: "hypoxemia", level: "red", message: `🚨 HIPOXEMIA SEVERA (SpO2 ${vitals.spo2}%)` });
    } else if (vitals.hr > 150) {
      list.push({ id: "tachycardia", level: "yellow", message: `TAQUICARDIA SEVERA (${vitals.hr} bpm)` });
    }

    return list;
  }, [vitals, isMonitored]);

  return {
    vitals,
    isMonitored,
    displayedNibp,
    isMeasuringNibp,
    interventions,
    iatrogenicAlerts,
    activeAlarms,
    isAlarmSilenced,
    isAudioMuted,
    vitalsHistory,
    measureNibp,
    connectSensors,
    silenceAlarms,
    toggleAudio,
    applyIntervention,
    executeCardioversion,
  };
}
