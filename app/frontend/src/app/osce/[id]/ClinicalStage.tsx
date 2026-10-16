"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Stethoscope,
  Mic,
  UserCheck,
  ShieldAlert,
  ClipboardList,
  Volume2,
  VolumeX,
  Send,
} from "lucide-react";
import {
  stethoscopeEngine,
  AuscultationSoundType,
} from "./StethoscopeAudioEngine";
import { OsceTranscriptItem } from "@/types/api";

export interface AuscultationFocus {
  id: string;
  label: string; // Ex: "2º EIC Direito (Foco Aórtico)"
  x: number;     // Coordenada percentual no tórax (0-100)
  y: number;
  soundType: AuscultationSoundType;
}

interface ClinicalStageProps {
  station: {
    title: string;
    institution: string;
    patient_persona: {
      name?: string;
      age?: number | string;
      gender?: string;
      chief_complaint?: string;
    };
    auscultation_foci?: AuscultationFocus[];
  };
  vitals: {
    hr: number;
    sbp: number;
    dbp: number;
    rr: number;
    spo2: number;
    temp?: number;
    gcs?: number;
  };
  transcript: OsceTranscriptItem[];
  isLoading: boolean;
  onSendMessage: (text: string, target: "PATIENT" | "EXAMINER") => Promise<void>;
  isListening?: boolean;
  onToggleListening?: () => void;
  micPermission?: "granted" | "denied" | "prompt" | "unsupported";
}

export function ClinicalStage({
  station,
  vitals,
  transcript,
  isLoading,
  onSendMessage,
  isListening = false,
  onToggleListening,
  micPermission: _micPermission = "prompt",
}: ClinicalStageProps) {
  // Canal Tático de Comunicação: PACIENTE vs EXAMINADOR
  const [activeChannel, setActiveChannel] = useState<"PATIENT" | "EXAMINER">("PATIENT");
  const [utterance, setUtterance] = useState("");

  // Prontuário de Bolso (Rascunho Rápido do Candidato com persistência local)
  const [pocketNotes, setPocketNotes] = useState<string>(
    "ID:\nQP:\nHMA:\nExame Físico:\nHD / Conduta:"
  );

  // Semiotécnica Bruta Acústica: Modo Estetoscópio
  const [stethoscopeActive, setStethoscopeActive] = useState<boolean>(false);
  const [activeFocus, setActiveFocus] = useState<AuscultationFocus | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  // Focos Anatômicos Padrão (Mapeados pela Estação com fallback fisiológico)
  const anatomicalFoci: AuscultationFocus[] = station.auscultation_foci || [
    { id: "FA", label: "2º EIC Direito (Foco Aórtico)", x: 40, y: 28, soundType: "NORMAL_HEART" },
    { id: "FP", label: "2º EIC Esquerdo (Foco Pulmonar)", x: 60, y: 28, soundType: "NORMAL_HEART" },
    { id: "FM", label: "5º EIC Esquerdo (Foco Mitral / Ápice)", x: 64, y: 52, soundType: "NORMAL_HEART" },
    { id: "APD", label: "Base Pulmonar Direita", x: 34, y: 56, soundType: "NORMAL_VESICULAR" },
    { id: "APE", label: "Terço Médio Pulmonar Esquerdo", x: 66, y: 40, soundType: "NORMAL_VESICULAR" },
  ];

  const handleStopAuscultation = React.useCallback(() => {
    stethoscopeEngine.stopAuscultation();
    setActiveFocus(null);
  }, []);

  const handleFocusClick = (focus: AuscultationFocus) => {
    if (!stethoscopeActive) return;
    if (activeFocus?.id === focus.id) {
      handleStopAuscultation();
      return;
    }
    setActiveFocus(focus);
    stethoscopeEngine.startAuscultation(focus.soundType, vitals.hr, vitals.rr);
  };

  // Atalhos Táticos de Teclado (Tab alterna canal | Esc guarda estetoscópio)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab" && !e.shiftKey && !e.ctrlKey && !e.altKey) {
        // Se o foco não estiver em um textarea (para permitir tabulação em notas)
        if (document.activeElement?.tagName !== "TEXTAREA") {
          e.preventDefault();
          setActiveChannel((prev) => (prev === "PATIENT" ? "EXAMINER" : "PATIENT"));
          inputRef.current?.focus();
        }
      }
      if (e.key === "Escape" && stethoscopeActive) {
        handleStopAuscultation();
        setStethoscopeActive(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [stethoscopeActive, handleStopAuscultation]);

  // Limpeza de áudio ao desmontar ou trocar de tela
  useEffect(() => {
    return () => {
      stethoscopeEngine.stopAuscultation();
    };
  }, []);

  // Atualiza parâmetros de FC e FR se o foco estiver ativo
  useEffect(() => {
    if (activeFocus && stethoscopeActive) {
      stethoscopeEngine.startAuscultation(activeFocus.soundType, vitals.hr, vitals.rr);
    }
  }, [vitals.hr, vitals.rr, activeFocus, stethoscopeActive]);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanText = utterance.trim();
    if (!cleanText || isLoading) return;

    setUtterance("");
    await onSendMessage(cleanText, activeChannel);
  };

  // HUD Cinematográfico: Extrai rigorosamente apenas os 2 últimos eventos de diálogo (sem rolagem passiva!)
  const recentUtterances = transcript.slice(-2);

  return (
    <div className="relative w-full h-full flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-slate-950 text-slate-100 shadow-2xl select-none">
      
      {/* 1. BARRA SUPERIOR DO PALCO CLÍNICO */}
      <div className="z-20 flex items-center justify-between px-4 py-3 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-amber-400 block font-semibold">
              {station.institution} • Beira-Leito Real
            </span>
            <h3 className="text-sm font-bold text-white flex items-center gap-1.5 line-clamp-1">
              {station.patient_persona.name || "Paciente Simulado"}, {station.patient_persona.age || "Adulto"} anos
            </h3>
          </div>
        </div>

        {/* Controles de Semiotécnica Bruta (Estetoscópio Virtual) */}
        <div className="flex items-center gap-2">
          {activeFocus && (
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950 border border-emerald-500/50 text-emerald-300 text-xs font-mono animate-pulse">
              <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
              <span className="truncate max-w-[170px]">{activeFocus.label}</span>
              <button
                type="button"
                onClick={handleStopAuscultation}
                className="ml-1 text-emerald-400 hover:text-white"
                title="Pausar ausculta"
              >
                <VolumeX className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              if (stethoscopeActive) handleStopAuscultation();
              setStethoscopeActive(!stethoscopeActive);
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold text-xs transition-all cursor-pointer ${
              stethoscopeActive
                ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/30 ring-2 ring-emerald-400"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700"
            }`}
            title="Atalho: Esc para guardar"
          >
            <Stethoscope className="w-3.5 h-3.5" />
            <span>{stethoscopeActive ? "Guardar Esteto (ESC)" : "Empunhar Estetoscópio"}</span>
          </button>
        </div>
      </div>

      {/* 2. ÁREA CENTRAL: SILHUETA ANATÔMICA VETORIAL & FOCOS DE AUSCULTA */}
      <div
        className={`relative flex-1 flex items-center justify-center p-4 min-h-[260px] bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950 ${
          stethoscopeActive ? "cursor-crosshair" : "cursor-default"
        }`}
      >
        {/* Prontuário de Bolso Flutuante Retrátil (Canto Superior Esquerdo) */}
        <details className="absolute top-3 left-3 z-30 group">
          <summary className="list-none flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[11px] font-bold cursor-pointer transition-colors shadow-lg">
            <ClipboardList className="w-3.5 h-3.5 text-amber-400" />
            <span>Prontuário de Bolso</span>
          </summary>
          <div className="mt-2 w-72 bg-amber-50 text-slate-900 rounded-xl p-3 shadow-2xl border-t-4 border-amber-700 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-amber-200 text-[10px] font-mono text-amber-900">
              <span className="font-bold uppercase tracking-wider">Rascunho de Bolso</span>
              <span>Uso do Aluno</span>
            </div>
            <textarea
              value={pocketNotes}
              onChange={(e) => setPocketNotes(e.target.value)}
              placeholder="Anote achados, hipóteses e doses antes de falar à banca..."
              rows={6}
              className="w-full bg-transparent resize-none focus:outline-none font-mono text-xs leading-relaxed text-slate-900"
            />
          </div>
        </details>

        {/* Manequim Torácico Vetorial Estilizado */}
        <div className="relative w-64 md:w-72 h-72 md:h-80 bg-slate-950/70 border border-slate-800/90 rounded-3xl flex flex-col items-center justify-center shadow-2xl p-4">
          <svg viewBox="0 0 200 240" className="w-full h-full stroke-slate-700/80 fill-slate-900/40 stroke-2">
            {/* Contorno Torácico + Clavículas + Esterno */}
            <path d="M40,30 C70,15 130,15 160,30 L175,90 L160,210 L40,210 L25,90 Z" />
            <line x1="100" y1="30" x2="100" y2="140" className="stroke-slate-800 stroke-[3]" />
            <path d="M45,35 Q75,45 100,32 Q125,45 155,35" className="fill-none stroke-slate-600/70" />
            {/* Arcos Costais Esboçados */}
            <path d="M50,70 Q100,85 150,70" className="fill-none stroke-slate-800/60 stroke-1" />
            <path d="M48,100 Q100,115 152,100" className="fill-none stroke-slate-800/60 stroke-1" />
            <path d="M46,130 Q100,145 154,130" className="fill-none stroke-slate-800/60 stroke-1" />
          </svg>

          {/* Renderização Interativa dos Focos de Ausculta */}
          {stethoscopeActive ? (
            anatomicalFoci.map((focus) => {
              const isListeningThis = activeFocus?.id === focus.id;
              return (
                <button
                  key={focus.id}
                  type="button"
                  onClick={() => handleFocusClick(focus)}
                  style={{ left: `${focus.x}%`, top: `${focus.y}%` }}
                  title={`${focus.label} (Clique para auscultar)`}
                  className={`absolute -translate-x-1/2 -translate-y-1/2 w-8 h-8 rounded-full flex items-center justify-center transition-all cursor-pointer ${
                    isListeningThis
                      ? "bg-emerald-500 text-slate-950 scale-125 ring-4 ring-emerald-400/60 animate-pulse shadow-lg"
                      : "bg-slate-900/90 text-emerald-400 border border-emerald-500/70 hover:scale-115 hover:bg-slate-800"
                  }`}
                >
                  <Stethoscope className="w-4 h-4" />
                </button>
              );
            })
          ) : (
            <div className="absolute inset-x-4 bottom-3 text-center">
              <span className="text-[10px] font-mono text-slate-400 bg-slate-900/80 px-2 py-1 rounded-md border border-slate-800">
                Empunhe o estetoscópio para habilitar a ausculta nos focos
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 3. HUD DE LEGENDAS CINEMATOGRÁFICAS (Apenas as 2 últimas falas, Zero Scroll) */}
      <div className="z-20 px-4 md:px-6 pb-2 pointer-events-none flex flex-col justify-end min-h-[90px] bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent">
        <div className="w-full space-y-2">
          {recentUtterances.length === 0 && (
            <div className="text-center text-xs font-mono text-slate-500 italic py-2">
              Aproxime-se do leito. Dirija-se ao paciente ou verbalize suas condutas ao examinador da banca.
            </div>
          )}

          {recentUtterances.map((item, idx) => {
            const isOlder = recentUtterances.length === 2 && idx === 0;
            const isCandidate = item.sender === "candidato";
            const isExaminer = item.sender === "examinador";

            const badgeColor = isExaminer
              ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
              : isCandidate
              ? "bg-slate-700/50 text-slate-300 border-slate-600"
              : "bg-sky-500/20 text-sky-300 border-sky-500/40";

            const senderLabel = isExaminer
              ? "EXAMINADOR OFICIAL"
              : isCandidate
              ? `VOCÊ ➔ ${item.target?.toUpperCase() || (activeChannel === "PATIENT" ? "PACIENTE" : "EXAMINADOR")}`
              : `${station.patient_persona.name?.toUpperCase() || "PACIENTE"}`;

            return (
              <div
                key={idx}
                className={`transition-all duration-300 rounded-xl px-3.5 py-2 backdrop-blur-md border ${
                  isOlder
                    ? "opacity-45 scale-[0.98] bg-slate-900/60 border-slate-800/60"
                    : "opacity-100 scale-100 bg-slate-900/90 border-slate-700 shadow-xl"
                }`}
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <span
                    className={`inline-block text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded border ${badgeColor}`}
                  >
                    {senderLabel}
                  </span>
                </div>
                <p className="text-xs md:text-sm font-medium text-slate-100 tracking-wide leading-snug">
                  &ldquo;{item.message}&rdquo;
                </p>
              </div>
            );
          })}

          {isLoading && (
            <div className="text-center text-xs font-mono text-slate-400 animate-pulse py-1">
              {activeChannel === "PATIENT" ? "Paciente formulando resposta..." : "Examinador da banca avaliando sua conduta..."}
            </div>
          )}
        </div>
      </div>

      {/* 4. BARRA TÁTICA DE ENTRADA & SELETOR DE CANAL */}
      <form
        onSubmit={handleFormSubmit}
        className="z-20 bg-slate-950 border-t border-slate-800 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5"
      >
        {/* Seletor Tático de Canal (Paciente vs Examinador) com atalho Tab */}
        <div className="flex rounded-xl bg-slate-900 p-1 border border-slate-800 shrink-0">
          <button
            type="button"
            onClick={() => setActiveChannel("PATIENT")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all cursor-pointer ${
              activeChannel === "PATIENT"
                ? "bg-sky-600 text-white shadow-md shadow-sky-600/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Atalho: Tecla Tab alterna canais"
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span>Falar ao Paciente</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveChannel("EXAMINER")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all cursor-pointer ${
              activeChannel === "EXAMINER"
                ? "bg-amber-600 text-white shadow-md shadow-amber-600/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Atalho: Tecla Tab alterna canais"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Dirigir-se ao Examinador</span>
          </button>
        </div>

        {/* Input Textual de Comunicação */}
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={utterance}
            onChange={(e) => setUtterance(e.target.value)}
            placeholder={
              activeChannel === "PATIENT"
                ? 'Anamnese direta ao paciente (Ex: "Há quanto tempo sente essa dor? Toma remédios?") [TAB alterna]'
                : 'Fale à banca (Ex: "Solicito ECG 12d e realizo palpação de pulsos") [TAB alterna]'
            }
            className={`w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-slate-900 text-xs md:text-sm text-white placeholder-slate-500 border focus:outline-none transition-colors ${
              activeChannel === "PATIENT"
                ? "border-sky-500/40 focus:border-sky-400"
                : "border-amber-500/40 focus:border-amber-400"
            }`}
          />
          {onToggleListening && (
            <button
              type="button"
              onClick={onToggleListening}
              className={`absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-md transition-colors ${
                isListening ? "text-emerald-400 animate-pulse" : "text-slate-500 hover:text-slate-300"
              }`}
              title={isListening ? "Microfone ativo" : "Ativar microfone"}
            >
              <Mic className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Botão de Envio / Verbalização */}
        <button
          type="submit"
          disabled={isLoading || !utterance.trim()}
          className={`px-4 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-1.5 transition-all disabled:opacity-40 cursor-pointer shrink-0 shadow-lg ${
            activeChannel === "PATIENT"
              ? "bg-sky-600 hover:bg-sky-500 text-white"
              : "bg-amber-600 hover:bg-amber-500 text-white"
          }`}
        >
          <Send className="w-3.5 h-3.5" />
          <span>Verbalizar</span>
        </button>
      </form>
    </div>
  );
}
