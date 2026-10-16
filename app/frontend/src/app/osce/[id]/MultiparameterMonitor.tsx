"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { 
  Heart, Activity, Volume2, VolumeX, BellOff, 
  RefreshCw, Radio, ShieldAlert, Zap, AlertTriangle
} from "lucide-react";
import { OscePhysiologyVitals } from "@/types/api";
import { DisplayedNibp, VitalAlarm } from "./useVitalStateEngine";

interface MultiparameterMonitorProps {
  vitals: OscePhysiologyVitals;
  isMonitored: {
    ecg: boolean;
    spo2: boolean;
    nibp: boolean;
    capno: boolean;
  };
  displayedNibp: DisplayedNibp | null;
  isMeasuringNibp: boolean;
  activeAlarms: VitalAlarm[];
  isAlarmSilenced: boolean;
  isAudioMuted: boolean;
  onMeasureNibp: () => void;
  onConnectSensors: () => void;
  onSilenceAlarms: () => void;
  onToggleAudio: () => void;
  onExecuteCardioversion?: (sync: boolean, joules: number) => void;
}

export function MultiparameterMonitor({
  vitals,
  isMonitored,
  displayedNibp,
  isMeasuringNibp,
  activeAlarms,
  isAlarmSilenced,
  isAudioMuted,
  onMeasureNibp,
  onConnectSensors,
  onSilenceAlarms,
  onToggleAudio,
  onExecuteCardioversion,
}: MultiparameterMonitorProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const lastBeepTimeRef = useRef<number>(0);
  const [pulseGlow, setPulseGlow] = useState(false);
  const [showDefibModal, setShowDefibModal] = useState(false);
  const [defibSync, setDefibSync] = useState(true);
  const [defibJoules, setDefibJoules] = useState(100);

  // Inicializa Web Audio API de forma segura
  const getAudioContext = useCallback((): AudioContext | null => {
    if (typeof window === "undefined") return null;
    if (!audioCtxRef.current) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        audioCtxRef.current = new AudioCtx();
      }
    }
    if (audioCtxRef.current && audioCtxRef.current.state === "suspended") {
      audioCtxRef.current.resume().catch(() => {});
    }
    return audioCtxRef.current;
  }, []);

  // Sintetizador do Bip do QRS modulado por SpO2
  const playQrsBeep = useCallback((spo2Val: number) => {
    if (isAudioMuted) return;
    try {
      const ctx = getAudioContext();
      if (!ctx || ctx.state !== "running") return;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      // Fórmula psicoacústica de saturação: tom cai quando desnatura
      const freq = Math.min(800, Math.max(220, 440 + (spo2Val - 80) * 18));
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      osc.type = "sine";

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.06);
    } catch {
      // AudioContext bloqueado pelo navegador até o primeiro clique
    }
  }, [isAudioMuted, getAudioContext]);

  // Sintetizador de Alarme IEC (Sequência de 5 bips para alarme vermelho)
  const playAlarmTone = useCallback(() => {
    if (isAudioMuted || isAlarmSilenced) return;
    try {
      const ctx = getAudioContext();
      if (!ctx || ctx.state !== "running") return;

      const now = ctx.currentTime;
      [0, 0.12, 0.24, 0.44, 0.56].forEach((offset) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.frequency.setValueAtTime(880, now + offset);
        gain.gain.setValueAtTime(0.12, now + offset);
        gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.08);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now + offset);
        osc.stop(now + offset + 0.08);
      });
    } catch {
      // Ignora erro de áudio
    }
  }, [isAudioMuted, isAlarmSilenced, getAudioContext]);

  // Alarme sonoro periódico se houver alarme vermelho ativo
  useEffect(() => {
    const hasRedAlarm = activeAlarms.some((a) => a.level === "red");
    if (!hasRedAlarm || isAlarmSilenced || isAudioMuted) return;

    const interval = setInterval(() => {
      playAlarmTone();
    }, 4500);

    return () => clearInterval(interval);
  }, [activeAlarms, isAlarmSilenced, isAudioMuted, playAlarmTone]);

  // Loop de Renderização das Ondas no Canvas a 60 FPS
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let sweepX = 0;
    const speed = 2.4; // velocidade do feixe

    // Estado interno da onda de ECG
    let ecgPhase = 0;
    let plethPhase = 0;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;

      // Zonas verticais do canvas: Canal 1 (ECG: 0 a 55%), Canal 2 (Pleth: 55 a 85%), Canal 3 (EtCO2: 85 a 100%)
      const ecgMidY = height * 0.28;
      const ecgAmp = height * 0.22;

      const plethMidY = height * 0.72;
      const plethAmp = height * 0.18;

      // Apaga a fatia à frente da barra de varredura (efeito phosphor decay)
      const clearWidth = 24;
      ctx.fillStyle = "#070b12";
      ctx.fillRect(sweepX, 0, clearWidth, height);

      // Traça linha guia sutil de fundo
      ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(sweepX, ecgMidY);
      ctx.lineTo(sweepX + speed, ecgMidY);
      ctx.moveTo(sweepX, plethMidY);
      ctx.lineTo(sweepX + speed, plethMidY);
      ctx.stroke();

      // =========================================================================
      // CANAL 1: ONDA DE ECG DII (Verde #22c55e)
      // =========================================================================
      if (isMonitored.ecg) {
        ctx.strokeStyle = "#22c55e";
        ctx.lineWidth = 2.2;
        ctx.lineJoin = "round";

        const hr = Math.max(20, Math.min(260, vitals.hr));
        const beatsPerSec = hr / 60;
        const cycleLength = (60 / beatsPerSec) * (60 / speed); // duração do ciclo em pixels

        ecgPhase = (ecgPhase + speed) % cycleLength;
        const normalizedCycle = ecgPhase / cycleLength; // 0.0 a 1.0

        let ecgOffset = 0;
        const rhythm = vitals.rhythm;

        if (rhythm === "VENTRICULAR_FIBRILLATION") {
          // Caos fibrilatório irregular
          ecgOffset = Math.sin(sweepX * 0.18) * 0.6 + Math.sin(sweepX * 0.35) * 0.35 + (Math.random() - 0.5) * 0.4;
        } else if (rhythm === "VENTRICULAR_TACHYCARDIA") {
          // Ondas sinusóides largas sem P
          const tvPhase = (sweepX * 0.15) % (Math.PI * 2);
          ecgOffset = Math.sin(tvPhase) * 1.1 + Math.sin(tvPhase * 2) * 0.25;
        } else if (rhythm === "ASYSTOLE" || vitals.hr <= 20) {
          // Linha isoelétrica com mínimo ruído
          ecgOffset = (Math.random() - 0.5) * 0.04;
        } else {
          // Traçado com complexo QRS procedural preciso
          if (normalizedCycle < 0.12) {
            // Onda P
            ecgOffset = Math.sin((normalizedCycle / 0.12) * Math.PI) * 0.18;
          } else if (normalizedCycle >= 0.12 && normalizedCycle < 0.18) {
            // Segmento PR isoelétrico
            ecgOffset = 0;
          } else if (normalizedCycle >= 0.18 && normalizedCycle < 0.21) {
            // Onda Q (descida)
            ecgOffset = -0.15;
          } else if (normalizedCycle >= 0.21 && normalizedCycle < 0.25) {
            // Onda R (pico agudo)
            ecgOffset = 1.35;
            // Gatilho do Bip Sonoro no pico do QRS
            const now = Date.now();
            if (now - lastBeepTimeRef.current > (50 / hr) * 1000) {
              lastBeepTimeRef.current = now;
              playQrsBeep(vitals.spo2);
              setPulseGlow(true);
              setTimeout(() => setPulseGlow(false), 90);
            }
          } else if (normalizedCycle >= 0.25 && normalizedCycle < 0.28) {
            // Onda S (descida)
            ecgOffset = -0.35;
          } else if (normalizedCycle >= 0.28 && normalizedCycle < 0.38) {
            // Segmento ST
            ecgOffset = 0.02;
          } else if (normalizedCycle >= 0.38 && normalizedCycle < 0.55) {
            // Onda T
            ecgOffset = Math.sin(((normalizedCycle - 0.38) / 0.17) * Math.PI) * 0.32;
          } else {
            // Linha de base diastólica
            ecgOffset = 0;
          }
        }

        const yEcg = ecgMidY - ecgOffset * ecgAmp;
        ctx.beginPath();
        ctx.moveTo(sweepX, yEcg);
        ctx.lineTo(sweepX + speed, yEcg);
        ctx.stroke();
      } else {
        // Derivação desconectada (linha tracejada sutil)
        ctx.strokeStyle = "rgba(34, 197, 94, 0.3)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(sweepX, ecgMidY);
        ctx.lineTo(sweepX + speed, ecgMidY);
        ctx.stroke();
      }

      // =========================================================================
      // CANAL 2: ONDA DE OXIMETRIA / PLETH (Ciano #06b6d4)
      // =========================================================================
      if (isMonitored.spo2) {
        ctx.strokeStyle = "#06b6d4";
        ctx.lineWidth = 2.0;

        const hr = Math.max(30, Math.min(220, vitals.hr));
        const beatsPerSec = hr / 60;
        const cycleLength = (60 / beatsPerSec) * (60 / speed);

        plethPhase = (plethPhase + speed) % cycleLength;
        const normPleth = plethPhase / cycleLength;

        let plethOffset = 0;
        if (normPleth < 0.28) {
          // Subida sistólica rápida
          plethOffset = Math.sin((normPleth / 0.28) * (Math.PI / 2));
        } else if (normPleth >= 0.28 && normPleth < 0.42) {
          // Descida inicial
          plethOffset = 1.0 - (normPleth - 0.28) * 3.5;
        } else if (normPleth >= 0.42 && normPleth < 0.52) {
          // Incisura dicrótica (onda secundária)
          plethOffset = 0.5 + Math.sin(((normPleth - 0.42) / 0.1) * Math.PI) * 0.18;
        } else {
          // Decaimento diastólico
          plethOffset = Math.max(0, 0.5 - (normPleth - 0.52) * 1.1);
        }

        // Modula pela perfusão periférica
        const perfusionScale = Math.min(1.0, Math.max(0.2, (vitals.sbp - 40) / 80));
        const yPleth = plethMidY - plethOffset * plethAmp * perfusionScale;

        ctx.beginPath();
        ctx.moveTo(sweepX, yPleth);
        ctx.lineTo(sweepX + speed, yPleth);
        ctx.stroke();
      } else {
        ctx.strokeStyle = "rgba(6, 182, 212, 0.3)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(sweepX, plethMidY);
        ctx.lineTo(sweepX + speed, plethMidY);
        ctx.stroke();
      }

      // Avança a barra de varredura
      sweepX = (sweepX + speed) % width;
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [vitals, isMonitored, playQrsBeep]);

  // Label do Ritmo Eletrocardiográfico
  const rhythmLabel = {
    NORMAL_SINUS: "RITMO SINUSAL",
    SINUS_TACHYCARDIA: "TAQUICARDIA SINUSAL",
    SINUS_BRADYCARDIA: "BRADICARDIA SINUSAL",
    UNSTABLE_SVT: "TAQUI SUPRAVENTRICULAR",
    VENTRICULAR_TACHYCARDIA: "TAQUI VENTRICULAR (TV)",
    VENTRICULAR_FIBRILLATION: "FIBRILAÇÃO VENTRICULAR (FV)",
    AFIB: "FIBRILAÇÃO ATRIAL",
    PEA: "AESP / DISSOCIAÇÃO",
    ASYSTOLE: "ASSISTOLIA",
  }[vitals.rhythm] || "RITMO INDEFINIDO";

  const hasCriticalAlarm = activeAlarms.some((a) => a.level === "red");

  return (
    <div className="rounded-2xl border-2 border-border/80 bg-[#070b12] text-white shadow-2xl overflow-hidden flex flex-col font-mono select-none">
      {/* Barra de Status Superior do Monitor */}
      <div className="px-3 py-2 bg-[#0d1424] border-b border-border/40 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 font-bold tracking-wider text-emerald-400">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            SALA VERMELHA • LEITO 01
          </span>
          <span className="text-muted-foreground text-[11px] hidden sm:inline">
            Modo: Adulto Emergência
          </span>
        </div>

        {/* Banner Central de Alarmes Ativos */}
        <div className="flex-1 max-w-md mx-3">
          {activeAlarms.length > 0 ? (
            <div
              className={`px-3 py-1 rounded-lg text-xs font-bold text-center flex items-center justify-center gap-2 truncate ${
                hasCriticalAlarm
                  ? "bg-rose-950 text-rose-300 border border-rose-700 animate-pulse"
                  : "bg-amber-950 text-amber-300 border border-amber-700"
              }`}
            >
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span className="truncate">{activeAlarms[0].message}</span>
              {activeAlarms.length > 1 && (
                <span className="text-[10px] opacity-75">+{activeAlarms.length - 1}</span>
              )}
            </div>
          ) : (
            <div className="px-3 py-1 rounded-lg bg-emerald-950/40 text-emerald-400 border border-emerald-900/40 text-center text-[11px]">
              SINAIS FISIOLÓGICOS ESTÁVEIS
            </div>
          )}
        </div>

        {/* Controles do Monitor */}
        <div className="flex items-center gap-2">
          {!isMonitored.ecg && (
            <button
              onClick={onConnectSensors}
              className="px-2.5 py-1 rounded-lg bg-primary text-primary-foreground text-[11px] font-bold hover:bg-primary/90 flex items-center gap-1 transition-transform active:scale-95 cursor-pointer shadow"
            >
              <Activity className="w-3.5 h-3.5" />
              Monitorizar
            </button>
          )}

          <button
            onClick={onSilenceAlarms}
            title={isAlarmSilenced ? "Alarmes silenciados" : "Silenciar alarmes por 2 minutos"}
            className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
              isAlarmSilenced
                ? "bg-amber-500/20 text-amber-400 border-amber-500"
                : "bg-muted/30 text-muted-foreground border-border/40 hover:text-white"
            }`}
          >
            <BellOff className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onToggleAudio}
            title={isAudioMuted ? "Ativar som dos bips" : "Mutar bips"}
            className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
              isAudioMuted
                ? "bg-rose-500/20 text-rose-400 border-rose-500"
                : "bg-muted/30 text-emerald-400 border-border/40 hover:text-white"
            }`}
          >
            {isAudioMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>

          {/* Botão de Cardioversor de Emergência */}
          {onExecuteCardioversion && (
            <button
              onClick={() => setShowDefibModal(true)}
              className="px-2.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-[11px] flex items-center gap-1 transition-transform active:scale-95 shadow cursor-pointer"
            >
              <Zap className="w-3.5 h-3.5 fill-current" />
              Cardioversor
            </button>
          )}
        </div>
      </div>

      {/* Grid Central: Canvas de Ondas (Esq) + Painéis Numéricos de Parâmetros (Dir) */}
      <div className="grid grid-cols-12 gap-0 min-h-[220px]">
        {/* Painel Esquerdo: Ondas de ECG Contínuo e Oximetria (7 cols) */}
        <div className="col-span-12 lg:col-span-7 p-2.5 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-border/30 relative">
          {/* Legenda de Ondas no Topo */}
          <div className="flex items-center justify-between text-[11px] mb-1 px-1">
            <div className="flex items-center gap-2 text-emerald-400 font-bold">
              <span>ECG: DII</span>
              <span className="text-[10px] text-emerald-300/80 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-900/60">
                {rhythmLabel}
              </span>
            </div>
            <div className="text-cyan-400 font-bold flex items-center gap-2">
              <span>SpO2 Pleth</span>
              <span className="text-[10px] text-cyan-300/80 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-900/60">
                PI: {vitals.perfusion_index?.toFixed(1) || "1.8"}%
              </span>
            </div>
          </div>

          {/* Canvas HTML5 de Alta Precisão */}
          <div className="flex-1 w-full relative min-h-[160px] bg-[#05080f] rounded-xl border border-border/30 overflow-hidden shadow-inner">
            <canvas
              ref={canvasRef}
              width={560}
              height={200}
              className="w-full h-full block"
            />

            {!isMonitored.ecg && (
              <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center text-xs text-amber-300 font-bold flex-col gap-1.5">
                <AlertTriangle className="w-5 h-5 text-amber-400 animate-pulse" />
                <span>MONITOR CARDÍACO DESCONECTADO</span>
                <span className="text-[10px] text-muted-foreground font-normal">
                  Clique em &ldquo;Monitorizar&rdquo; ou solicite por comando de voz
                </span>
              </div>
            )}
          </div>

          {/* Rodapé do Traçado: Velocidade da Onda */}
          <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1.5 px-1">
            <span>Velocidade: 25 mm/s</span>
            <span>Ganho: N (10 mm/mV)</span>
            <span>Filtro: Monitor (0.5 - 40 Hz)</span>
          </div>
        </div>

        {/* Painel Direito: Caixas de Valores Digitais (5 cols) */}
        <div className="col-span-12 lg:col-span-5 grid grid-cols-2 gap-2 p-2.5 bg-[#090d18]">
          {/* Tile 1: Frequência Cardíaca (Verde) */}
          <div
            className={`p-2.5 rounded-sm border transition-all flex flex-col justify-between ${
              pulseGlow
                ? "bg-emerald-950/60 border-emerald-400 shadow-sm ring-1 ring-emerald-500/30"
                : "bg-[#0b1220] border-emerald-900/40"
            }`}
          >
            <div className="flex items-center justify-between text-xs text-emerald-400">
              <span className="font-bold font-mono-lab flex items-center gap-1 uppercase tracking-wider text-[11px]">
                <Heart className={`w-3.5 h-3.5 ${pulseGlow ? "scale-110 text-emerald-300 fill-emerald-300" : ""}`} />
                FC
              </span>
              <span className="text-[10px] text-emerald-400/70 font-mono-lab tabular-nums">50 - 120</span>
            </div>
            <div className="my-1 flex items-baseline justify-between">
              <span className="text-3xl lg:text-4xl font-extrabold text-emerald-400 font-mono-lab tabular-nums tracking-tighter">
                {isMonitored.ecg ? vitals.hr : "--"}
              </span>
              <span className="text-[11px] text-emerald-400/80 font-mono-lab font-bold">bpm</span>
            </div>
            <span className="text-[10px] text-emerald-400/70 truncate font-mono-lab">DII Contínuo</span>
          </div>

          {/* Tile 2: Oximetria de Pulso SpO2 (Ciano) */}
          <div className="p-2.5 rounded-sm bg-[#0b1220] border border-cyan-900/40 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-cyan-400">
              <span className="font-bold font-mono-lab uppercase tracking-wider text-[11px]">SpO2</span>
              <span className="text-[10px] text-cyan-400/70 font-mono-lab tabular-nums">92 - 100</span>
            </div>
            <div className="my-1 flex items-baseline justify-between">
              <span
                className={`text-3xl lg:text-4xl font-extrabold font-mono-lab tabular-nums tracking-tighter ${
                  vitals.spo2 < 90 ? "text-rose-400 animate-pulse" : "text-cyan-400"
                }`}
              >
                {isMonitored.spo2 ? vitals.spo2 : "--"}
              </span>
              <span className="text-[11px] text-cyan-400/80 font-mono-lab font-bold">%</span>
            </div>
            <span className="text-[10px] text-cyan-400/70 truncate font-mono-lab">Sensor Digital</span>
          </div>

          {/* Tile 3: Pressão Arterial Não-Invasiva PNI (Branco / Âmbar) */}
          <div className="p-2.5 rounded-sm bg-[#0b1220] border border-border/50 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-zinc-300">
              <span className="font-bold font-mono-lab uppercase tracking-wider text-[11px]">PNI (PA)</span>
              <button
                onClick={onMeasureNibp}
                disabled={isMeasuringNibp}
                className="text-[10px] font-mono-lab text-accent hover:underline flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw className={`w-2.5 h-2.5 ${isMeasuringNibp ? "animate-spin" : ""}`} />
                {isMeasuringNibp ? "Insufl..." : "Aferir"}
              </button>
            </div>
            <div className="my-1 flex items-baseline justify-between">
              {displayedNibp ? (
                <div className="flex items-baseline gap-1">
                  <span className="text-xl lg:text-2xl font-extrabold text-white font-mono-lab tabular-nums tracking-tighter">
                    {displayedNibp.sbp}/{displayedNibp.dbp}
                  </span>
                  <span className="text-[11px] text-muted-foreground font-mono-lab">({displayedNibp.pam})</span>
                </div>
              ) : (
                <span className="text-xl font-bold text-muted-foreground font-mono-lab tabular-nums">
                  {isMeasuringNibp ? "Insufl..." : "--/--"}
                </span>
              )}
              <span className="text-[10px] text-muted-foreground font-mono-lab">mmHg</span>
            </div>
            <span className="text-[10px] text-muted-foreground truncate font-mono-lab">
              {displayedNibp ? "Manguito Braquial" : "Aguardando aferição"}
            </span>
          </div>

          {/* Tile 4: Frequência Respiratória / Capnografia (Amarelo) */}
          <div className="p-2.5 rounded-sm bg-[#0b1220] border border-amber-900/40 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-amber-400">
              <span className="font-bold font-mono-lab uppercase tracking-wider text-[11px]">FR & EtCO2</span>
              <span className="text-[10px] text-amber-400/70 font-mono-lab tabular-nums">12 - 20</span>
            </div>
            <div className="my-1 flex items-baseline justify-between">
              <div className="flex items-baseline gap-1">
                <span className="text-2xl lg:text-3xl font-extrabold text-amber-400 font-mono-lab tabular-nums tracking-tighter">
                  {vitals.rr}
                </span>
                <span className="text-[10px] text-amber-300/80 font-mono-lab">irpm</span>
              </div>
              <span className="text-[11px] font-bold text-amber-300 font-mono-lab tabular-nums">
                {vitals.etco2 || 36} <span className="text-[9px] font-normal">mmHg</span>
              </span>
            </div>
            <span className="text-[10px] text-amber-400/70 truncate font-mono-lab">
              {vitals.gcs ? `Glasgow: ${vitals.gcs}` : "Capnografia Beira-Leito"}
            </span>
          </div>
        </div>
      </div>

      {/* Modal Tático de Cardioversor / Desfibrilador de Emergência */}
      {showDefibModal && onExecuteCardioversion && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
          <div className="max-w-md w-full bg-[#0d1424] border-2 border-rose-600 rounded-2xl p-5 shadow-2xl space-y-4 font-sans text-white">
            <div className="flex items-center justify-between border-b border-border/40 pb-3">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-base">
                <Zap className="w-5 h-5 fill-current" />
                Desfibrilador / Cardioversor Manual
              </div>
              <button
                onClick={() => setShowDefibModal(false)}
                className="text-muted-foreground hover:text-white text-xs px-2 py-1 rounded bg-muted/30 cursor-pointer"
              >
                ✕ Fechar
              </button>
            </div>

            <div className="p-3 rounded-xl bg-muted/20 border border-border/50 text-xs space-y-1 font-mono">
              <div>Ritmo Monitorado: <span className="font-bold text-emerald-400">{rhythmLabel}</span></div>
              <div>FC: <span className="font-bold text-emerald-400">{vitals.hr} bpm</span> • PA: <span className="font-bold text-white">{vitals.sbp}/{vitals.dbp} mmHg</span></div>
            </div>

            {/* Controle de Sincronismo */}
            <div className="space-y-1.5 text-xs">
              <label className="font-bold text-foreground flex items-center justify-between">
                <span>Modo de Disparo:</span>
                <span className={defibSync ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                  {defibSync ? "SINCRONIZADO (Onda R)" : "DESINCRO / DESFIBRILAÇÃO"}
                </span>
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setDefibSync(true)}
                  className={`p-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                    defibSync
                      ? "bg-emerald-600 text-white border-emerald-500 shadow-md ring-2 ring-emerald-500/30"
                      : "bg-muted/30 text-muted-foreground border-border/40 hover:bg-muted/50"
                  }`}
                >
                  SINCRONIZAR (TV c/ pulso)
                </button>
                <button
                  type="button"
                  onClick={() => setDefibSync(false)}
                  className={`p-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                    !defibSync
                      ? "bg-rose-600 text-white border-rose-500 shadow-md ring-2 ring-rose-500/30"
                      : "bg-muted/30 text-muted-foreground border-border/40 hover:bg-muted/50"
                  }`}
                >
                  DESINCRO (FV / TV s/ pulso)
                </button>
              </div>
            </div>

            {/* Carga em Joules */}
            <div className="space-y-1.5 text-xs">
              <label className="font-bold text-foreground">Selecionar Carga (Bifásico):</label>
              <div className="grid grid-cols-4 gap-2 font-mono">
                {[50, 100, 150, 200].map((j) => (
                  <button
                    key={j}
                    type="button"
                    onClick={() => setDefibJoules(j)}
                    className={`py-2 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                      defibJoules === j
                        ? "bg-primary text-primary-foreground border-primary shadow"
                        : "bg-muted/30 text-muted-foreground border-border/40 hover:bg-muted/50"
                    }`}
                  >
                    {j} J
                  </button>
                ))}
              </div>
            </div>

            {/* Botão de Disparo */}
            <div className="pt-2">
              <button
                type="button"
                onClick={() => {
                  onExecuteCardioversion(defibSync, defibJoules);
                  setShowDefibModal(false);
                }}
                className="w-full py-3 rounded-xl bg-rose-600 hover:bg-rose-500 active:scale-98 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg shadow-rose-950/60 cursor-pointer"
              >
                <Zap className="w-4 h-4 fill-current" />
                AFASTAR EQUIPE E DISPARAR CHOQUE ({defibJoules}J)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
