"use client";

import React, { useState } from "react";
import { 
  Radio, Zap, CheckCircle2, 
  Sparkles, Crosshair, ChevronRight
} from "lucide-react";
import { OsceSpokenQueueItem, OsceLiveFeedback } from "@/types/api";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";

interface ProcedureMannequinProps {
  sessionId: string;
  elapsedSeconds: number;
  onProcedureExecuted: (
    title: string, 
    findings: string, 
    examinerMessage: string, 
    spokenQueue: OsceSpokenQueueItem[],
    guidedFeedback?: OsceLiveFeedback
  ) => void;
  isLoading?: boolean;
}

export function ProcedureMannequin({
  sessionId,
  elapsedSeconds,
  onProcedureExecuted,
  isLoading = false
}: ProcedureMannequinProps) {
  const [activeMode, setActiveMode] = useState<"efast" | "invasive">("efast");
  const [activeSite, setActiveSite] = useState<string | null>(null);
  const [lastFinding, setLastFinding] = useState<{ title: string; desc: string; site: string } | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Executa procedimento no backend
  const handlePerformAction = async (procType: string, siteKey: string, siteLabel: string) => {
    if (isProcessing || isLoading) return;
    setIsProcessing(true);
    setActiveSite(siteKey);

    try {
      const res = await api.osce.performProcedure(sessionId, procType, siteKey, elapsedSeconds);
      if (res?.success) {
        setLastFinding({
          title: siteLabel,
          desc: res.findings,
          site: siteKey
        });
        toast.success(`Procedimento realizado: ${siteLabel}`);
        onProcedureExecuted(siteLabel, res.findings, res.examiner_message, res.spoken_queue || [], res.guided_feedback);
      }
    } catch {
      toast.error("Erro ao registrar procedimento beira-leito.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      {/* Seletor de Modo do Manequim */}
      <div className="flex rounded-xl bg-muted/40 p-1 border border-border">
        <button
          type="button"
          onClick={() => setActiveMode("efast")}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
            activeMode === "efast"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Radio className="w-3.5 h-3.5" />
          <span>Ultrassom E-FAST (POCUS Trauma)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveMode("invasive")}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
            activeMode === "invasive"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>Punções & Descompressão Beira-Leito</span>
        </button>
      </div>

      {/* Grid Principal: Manequim SVG Anatômico (Esquerda) + Janela de Laudo/Achados (Direita) */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-start">
        {/* Coluna do Manequim 2D (7 cols) */}
        <div className="md:col-span-7 p-3 rounded-2xl bg-card border border-border flex flex-col items-center justify-center relative overflow-hidden min-h-[360px]">
          <div className="absolute top-2 left-3 flex items-center gap-1.5 text-[10px] text-muted-foreground font-mono">
            <Crosshair className="w-3 h-3 text-primary animate-pulse" />
            <span>Manequim Beira-Leito 2D (Decúbito Dorsal)</span>
          </div>

          {/* SVG do Corpo Humano Estilizado */}
          <div className="relative w-48 h-80 my-2 select-none">
            <svg
              viewBox="0 0 200 360"
              className="w-full h-full drop-shadow-md text-muted-foreground/30 fill-current"
            >
              {/* Cabeça */}
              <circle cx="100" cy="35" r="24" className="fill-muted/60 stroke-border stroke-2" />
              {/* Pescoço */}
              <rect x="92" y="58" width="16" height="15" rx="3" className="fill-muted/60 stroke-border stroke-2" />
              {/* Tronco */}
              <path
                d="M 60 75 C 60 75, 45 100, 48 160 C 50 190, 65 215, 65 215 L 135 215 C 135 215, 150 190, 152 160 C 155 100, 140 75, 140 75 Z"
                className="fill-muted/50 stroke-border stroke-2"
              />
              {/* Clavículas */}
              <line x1="68" y1="78" x2="94" y2="82" className="stroke-border stroke-2" />
              <line x1="132" y1="78" x2="106" y2="82" className="stroke-border stroke-2" />
              {/* Braço Direito */}
              <path d="M 52 82 C 30 115, 25 160, 20 195 L 34 198 C 38 165, 44 125, 60 92 Z" className="fill-muted/40 stroke-border stroke-2" />
              {/* Braço Esquerdo */}
              <path d="M 148 82 C 170 115, 175 160, 180 195 L 166 198 C 162 165, 156 125, 140 92 Z" className="fill-muted/40 stroke-border stroke-2" />
              {/* Pelve */}
              <path d="M 65 215 L 135 215 L 128 245 L 72 245 Z" className="fill-muted/60 stroke-border stroke-2" />
              {/* Membros Inferiores */}
              <rect x="68" y="245" width="28" height="105" rx="10" className="fill-muted/50 stroke-border stroke-2" />
              <rect x="104" y="245" width="28" height="105" rx="10" className="fill-muted/50 stroke-border stroke-2" />
            </svg>

            {/* ========================================================================= */}
            {/* OVERLAY DE PONTOS ANATÔMICOS: MODO E-FAST */}
            {/* ========================================================================= */}
            {activeMode === "efast" && (
              <>
                {/* 1. Janela Pericárdica / Subxifoide */}
                <button
                  type="button"
                  title="Janela Subxifoide / Pericárdica (Descarte de Tamponamento)"
                  onClick={() => handlePerformAction("efast", "pericardial", "Janela Subxifoide (Pericárdica)")}
                  className={`absolute top-[130px] left-[92px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "pericardial"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-primary/80 hover:bg-primary text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-white animate-ping"></span>
                </button>

                {/* 2. Janela Hepatorrenal (Espaço de Morrison) - Hipocôndrio Direito */}
                <button
                  type="button"
                  title="Janela Hepatorrenal (Morrison) - Hipocôndrio Direito"
                  onClick={() => handlePerformAction("efast", "morrison", "Janela Hepatorrenal (Morrison)")}
                  className={`absolute top-[145px] left-[66px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "morrison"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-emerald-500/80 hover:bg-emerald-500 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-white"></span>
                </button>

                {/* 3. Janela Esplenorrenal (Recesso de Koller) - Hipocôndrio Esquerdo */}
                <button
                  type="button"
                  title="Janela Esplenorrenal (Koller) - Hipocôndrio Esquerdo"
                  onClick={() => handlePerformAction("efast", "splenorenal", "Janela Esplenorrenal (Koller)")}
                  className={`absolute top-[145px] left-[132px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "splenorenal"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-emerald-500/80 hover:bg-emerald-500 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-white"></span>
                </button>

                {/* 4. Janela Pélvica / Suprapúbica */}
                <button
                  type="button"
                  title="Janela Pélvica / Suprapúbica"
                  onClick={() => handlePerformAction("efast", "pelvic", "Janela Pélvica (Suprapúbica)")}
                  className={`absolute top-[198px] left-[98px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "pelvic"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-blue-500/80 hover:bg-blue-500 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-white"></span>
                </button>

                {/* 5. E-FAST Pleural Direito */}
                <button
                  type="button"
                  title="E-FAST Pulmonar Direito (Lung Sliding / Pneumotórax)"
                  onClick={() => handlePerformAction("efast", "pleural_right", "E-FAST Pleural Direito")}
                  className={`absolute top-[100px] left-[74px] -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "pleural_right"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-violet-500/80 hover:bg-violet-500 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
                </button>

                {/* 6. E-FAST Pleural Esquerdo */}
                <button
                  type="button"
                  title="E-FAST Pulmonar Esquerdo (Lung Sliding / Pneumotórax)"
                  onClick={() => handlePerformAction("efast", "pleural_left", "E-FAST Pleural Esquerdo")}
                  className={`absolute top-[100px] left-[122px] -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "pleural_left"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-violet-500/80 hover:bg-violet-500 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
                </button>
              </>
            )}

            {/* ========================================================================= */}
            {/* OVERLAY DE PONTOS ANATÔMICOS: PUNÇÕES E PROCEDIMENTOS INVASIVOS */}
            {/* ========================================================================= */}
            {activeMode === "invasive" && (
              <>
                {/* 1. Toracocentese de Alívio (2º EIC Linha Hemiclavicular Direita) */}
                <button
                  type="button"
                  title="Toracocentese de Alívio com Agulha (2º EIC)"
                  onClick={() => handlePerformAction("puncture", "thoracocentesis", "Toracocentese de Alívio (2º EIC)")}
                  className={`absolute top-[96px] left-[74px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "thoracocentesis"
                      ? "bg-rose-500 text-white ring-4 ring-rose-500/40 scale-125 z-10"
                      : "bg-rose-500/80 hover:bg-rose-600 text-white hover:scale-110 shadow-sm animate-pulse"
                  }`}
                >
                  <span className="text-[10px] font-black">2º</span>
                </button>

                {/* 2. Drenagem Torácica Fechada em Selo D'água (5º EIC Linha Axilar Média) */}
                <button
                  type="button"
                  title="Drenagem Torácica Fechada em Selo D'água (5º EIC)"
                  onClick={() => handlePerformAction("drainage", "chest_tube", "Drenagem Torácica (5º EIC)")}
                  className={`absolute top-[138px] left-[52px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "chest_tube"
                      ? "bg-rose-500 text-white ring-4 ring-rose-500/40 scale-125 z-10"
                      : "bg-rose-500/80 hover:bg-rose-600 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="text-[10px] font-black">5º</span>
                </button>

                {/* 3. Acesso Venoso Central (Subclávia Infraclavicular Direita) */}
                <button
                  type="button"
                  title="Acesso Venoso Central (Subclávia / Jugular)"
                  onClick={() => handlePerformAction("vascular", "central_vein", "Acesso Venoso Central")}
                  className={`absolute top-[78px] left-[80px] -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "central_vein"
                      ? "bg-blue-500 text-white ring-4 ring-blue-500/40 scale-125 z-10"
                      : "bg-blue-500/80 hover:bg-blue-600 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
                </button>

                {/* 4. Punção Intraóssea (Tíbia Proximal) */}
                <button
                  type="button"
                  title="Punção Intraóssea de Emergência (Tíbia Proximal)"
                  onClick={() => handlePerformAction("vascular", "intraosseous", "Punção Intraóssea (Tíbia)")}
                  className={`absolute top-[280px] left-[82px] -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "intraosseous"
                      ? "bg-amber-500 text-white ring-4 ring-amber-500/40 scale-125 z-10"
                      : "bg-amber-500/80 hover:bg-amber-600 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
                </button>

                {/* 5. Manobra de Hamilton (Compressão Uterina Bimanual) */}
                <button
                  type="button"
                  title="Compressão Uterina Bimanual (Manobra de Hamilton na HPP)"
                  onClick={() => handlePerformAction("maneuver", "hamilton", "Manobra de Hamilton (Atonia Uterina)")}
                  className={`absolute top-[215px] left-[98px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "hamilton"
                      ? "bg-violet-500 text-white ring-4 ring-violet-500/40 scale-125 z-10"
                      : "bg-violet-500/80 hover:bg-violet-600 text-white hover:scale-110 shadow-sm"
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-white"></span>
                </button>

                {/* 6. Cardioversão Elétrica Sincronizada */}
                <button
                  type="button"
                  title="Cardioversão Elétrica Sincronizada 100J (Pás Cardíacas)"
                  onClick={() => handlePerformAction("cardioversion", "cardioversion", "Cardioversão Elétrica (100J)")}
                  className={`absolute top-[115px] left-[118px] -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                    activeSite === "cardioversion"
                      ? "bg-yellow-500 text-black ring-4 ring-yellow-500/40 scale-125 z-10"
                      : "bg-yellow-500/90 hover:bg-yellow-500 text-black hover:scale-110 shadow-sm"
                  }`}
                >
                  <Zap className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>

          <div className="text-[10px] text-muted-foreground/80 mt-1 italic text-center">
            {activeMode === "efast" 
              ? "Toque nos alvos circulares para posicionar o transdutor ultrassonográfico" 
              : "Toque nos sítios para realizar punção, drenagem ou manobras invasivas"}
          </div>
        </div>

        {/* Coluna de Laudo e Achados do Procedimento (5 cols) */}
        <div className="md:col-span-5 space-y-3">
          {/* Seletor rápido em lista */}
          <div className="p-3 rounded-xl border border-border bg-card space-y-2">
            <span className="text-[11px] font-bold text-foreground block">
              {activeMode === "efast" ? "Janelas E-FAST Disponíveis:" : "Procedimentos Rápidos:"}
            </span>

            {activeMode === "efast" ? (
              <div className="space-y-1 text-xs">
                <button
                  type="button"
                  onClick={() => handlePerformAction("efast", "morrison", "Janela Hepatorrenal (Morrison)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>1. Espaço Hepatorrenal (Morrison)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("efast", "splenorenal", "Janela Esplenorrenal (Koller)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>2. Espaço Esplenorrenal (Koller)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("efast", "pelvic", "Janela Pélvica (Suprapúbica)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>3. Janela Pélvica / Suprapúbica</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("efast", "pericardial", "Janela Subxifoide (Pericárdica)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>4. Janela Subxifoide (Pericárdio)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("efast", "pleural_right", "E-FAST Pleural Direito")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>5. E-FAST Pulmonar (Lung Sliding)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
              </div>
            ) : (
              <div className="space-y-1 text-xs">
                <button
                  type="button"
                  onClick={() => handlePerformAction("puncture", "thoracocentesis", "Toracocentese de Alívio (2º EIC)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>1. Toracocentese de Alívio (2º EIC)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("drainage", "chest_tube", "Drenagem Torácica Fechada (5º EIC)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>2. Drenagem Torácica (5º EIC)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("cardioversion", "cardioversion", "Cardioversão Elétrica Sincronizada")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>3. Cardioversão Elétrica Sincronizada</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("maneuver", "hamilton", "Manobra de Hamilton (Atonia Uterina)")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>4. Manobra Bimanual de Hamilton</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePerformAction("vascular", "intraosseous", "Punção Intraóssea na Tíbia")}
                  className="w-full p-2 rounded-lg text-left hover:bg-muted font-medium flex items-center justify-between border border-border/50 text-[11px]"
                >
                  <span>5. Punção Intraóssea (Tíbia)</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
              </div>
            )}
          </div>

          {/* Card de Visualização do Laudo / Achado Imediato */}
          {lastFinding ? (
            <div className="p-3.5 rounded-xl border-2 border-primary/30 bg-card space-y-2 animate-in fade-in">
              <div className="flex items-center justify-between border-b border-border pb-1.5">
                <span className="font-bold text-xs text-primary flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  {lastFinding.title}
                </span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                  {lastFinding.site}
                </span>
              </div>
              <p className="text-xs text-foreground/90 font-medium leading-relaxed">
                {lastFinding.desc}
              </p>
            </div>
          ) : (
            <div className="p-4 rounded-xl border border-dashed border-border text-center text-xs text-muted-foreground bg-muted/20">
              <Sparkles className="w-4 h-4 mx-auto mb-1 text-primary/60" />
              <span>Selecione uma janela de E-FAST ou procedimento no manequim para avaliar o resultado beira-leito.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
