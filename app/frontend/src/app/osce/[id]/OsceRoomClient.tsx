"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Stethoscope, Clock, FileText,
  Volume2, VolumeX,
  ChevronLeft, Award, Sparkles, AlertTriangle, ShieldCheck,
  Radio, Headphones, Zap, Eye, CheckCircle2, Printer
} from "lucide-react";
import { toast } from "react-hot-toast";
import { OsceStationDetail, OsceTranscriptItem, OsceFinishResponse, OsceSpokenQueueItem, OsceLiveFeedback } from "@/types/api";
import { api } from "@/lib/api";
import { PrescriptionPad } from "./PrescriptionPad";
import { ProcedureMannequin } from "./ProcedureMannequin";
import { GhostPreceptorHUD } from "./GhostPreceptorHUD";
import { StationResultMirror } from "./StationResultMirror";
import { PreceptorFeedback } from "@/types/osce-evaluation";
import { useVitalStateEngine } from "./useVitalStateEngine";
import { useOsceAudio } from "./useOsceAudio";
import { SessionTimer } from "@/components/ui/SessionTimer";
import { MultiparameterMonitor } from "./MultiparameterMonitor";
import { ClinicalStage } from "./ClinicalStage";

interface OsceRoomClientProps {
  station: OsceStationDetail;
  circuitId?: string;
  step?: number;
}

export function OsceRoomClient({ station, circuitId, step = 1 }: OsceRoomClientProps) {
  const router = useRouter();

  // Fases: 'door' (porta da estação) | 'exam' (sala de exame) | 'finished' (espelho da banca)
  const [phase, setPhase] = useState<"door" | "exam" | "finished">("door");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const defaultDuration = station.duration_seconds || 480;
  const [examTiming, setExamTiming] = useState<{ duration: number; deadlineAt: number }>({
    duration: defaultDuration,
    deadlineAt: 0,
  });
  const examTimingRef = useRef(examTiming);
  const [finalElapsedSeconds, setFinalElapsedSeconds] = useState(0);
  const [transcript, setTranscript] = useState<OsceTranscriptItem[]>([]);
  const [inputText, setInputText] = useState("");
  const [conductText, setConductText] = useState("");
  const [activeTab, setActiveTab] = useState<"physical" | "procedures" | "labs" | "conduct">("physical");
  const [vitals, setVitals] = useState<Record<string, string> | null>(null);
  const [selectedExam, setSelectedExam] = useState<{ title: string; image_url?: string; result_text?: string } | null>(null);
  const [report, setReport] = useState<OsceFinishResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const getElapsedSeconds = useCallback(() => {
    const { duration, deadlineAt } = examTimingRef.current;
    if (deadlineAt <= 0) return 0;
    const remaining = Math.max(0, Math.ceil((deadlineAt - Date.now()) / 1000));
    return Math.max(0, duration - remaining);
  }, []);

  // Estados do Modo Duplo (Prova Cega vs Treino Guiado com Preceptor Fantasma)
  const [selectedMode, setSelectedMode] = useState<"blind" | "guided">("guided");
  const [sessionMode, setSessionMode] = useState<"blind" | "guided">("guided");
  const [liveFeedback, setLiveFeedback] = useState<OsceLiveFeedback | null>(null);

  // Motor Fisiológico Dinâmico Beira-Leito (VitalStateEngine)
  const vitalEngine = useVitalStateEngine({
    initialConfig: station.physiology_engine,
    fallbackVitals: vitals,
    getElapsedSeconds,
    isActive: phase === "exam",
  });

  // Estados do Circuito Oficial de 5 Estações
  const [circuitPlan, setCircuitPlan] = useState<import("@/types/api").OsceCircuitPlanResponse | null>(null);
  const [circuitSummary, setCircuitSummary] = useState<import("@/types/api").OsceCircuitSummaryResponse | null>(null);
  const [showCircuitModal, setShowCircuitModal] = useState(false);
  const [isLoadingCircuit, setIsLoadingCircuit] = useState(false);

  useEffect(() => {
    if (!circuitId) return;
    api.osce.getCircuitPlan(station.institution || "USP-RP")
      .then((plan) => {
        if (plan) setCircuitPlan(plan);
      })
      .catch(() => {});
  }, [circuitId, station.institution]);

  const handleAdvanceCircuit = () => {
    if (!circuitPlan?.stations) {
      router.push("/osce");
      return;
    }
    const nextItem = circuitPlan.stations.find((s) => s.step === step + 1);
    if (nextItem) {
      router.push(`/osce/${nextItem.station_id}?circuit=${circuitId}&step=${step + 1}`);
    } else {
      router.push("/osce");
    }
  };

  const handleOpenCircuitSummary = async () => {
    if (!circuitId) return;
    setIsLoadingCircuit(true);
    try {
      const summary = await api.osce.getCircuitSummary(circuitId);
      if (summary) {
        setCircuitSummary(summary);
        setShowCircuitModal(true);
      }
    } catch {
      toast.error("Erro ao carregar parecer global do circuito.");
    } finally {
      setIsLoadingCircuit(false);
    }
  };

  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const handleDispatchSpeechRef = useRef<(spokenText: string) => Promise<void>>(async () => {});
  const dispatchSpeechViaRef = useCallback(
    (spokenText: string) => handleDispatchSpeechRef.current(spokenText),
    []
  );

  const {
    voiceEnabled,
    setVoiceEnabled,
    isListening,
    handsFreeMode,
    interimSpeechText,
    setInterimSpeechText,
    activeSpeaker,
    micPermission,
    micErrorMsg,
    playExamBell,
    stopRecognition,
    speakSpokenQueue,
    cancelSpeechSynthesis,
    requestMicrophonePermission,
    startListening,
    toggleHandsFreeMode,
    toggleListening,
    resumeAfterSpeechFailure,
  } = useOsceAudio({
    phase,
    patientGender: station.patient_persona.gender,
    isLoading,
    onDispatchSpeech: dispatchSpeechViaRef,
  });

  // Autoscroll no transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Dispatcher Unificado de Voz (Modo Hands-Free)
  const handleDispatchSpeech = useCallback(async (spokenText: string) => {
    const text = spokenText.trim();
    if (!text || !sessionId || isLoading) return;

    const elapsed = getElapsedSeconds();
    setIsLoading(true);
    setInterimSpeechText("");

    // Adiciona fala otimista no transcript
    setTranscript((prev) => [
      ...prev,
      {
        sender: "candidato",
        message: text,
        timestamp: new Date().toISOString(),
        elapsed_seconds: elapsed
      }
    ]);

    try {
      const res = await api.osce.dispatchSpeech(sessionId, text, elapsed);

      if (res.guided_feedback) {
        setLiveFeedback(res.guided_feedback);
      }

      if (res.transcript && res.transcript.length > 0) {
        setTranscript(res.transcript);
      }

      if (res.actions_executed && res.actions_executed.length > 0) {
        for (const act of res.actions_executed) {
          if (act.action_type === "vitals" && act.payload?.vitals) {
            setVitals(act.payload.vitals as Record<string, string>);
          }
          if (act.action_type === "lab_imaging" && act.payload?.title) {
            setSelectedExam({
              title: String(act.payload.title),
              image_url: act.payload.image_url ? String(act.payload.image_url) : undefined,
              result_text: act.payload.result_text ? String(act.payload.result_text) : undefined
            });
            setActiveTab("labs");
          }
          if (act.action_type === "physical_exam") {
            setActiveTab("physical");
          }
          if (act.action_type === "procedure") {
            setActiveTab("procedures");
          }
          if (act.action_type === "prescription") {
            setActiveTab("conduct");
          }
        }
      }

      if (res.spoken_queue && res.spoken_queue.length > 0) {
        speakSpokenQueue(res.spoken_queue);
      } else {
        resumeAfterSpeechFailure();
      }
    } catch (err) {
      console.error("Falha no speech dispatcher:", err);
      resumeAfterSpeechFailure();
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, isLoading, getElapsedSeconds, setInterimSpeechText, speakSpokenQueue, resumeAfterSpeechFailure]);

  // Sincroniza ref para chamadas livres de ciclo
  useEffect(() => {
    handleDispatchSpeechRef.current = handleDispatchSpeech;
  }, [handleDispatchSpeech]);

  // Iniciar sessão
  const handleStartExam = async () => {
    setIsLoading(true);
    try {
      const res = await api.osce.startSession(station.id, circuitId, selectedMode);
      setSessionId(res.session_id);
      setSessionMode(res.mode || selectedMode);
      if (res.guided_feedback) {
        setLiveFeedback(res.guided_feedback);
      }
      setTranscript(res.transcript || []);
      const duration = res.duration_seconds || 480;
      const nextTiming = { duration, deadlineAt: Date.now() + duration * 1000 };
      examTimingRef.current = nextTiming;
      setExamTiming(nextTiming);
      setPhase("exam");
      playExamBell("start");

      // Anúncio do Examinador
      const introQueue: OsceSpokenQueueItem[] = [
        {
          speaker: "examinador",
          text: "Candidato, pode entrar na sala de exame. Seu tempo de prova começou."
        }
      ];

      if (voiceEnabled) {
        speakSpokenQueue(introQueue);
      } else if (handsFreeMode) {
        setTimeout(() => startListening(false), 500);
      }
    } catch (err) {
      console.error("Falha ao iniciar estação:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Finalizar sessão
  const handleFinishExam = useCallback(async () => {
    if (!sessionId || isLoading) return;
    setFinalElapsedSeconds(getElapsedSeconds());
    stopRecognition();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsLoading(true);
    playExamBell("finish");

    try {
      const res = await api.osce.finishSession(sessionId, conductText);
      setReport(res);
      setPhase("finished");
    } catch (err) {
      console.error("Erro ao finalizar sessão:", err);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, conductText, isLoading, getElapsedSeconds, playExamBell, stopRecognition]);

  const timerMilestones = useMemo(
    () => ({
      180: () => playExamBell("warning"),
      60: () => {
        playExamBell("warning");
        toast("⚠️ Atenção: Falta 1 minuto para o término da estação! Conclua suas condutas e prescrição.", {
          icon: "⏱️",
          duration: 6000
        });
        if (voiceEnabled) {
          speakSpokenQueue([
            {
              speaker: "examinador",
              text: "Atenção candidato: resta um minuto para o encerramento da estação. Conclua sua conduta."
            }
          ]);
        }
      },
    }),
    [playExamBell, voiceEnabled, speakSpokenQueue]
  );

  // Listener de atalhos de teclado: Abas (Alt+1..4), Microfone (Alt+M / Espaço) e Silenciar (Escape)
  useEffect(() => {
    if (phase !== "exam") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Atalhos com tecla Alt: navegação ultrarrápida entre abas da estação
      if (e.altKey && !e.ctrlKey && !e.shiftKey) {
        if (e.key === "1") {
          e.preventDefault();
          setActiveTab("physical");
          return;
        }
        if (e.key === "2") {
          e.preventDefault();
          setActiveTab("procedures");
          return;
        }
        if (e.key === "3") {
          e.preventDefault();
          setActiveTab("labs");
          return;
        }
        if (e.key === "4") {
          e.preventDefault();
          setActiveTab("conduct");
          return;
        }
        if (e.key.toLowerCase() === "m") {
          e.preventDefault();
          toggleHandsFreeMode();
          return;
        }
      }

      if (e.key === "Escape") {
        cancelSpeechSynthesis();
      }
      // Barra de espaço fora de inputs aciona o microfone
      if (e.code === "Space" && e.target instanceof HTMLElement && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) {
        e.preventDefault();
        if (isListening) {
          stopRecognition();
        } else {
          startListening(true);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [phase, isListening, startListening, stopRecognition, setActiveTab, toggleHandsFreeMode, cancelSpeechSynthesis]);

  // Enviar mensagem manual por texto ou clique
  const handleSendMessage = async (msgToSend?: string, targetOverride?: "PATIENT" | "EXAMINER") => {
    const text = (msgToSend || inputText).trim();
    if (!text || !sessionId || isLoading) return;

    setInputText("");
    if (targetOverride) {
      const elapsed = getElapsedSeconds();
      setIsLoading(true);
      setTranscript((prev) => [
        ...prev,
        {
          sender: "candidato",
          message: text,
          timestamp: new Date().toISOString(),
          elapsed_seconds: elapsed,
          target: targetOverride.toLowerCase()
        }
      ]);

      try {
        const res = await api.osce.interact(sessionId, text, elapsed, targetOverride, vitalEngine.vitals);
        if (res.guided_feedback) {
          setLiveFeedback(res.guided_feedback);
        }
        setTranscript((prev) => [
          ...prev,
          {
            sender: res.sender as ("paciente" | "examinador"),
            message: res.reply,
            timestamp: new Date().toISOString(),
            elapsed_seconds: elapsed
          }
        ]);
        if (voiceEnabled) {
          speakSpokenQueue([
            {
              speaker: res.sender as ("paciente" | "examinador"),
              text: res.reply
            }
          ]);
        }
      } catch (err) {
        console.error("Erro ao enviar mensagem pelo palco clínico:", err);
      } finally {
        setIsLoading(false);
      }
    } else {
      await handleDispatchSpeech(text);
    }
  };

  // Solicitar Ação Clínica (Exame Físico / Sinais Vitais / Exames)
  const handleClinicalAction = async (actionType: "physical_exam" | "vitals" | "lab_imaging", target: string) => {
    if (!sessionId || isLoading) return;
    const elapsed = getElapsedSeconds();
    setIsLoading(true);

    try {
      const res = await api.osce.executeAction(sessionId, actionType, target, elapsed);
      
      if (res.guided_feedback) {
        setLiveFeedback(res.guided_feedback);
      }

      setTranscript((prev) => [
        ...prev,
        {
          sender: "examinador",
          message: res.examiner_message,
          timestamp: new Date().toISOString(),
          elapsed_seconds: elapsed,
          action_payload: res.payload
        }
      ]);

      if (actionType === "vitals") {
        vitalEngine.connectSensors(["all"]);
        vitalEngine.measureNibp();
        if (res.payload.vitals) {
          setVitals(res.payload.vitals as Record<string, string>);
        }
      }
      if (actionType === "lab_imaging" && res.payload.title) {
        setSelectedExam({
          title: String(res.payload.title),
          image_url: res.payload.image_url ? String(res.payload.image_url) : undefined,
          result_text: res.payload.result_text ? String(res.payload.result_text) : undefined
        });
      }
    } catch (err) {
      console.error("Falha ao executar ação:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Callback de prescrição assinada na prancheta da sala de emergência
  const handlePrescriptionSubmitted = (
    prescriptionText: string, 
    examinerMessage: string, 
    spokenQueue: OsceSpokenQueueItem[],
    guidedFeedback?: OsceLiveFeedback
  ) => {
    if (guidedFeedback) {
      setLiveFeedback(guidedFeedback);
    }

    // Alimenta o motor fisiológico com as drogas administradas
    if (prescriptionText) {
      const lower = prescriptionText.toLowerCase();
      if (lower.includes("adrenalina") || lower.includes("epinefrina")) {
        vitalEngine.applyIntervention("adrenalina", "Adrenalina");
      }
      if (lower.includes("noradrenalina")) {
        vitalEngine.applyIntervention("noradrenalina", "Noradrenalina");
      }
      if (lower.includes("amiodarona")) {
        vitalEngine.applyIntervention("amiodarona", "Amiodarona");
      }
      if (lower.includes("adenosina")) {
        vitalEngine.applyIntervention("adenosina", "Adenosina");
      }
      if (lower.includes("sf 0,9") || lower.includes("soro") || lower.includes("cristaloide")) {
        vitalEngine.applyIntervention("sf09", "Soro Fisiológico 0,9%");
      }
      if (lower.includes("insulina")) {
        vitalEngine.applyIntervention("insulina", "Insulina Regular");
      }
      if (lower.includes("kcl") || lower.includes("potassio")) {
        vitalEngine.applyIntervention("kcl", "Cloreto de Potássio");
      }
      if (lower.includes("sangue") || lower.includes("transfusao") || lower.includes("1:1:1")) {
        vitalEngine.applyIntervention("sangue_111", "Transfusão Maciça 1:1:1");
      }
      if (lower.includes("tranexamico") || lower.includes("transamin")) {
        vitalEngine.applyIntervention("acido_tranexamico", "Ácido Tranexâmico");
      }
      if (lower.includes("midazolam") || lower.includes("etomidato") || lower.includes("fentanil")) {
        vitalEngine.applyIntervention("sedacao", "Sedação / Analgesia");
      }
    }

    const elapsed = getElapsedSeconds();
    setTranscript((prev) => [
      ...prev,
      {
        sender: "examinador",
        message: examinerMessage,
        timestamp: new Date().toISOString(),
        elapsed_seconds: elapsed,
        action_payload: { type: "prescription", text: prescriptionText }
      }
    ]);

    if (voiceEnabled && spokenQueue && spokenQueue.length > 0) {
      speakSpokenQueue(spokenQueue);
    }
  };

  // Callback de procedimento realizado no manequim 2D
  const handleProcedureExecuted = (
    title: string, 
    findings: string, 
    examinerMessage: string, 
    spokenQueue: OsceSpokenQueueItem[],
    guidedFeedback?: OsceLiveFeedback
  ) => {
    if (guidedFeedback) {
      setLiveFeedback(guidedFeedback);
    }

    // Alimenta o motor fisiológico com o procedimento realizado
    if (title.toLowerCase().includes("cardiovers") || title.toLowerCase().includes("choque")) {
      vitalEngine.executeCardioversion(true, 100);
    } else {
      vitalEngine.applyIntervention("procedure", title);
    }

    const elapsed = getElapsedSeconds();
    setTranscript((prev) => [
      ...prev,
      {
        sender: "examinador",
        message: examinerMessage,
        timestamp: new Date().toISOString(),
        elapsed_seconds: elapsed,
        action_payload: { type: "procedure", title, findings }
      }
    ]);

    if (voiceEnabled && spokenQueue && spokenQueue.length > 0) {
      speakSpokenQueue(spokenQueue);
    }
  };

  // Polling suave do Preceptor Fantasma para atualizar alertas proativos baseados no tempo decorrido
  useEffect(() => {
    if (phase !== "exam" || sessionMode !== "guided" || !sessionId) return;

    const interval = setInterval(async () => {
      try {
        const elapsed = getElapsedSeconds();
        const feedback = await api.osce.getLiveFeedback(sessionId, elapsed);
        if (feedback) {
          setLiveFeedback(feedback);
        }
      } catch {
        // Silencioso em caso de atraso na rede
      }
    }, 20000);

    return () => clearInterval(interval);
  }, [phase, sessionMode, sessionId, getElapsedSeconds]);

  return (
    <div className="flex-1 flex flex-col min-h-full w-full max-w-7xl mx-auto p-3 md:p-6">
      {/* ========================================================================= */}
      {/* FASE 1: PORTA DA ESTAÇÃO */}
      {/* ========================================================================= */}
      {phase === "door" && (
        <div className="flex-1 flex flex-col items-center p-2 sm:p-4 max-w-3xl mx-auto text-center space-y-6 w-full pb-32 animate-in fade-in zoom-in-95 duration-200">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase tracking-wider">
            <Stethoscope className="w-4 h-4" />
            <span>Porta da Estação • {station.institution}</span>
            {circuitId && <span className="ml-2 text-amber-500 font-extrabold">• Circuito: Estação {step} de 5</span>}
          </div>

          <h1 className="text-3xl md:text-4xl font-black text-foreground">
            {station.title}
          </h1>

          <div className="flex items-center justify-center gap-4 text-xs md:text-sm text-muted-foreground font-semibold">
            <span>{station.area}</span>
            <span>•</span>
            <span>{station.subtema}</span>
            <span>•</span>
            <span className="flex items-center gap-1 text-primary">
              <Clock className="w-4 h-4" />
              {Math.round(station.duration_seconds / 60)} minutos
            </span>
          </div>

          {/* Cartaz Colado na Porta */}
          <div className="w-full text-left rounded-2xl border-2 border-border bg-card p-6 md:p-8 shadow-sm space-y-4">
            <div className="text-xs font-bold uppercase text-muted-foreground tracking-wider pb-2 border-b border-border">
              Instruções Fixadas na Porta da Sala
            </div>
            <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-line text-sm text-foreground/90">
              {station.scenario_door_markdown}
            </div>
          </div>

          {/* Seletor de Modo de Avaliação: Treino Guiado vs Prova Cega */}
          <div className="w-full text-left rounded-2xl border border-border bg-card p-4 md:p-6 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Escolha o Modo de Simulação
              </span>
              <span className="text-[11px] text-muted-foreground font-medium hidden sm:inline">
                Pode alternar livremente a qualquer momento
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Opção 1: Treino Guiado (Preceptor Fantasma) */}
              <button
                type="button"
                onClick={() => setSelectedMode("guided")}
                className={`p-4 rounded-xl border-2 text-left transition-all relative flex flex-col justify-between ${
                  selectedMode === "guided"
                    ? "border-primary bg-primary/10 shadow-sm ring-2 ring-primary/20"
                    : "border-border bg-background hover:bg-muted/50"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">👻</span>
                    <div>
                      <div className="font-bold text-sm text-foreground flex items-center gap-1.5">
                        Treinamento Guiado
                      </div>
                      <div className="text-[10px] font-bold text-primary uppercase">
                        Preceptor Fantasma Ativo
                      </div>
                    </div>
                  </div>
                  {selectedMode === "guided" && (
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Barema dinâmico com pontuação ao vivo. O Preceptor alerta sobre tempos críticos, dosagem de eletrólitos e condutas essenciais antes do fim do tempo.
                </p>
                <div className="mt-3 flex items-center gap-1.5 text-[10px] font-bold text-primary">
                  <Sparkles className="w-3 h-3" />
                  <span>Recomendado para aprendizado e fixação</span>
                </div>
              </button>

              {/* Opção 2: Prova Cega (Banca Oficial) */}
              <button
                type="button"
                onClick={() => setSelectedMode("blind")}
                className={`p-4 rounded-xl border-2 text-left transition-all relative flex flex-col justify-between ${
                  selectedMode === "blind"
                    ? "border-primary bg-primary/10 shadow-sm ring-2 ring-primary/20"
                    : "border-border bg-background hover:bg-muted/50"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <Eye className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <div className="font-bold text-sm text-foreground flex items-center gap-1.5">
                        Prova Cega Oficial
                      </div>
                      <div className="text-[10px] font-bold text-muted-foreground uppercase">
                        USP-RP / Unicamp / Banca Real
                      </div>
                    </div>
                  </div>
                  {selectedMode === "blind" && (
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Experiência realística de 2ª fase sem nenhuma pista visual. Cronômetro puro e barema 100% oculto até a finalização da conduta.
                </p>
                <div className="mt-3 flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground">
                  <ShieldCheck className="w-3 h-3" />
                  <span>Simulação de alta pressão real</span>
                </div>
              </button>
            </div>
          </div>

          <div className="sticky bottom-4 z-20 flex items-center justify-center gap-4 pt-4 pb-2 w-full max-w-xl mx-auto bg-background/90 backdrop-blur-md p-3 rounded-2xl border border-border shadow-xl">
            <Link
              href="/osce"
              className="px-5 py-3 rounded-xl border border-border bg-card hover:bg-muted text-sm font-semibold transition-colors shrink-0"
            >
              Voltar ao Hub
            </Link>
            <button
              onClick={handleStartExam}
              disabled={isLoading}
              className="flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold bg-primary text-primary-foreground hover:bg-primary/90 shadow-md transition-transform active:scale-95 text-base cursor-pointer shrink-0"
            >
              <Stethoscope className="w-5 h-5" />
              <span>Entrar na Sala de Exame</span>
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* FASE 2: SALA DE EXAME BEIRA-LEITO */}
      {/* ========================================================================= */}
      {phase === "exam" && (
        <div className="flex-1 flex flex-col min-h-0 w-full gap-4 pb-12">
          {/* Topbar da Estação */}
          <div className="flex items-center justify-between p-3 md:p-4 rounded-2xl border border-border bg-card shadow-sm shrink-0">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider bg-primary/10 text-primary">
                {station.institution}
              </span>
              <div>
                <h2 className="text-sm md:text-base font-bold text-foreground line-clamp-1">
                  {station.title}
                </h2>
                <p className="text-xs text-muted-foreground hidden md:block">
                  {station.patient_persona.name || "Paciente"}, {station.patient_persona.age || "Adulto"} anos
                </p>
              </div>
            </div>

            {/* Cronômetro e Ações Rápidas */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setVoiceEnabled(!voiceEnabled)}
                title={voiceEnabled ? "Desativar áudio do paciente" : "Ativar áudio do paciente"}
                className={`p-2 rounded-lg border text-xs ${
                  voiceEnabled ? "bg-primary/10 text-primary border-primary/20" : "bg-muted text-muted-foreground border-border"
                }`}
              >
                {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
              </button>

              <SessionTimer
                deadlineAt={examTiming.deadlineAt}
                fallbackSeconds={examTiming.duration}
                active={phase === "exam"}
                format="mmss"
                variant="osce"
                milestones={timerMilestones}
                onExpire={handleFinishExam}
              />

              <button
                onClick={handleFinishExam}
                disabled={isLoading}
                className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-rose-500 hover:bg-rose-600 text-white shadow-sm transition-transform active:scale-95"
              >
                Finalizar Conduta
              </button>
            </div>
          </div>

          {/* HUD do Preceptor Fantasma (Modo Guiado) ou Indicador de Prova Cega */}
          <GhostPreceptorHUD feedback={liveFeedback} mode={sessionMode} />

          {/* Banner de Sala Real Hands-Free (Viva-Voz Beira-Leito) */}
          <div className="rounded-2xl border border-primary/30 bg-gradient-to-r from-primary/10 via-background to-secondary/10 p-3.5 md:p-4 shadow-sm space-y-2.5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={toggleHandsFreeMode}
                  className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all shadow-sm ${
                    handsFreeMode
                      ? "bg-primary text-primary-foreground ring-2 ring-primary/40"
                      : "bg-muted text-muted-foreground hover:bg-muted/80 border border-border"
                  }`}
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>{handsFreeMode ? "🎙️ Modo Hands-Free ATIVADO" : "Modo Hands-Free Desligado"}</span>
                </button>

                {/* Status Dinâmico de Fala / Escuta */}
                <div className="flex items-center gap-2 text-xs">
                  {activeSpeaker ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-600 dark:text-amber-400 font-bold animate-pulse">
                      <Volume2 className="w-3.5 h-3.5" />
                      <span>{activeSpeaker === "examinador" ? "Examinador da Banca Falando..." : `${station.patient_persona.name || "Paciente"} Falando...`}</span>
                      <span className="text-[10px] opacity-75 font-normal ml-1">(Esc para interromper)</span>
                    </span>
                  ) : isListening ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-bold">
                      <span className="flex gap-0.5 items-end h-3">
                        <span className="w-1 h-2 bg-emerald-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                        <span className="w-1 h-3 bg-emerald-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                        <span className="w-1 h-2 bg-emerald-500 rounded-full animate-bounce"></span>
                      </span>
                      <span>Ouvindo sua voz em tempo real...</span>
                    </span>
                  ) : isLoading ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-primary/20 text-primary font-bold animate-pulse">
                      <Zap className="w-3.5 h-3.5" />
                      <span>Processando comando clínico...</span>
                    </span>
                  ) : micPermission === "unsupported" ? (
                    <span className="text-muted-foreground text-xs">Modo texto / atalhos ativo</span>
                  ) : (
                    <span className="text-muted-foreground text-xs">Microfone aguardando ativação</span>
                  )}
                </div>
              </div>

              {/* Dica de Teclado */}
              <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                <Headphones className="w-3.5 h-3.5 text-primary hidden sm:inline" />
                <span className="text-[11px] hidden sm:inline">Use fones •</span>
                <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[10px] font-mono">Espaço</kbd>
                <span className="text-[11px]">ligar mic •</span>
                <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[10px] font-mono">Alt+1..4</kbd>
                <span className="text-[11px] hidden sm:inline">trocar abas •</span>
                <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[10px] font-mono">Alt+M</kbd>
                <span className="text-[11px] hidden sm:inline">viva-voz •</span>
                <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[10px] font-mono">Esc</kbd>
                <span className="text-[11px] hidden md:inline">corta fala</span>
              </div>
            </div>

            {/* Alerta de Diagnóstico ou Orientação de Microfone */}
            {micPermission === "unsupported" && micErrorMsg && (
              <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-blue-500/10 border border-blue-500/30 text-xs text-blue-300 animate-in fade-in">
                <div className="flex items-start sm:items-center gap-2">
                  <span className="text-base shrink-0">💡</span>
                  <span className="leading-relaxed">{micErrorMsg}</span>
                </div>
              </div>
            )}

            {micPermission === "denied" && micErrorMsg && (
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 p-3 rounded-xl bg-destructive/15 border border-destructive/30 text-xs text-destructive animate-in fade-in">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{micErrorMsg}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                  <button
                    type="button"
                    onClick={() => requestMicrophonePermission().then(ok => { if (ok) startListening(true); })}
                    className="px-2.5 py-1 rounded-lg bg-destructive text-destructive-foreground text-[11px] font-bold hover:bg-destructive/90 cursor-pointer"
                  >
                    Tentar Novamente
                  </button>
                  <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="px-2.5 py-1 rounded-lg bg-muted border border-border text-foreground text-[11px] font-medium hover:bg-muted/80 cursor-pointer"
                  >
                    Recarregar Página
                  </button>
                </div>
              </div>
            )}

            {/* Balão de Transcrição Ao Vivo */}
            {interimSpeechText && (
              <div className="p-2.5 rounded-xl bg-card border border-primary/40 text-xs text-foreground flex items-center gap-2 animate-in fade-in">
                <span className="font-bold text-primary shrink-0">Transcrição ao vivo:</span>
                <span className="italic truncate text-foreground/90">&ldquo;{interimSpeechText}&rdquo;</span>
              </div>
            )}

            {/* Pílulas de Exemplos de Comandos Clínicos para Treinamento Verbal */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px]">
              <span className="text-muted-foreground font-semibold">Comandos por voz:</span>
              <button
                onClick={() => handleSendMessage("Examinador, solicito sinais vitais completos e PA")}
                className="px-2 py-0.5 rounded-md bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors text-muted-foreground border border-border/60"
              >
                &ldquo;Examinador, sinais vitais&rdquo;
              </button>
              <button
                onClick={() => handleSendMessage("Examinador, solicito eletrocardiograma de 12 derivações")}
                className="px-2 py-0.5 rounded-md bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors text-muted-foreground border border-border/60"
              >
                &ldquo;Solicito ECG 12d&rdquo;
              </button>
              <button
                onClick={() => handleSendMessage("Gostaria de realizar ausculta cardíaca e pulmonar")}
                className="px-2 py-0.5 rounded-md bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors text-muted-foreground border border-border/60"
              >
                &ldquo;Ausculta cardiopulmonar&rdquo;
              </button>
              <button
                onClick={() => handleSendMessage(`Olá ${station.patient_persona.name || "senhor"}, onde começou essa dor e como ela é?`)}
                className="px-2 py-0.5 rounded-md bg-muted/60 hover:bg-primary/20 hover:text-primary transition-colors text-muted-foreground border border-border/60"
              >
                &ldquo;Onde começou a dor?&rdquo;
              </button>
            </div>
          </div>

          {/* MONITOR MULTIPARAMÉTRICO VIRTUAL EM TEMPO REAL (SALA VERMELHA) */}
          <MultiparameterMonitor
            vitals={vitalEngine.vitals}
            isMonitored={vitalEngine.isMonitored}
            displayedNibp={vitalEngine.displayedNibp}
            isMeasuringNibp={vitalEngine.isMeasuringNibp}
            activeAlarms={vitalEngine.activeAlarms}
            isAlarmSilenced={vitalEngine.isAlarmSilenced}
            isAudioMuted={vitalEngine.isAudioMuted}
            onMeasureNibp={vitalEngine.measureNibp}
            onConnectSensors={vitalEngine.connectSensors}
            onSilenceAlarms={vitalEngine.silenceAlarms}
            onToggleAudio={vitalEngine.toggleAudio}
            onExecuteCardioversion={vitalEngine.executeCardioversion}
          />

          {/* Grid Principal: Chat com Paciente (Esq) + Painel de Ações Clínicas (Dir) */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
            {/* Coluna Esquerda: Palco Clínico Triplo & Semiotécnica Bruta (7 cols) */}
            <div className="lg:col-span-7 flex flex-col min-h-[440px] lg:min-h-0">
              <ClinicalStage
                station={station}
                vitals={vitalEngine.vitals}
                transcript={transcript}
                isLoading={isLoading}
                onSendMessage={async (text, target) => {
                  await handleSendMessage(text, target);
                }}
                isListening={isListening}
                onToggleListening={toggleListening}
                micPermission={micPermission}
              />
            </div>

            {/* Coluna Direita: Ações Médicas & Exame Físico (5 cols) */}
            <div className="lg:col-span-5 flex flex-col rounded-2xl border border-border bg-card overflow-hidden min-h-0">
              {/* Abas Laterais */}
              <div className="flex border-b border-border bg-muted/30">
                <button
                  onClick={() => setActiveTab("physical")}
                  className={`flex-1 py-2.5 text-xs font-bold text-center border-b-2 transition-colors flex items-center justify-center gap-1 ${
                    activeTab === "physical"
                      ? "border-primary text-primary bg-background"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                  title="Atalho: Alt + 1"
                >
                  <span>Exame Físico</span>
                  <span className="hidden xl:inline text-[9px] opacity-60 font-mono font-normal bg-muted/60 px-1 rounded">1</span>
                </button>
                <button
                  onClick={() => setActiveTab("procedures")}
                  className={`flex-1 py-2.5 text-xs font-bold text-center border-b-2 transition-colors flex items-center justify-center gap-1 ${
                    activeTab === "procedures"
                      ? "border-primary text-primary bg-background"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                  title="Atalho: Alt + 2"
                >
                  <span>Manequim</span>
                  <span className="hidden xl:inline text-[9px] opacity-60 font-mono font-normal bg-muted/60 px-1 rounded">2</span>
                </button>
                <button
                  onClick={() => setActiveTab("labs")}
                  className={`flex-1 py-2.5 text-xs font-bold text-center border-b-2 transition-colors flex items-center justify-center gap-1 ${
                    activeTab === "labs"
                      ? "border-primary text-primary bg-background"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                  title="Atalho: Alt + 3"
                >
                  <span>Exames</span>
                  <span className="hidden xl:inline text-[9px] opacity-60 font-mono font-normal bg-muted/60 px-1 rounded">3</span>
                </button>
                <button
                  onClick={() => setActiveTab("conduct")}
                  className={`flex-1 py-2.5 text-xs font-bold text-center border-b-2 transition-colors flex items-center justify-center gap-1 ${
                    activeTab === "conduct"
                      ? "border-primary text-primary bg-background"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                  title="Atalho: Alt + 4"
                >
                  <span>Conduta</span>
                  <span className="hidden xl:inline text-[9px] opacity-60 font-mono font-normal bg-muted/60 px-1 rounded">4</span>
                </button>
              </div>

              {/* Conteúdo da Aba */}
              <div className="flex-1 p-4 overflow-y-auto space-y-4 text-xs">
                {/* ABA 1: EXAME FÍSICO */}
                {activeTab === "physical" && (
                  <div className="space-y-4">
                    {/* Botão Sinais Vitais */}
                    <div className="flex items-center justify-between p-3 rounded-xl bg-muted/40 border border-border">
                      <span className="font-bold text-foreground">Monitor e Sinais Vitais</span>
                      <button
                        onClick={() => handleClinicalAction("vitals", "vitals")}
                        className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-bold text-[11px] hover:bg-primary/90"
                      >
                        Checar Sinais
                      </button>
                    </div>

                    {/* Sinais Vitais Exibidos Dinâmicos */}
                    {(vitals || vitalEngine.isMonitored.ecg || vitalEngine.displayedNibp) && (
                      <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-muted/20 border border-border font-mono text-[11px]">
                        <div>
                          PA:{" "}
                          <span className="font-bold text-foreground">
                            {vitalEngine.displayedNibp
                              ? `${vitalEngine.displayedNibp.sbp}x${vitalEngine.displayedNibp.dbp}`
                              : vitalEngine.isMeasuringNibp
                              ? "Aferindo..."
                              : vitals?.pa || "--/--"}
                          </span>
                        </div>
                        <div>
                          FC:{" "}
                          <span className="font-bold text-emerald-500">
                            {vitalEngine.isMonitored.ecg ? `${vitalEngine.vitals.hr} bpm` : vitals?.fc || "--"}
                          </span>
                        </div>
                        <div>
                          FR:{" "}
                          <span className="font-bold text-foreground">
                            {vitalEngine.vitals.rr} irpm
                          </span>
                        </div>
                        <div>
                          SatO2:{" "}
                          <span className="font-bold text-cyan-500">
                            {vitalEngine.isMonitored.spo2 ? `${vitalEngine.vitals.spo2}%` : vitals?.sato2 || "--"}
                          </span>
                        </div>
                        <div>
                          Temp:{" "}
                          <span className="font-bold text-foreground">
                            {vitalEngine.vitals.temp || 36.5} °C
                          </span>
                        </div>
                        <div>
                          Ritmo:{" "}
                          <span className="font-bold text-emerald-500 truncate block text-[10px]">
                            {vitalEngine.vitals.rhythm}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Estetoscópio Virtual & Áreas Anatômicas */}
                    <div className="space-y-2">
                      <span className="text-muted-foreground font-semibold block">
                        Estetoscópio & Exame Segmentar (Clique para auscultar/palpar):
                      </span>
                      <div className="grid grid-cols-2 gap-2">
                        {station.physical_exam_categories.map((cat) => (
                          <button
                            key={cat}
                            onClick={() => handleClinicalAction("physical_exam", cat)}
                            className="p-2.5 rounded-xl border border-border bg-card hover:bg-muted hover:border-primary/40 text-left font-medium capitalize transition-colors flex items-center justify-between"
                          >
                            <span>{cat.replace("_", " ")}</span>
                            <Stethoscope className="w-3.5 h-3.5 text-primary" />
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* ABA 2: MANEQUIM INTERATIVO & E-FAST */}
                {activeTab === "procedures" && (
                  <div className="space-y-4">
                    {sessionId ? (
                      <ProcedureMannequin
                        sessionId={sessionId}
                        getElapsedSeconds={getElapsedSeconds}
                        onProcedureExecuted={handleProcedureExecuted}
                        isLoading={isLoading}
                      />
                    ) : (
                      <div className="p-4 text-center text-muted-foreground text-xs">
                        Iniciando sessão do manequim...
                      </div>
                    )}
                  </div>
                )}

                {/* ABA 3: EXAMES COMPLEMENTARES */}
                {activeTab === "labs" && (
                  <div className="space-y-4">
                    <span className="text-muted-foreground font-semibold block">
                      Solicitar Exames à Banca Examinadora:
                    </span>
                    <div className="space-y-2">
                      {station.lab_imaging_catalog.map((lab) => (
                        <button
                          key={lab.key}
                          onClick={() => handleClinicalAction("lab_imaging", lab.key)}
                          className="w-full p-2.5 rounded-xl border border-border bg-card hover:bg-muted text-left font-medium flex items-center justify-between transition-colors"
                        >
                          <span>{lab.title}</span>
                          <FileText className="w-3.5 h-3.5 text-primary" />
                        </button>
                      ))}
                    </div>

                    {/* Visualizador de Exame Selecionado */}
                    {selectedExam && (
                      <div className="p-3.5 rounded-xl border-2 border-primary/20 bg-card space-y-2 mt-4">
                        <div className="font-bold text-foreground text-xs border-b border-border pb-1">
                          {selectedExam.title}
                        </div>
                        <p className="text-foreground/90 font-medium leading-relaxed">
                          {selectedExam.result_text}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* ABA 4: PRANCHETA DE PRESCRIÇÃO E CONDUTA VERBAL */}
                {activeTab === "conduct" && (
                  <div className="space-y-4">
                    {sessionId && (
                      <PrescriptionPad
                        sessionId={sessionId}
                        getElapsedSeconds={getElapsedSeconds}
                        onPrescriptionSubmitted={handlePrescriptionSubmitted}
                        isLoading={isLoading}
                      />
                    )}

                    <div className="pt-3 border-t border-border space-y-2">
                      <span className="text-muted-foreground font-semibold block text-[11px]">
                        Verbalização Final & Conclusão de Prova (Resumo da Conduta):
                      </span>
                      <textarea
                        value={conductText}
                        onChange={(e) => setConductText(e.target.value)}
                        onKeyDown={(e) => {
                          if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && conductText.trim() && !isLoading) {
                            e.preventDefault();
                            handleFinishExam();
                          }
                        }}
                        placeholder="Ex: Confirmo monitorização contínua, paciente estabilizado com a prescrição acima e indico laparotomia exploradora imediata... (ou pressione Ctrl+Enter)"
                        className="w-full h-24 p-3 bg-muted/40 border border-border rounded-xl text-xs focus:outline-none focus:border-primary resize-none leading-relaxed"
                      />
                      <button
                        onClick={handleFinishExam}
                        disabled={isLoading || !conductText.trim()}
                        className="w-full py-2.5 rounded-xl font-bold bg-primary text-primary-foreground hover:bg-primary/90 text-xs shadow-sm transition-transform active:scale-98 flex items-center justify-center gap-1.5"
                      >
                        <span>Registrar Conduta e Concluir Prova</span>
                        <span className="hidden sm:inline text-[10px] opacity-70 font-mono font-normal bg-primary-foreground/20 px-1 rounded">[Ctrl+Enter]</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* FASE 3: ESPELHO OFICIAL DE CORREÇÃO (BAREMA) */}
      {/* ========================================================================= */}
      {phase === "finished" && report && (
        <div className="flex-1 flex flex-col p-4 max-w-4xl mx-auto w-full space-y-6 pb-32 animate-in fade-in duration-300 print:p-0 print:m-0 print:max-w-full print:pb-0 print:space-y-4">
          {/* Cabeçalho Institucional Formal Exclusivo para Impressão / PDF */}
          <div className="hidden print:block border-b-2 border-black pb-4 text-black">
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-xl font-black uppercase tracking-wider">MedQuest • Prova Prática Beira-Leito (OSCE)</h1>
                <p className="text-xs font-bold text-gray-700">Comitê de Avaliação de 2ª Fase Presencial • Parecer Oficial da Banca</p>
              </div>
              <div className="text-right text-xs text-gray-600 font-mono">
                <div>Data: {new Date().toLocaleDateString("pt-BR")}</div>
                <div>Banca: {station.institution || "USP-RP"}</div>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-gray-300 flex justify-between text-xs">
              <span><strong>Estação:</strong> {station.title}</span>
              <span><strong>Grande Área:</strong> {station.area}</span>
              <span><strong>Subtema:</strong> {station.subtema}</span>
            </div>
          </div>

          {/* Espelho Oficial de 2ª Fase & Radar de Competências (Etapa 4) */}
          <StationResultMirror
            feedback={report.preceptor_feedback as unknown as PreceptorFeedback}
            stationTitle={station.title}
            institution={station.institution || "USP-RP"}
            area={station.area}
            subtema={station.subtema}
            elapsedSeconds={finalElapsedSeconds}
            onRetryStation={() => window.location.reload()}
            onGoBack={() => router.push("/osce")}
          />

          {/* Navegação Final & Ações */}
          <div className="flex items-center justify-between pt-4 border-t border-border print:hidden">
            <div className="flex items-center gap-2">
              <Link
                href="/osce"
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-border hover:bg-muted text-xs font-semibold"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Voltar ao Catálogo</span>
              </Link>

              <button
                type="button"
                onClick={() => window.print()}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-border bg-card hover:bg-muted text-xs font-bold text-foreground transition-all shadow-sm active:scale-95 cursor-pointer"
                title="Imprimir ou salvar parecer oficial em PDF"
              >
                <Printer className="w-4 h-4 text-primary" />
                <span>Imprimir Espelho (PDF)</span>
              </button>
            </div>

            {circuitId && (
              step < 5 ? (
                <button
                  onClick={handleAdvanceCircuit}
                  className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-black text-xs font-bold shadow-md transition-transform active:scale-95 flex items-center gap-2 cursor-pointer"
                >
                  <Award className="w-4 h-4" />
                  <span>
                    Avançar para Estação {step + 1} de 5 {circuitPlan?.stations?.find(s => s.step === step + 1)?.area ? `(${circuitPlan.stations.find(s => s.step === step + 1)?.area})` : ""} →
                  </span>
                </button>
              ) : (
                <button
                  onClick={handleOpenCircuitSummary}
                  disabled={isLoadingCircuit}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-600 hover:to-yellow-500 text-black text-xs font-black shadow-lg transition-transform active:scale-95 flex items-center gap-2 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{isLoadingCircuit ? "Calculando Parecer Global..." : "Parecer Final do Circuito (0 a 50 pts) 🏆"}</span>
                </button>
              )
            )}
          </div>
        </div>
      )}

      {/* Modal / Espelho Consolidado de 2ª Fase (0 a 50 pontos) */}
      {showCircuitModal && circuitSummary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-card border-2 border-primary/30 rounded-3xl max-w-2xl w-full p-6 md:p-8 space-y-6 shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="text-center space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/15 text-amber-500 text-xs font-bold uppercase tracking-wider">
                <Award className="w-4 h-4" />
                <span>Espelho Oficial de 2ª Fase Presencial • 5 Estações</span>
              </div>
              <h2 className="text-2xl md:text-3xl font-black text-foreground">
                Resultado Global do Circuito
              </h2>
              <p className="text-xs text-muted-foreground">
                Banca Examinadora • Faculdade de Medicina da FMRP-USP
              </p>
            </div>

            {/* Score Big Card */}
            <div className={`p-6 rounded-2xl border-2 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
              circuitSummary.approved ? "bg-emerald-500/10 border-emerald-500/30" : "bg-rose-500/10 border-rose-500/30"
            }`}>
              <div>
                <div className="text-xs uppercase font-bold text-muted-foreground">Nota Consolidada (0 a 50)</div>
                <div className={`text-4xl font-black ${circuitSummary.approved ? "text-emerald-500" : "text-rose-500"}`}>
                  {circuitSummary.total_score.toFixed(1)} <span className="text-xl text-muted-foreground">/ 50.0</span>
                </div>
                <div className="text-xs font-semibold text-foreground/80 mt-1">
                  Aproveitamento Global: {circuitSummary.percentage}%
                </div>
              </div>

              <div className={`px-4 py-2 rounded-xl text-xs font-black uppercase text-center ${
                circuitSummary.approved ? "bg-emerald-500 text-black" : "bg-rose-500 text-white"
              }`}>
                {circuitSummary.approved ? "Aprovado na 2ª Fase ✓" : "Reprovado (Abaixo do Corte)"}
              </div>
            </div>

            {/* Parecer da Banca */}
            <div className="p-4 rounded-xl bg-muted/40 border border-border text-xs leading-relaxed text-foreground/90 space-y-1">
              <span className="font-bold text-foreground block">Parecer da Banca Examinadora:</span>
              <p>{circuitSummary.board_feedback}</p>
            </div>

            {/* Rotação das 5 Estações */}
            <div className="space-y-2">
              <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Desempenho por Estação de Especialidade:
              </div>
              <div className="border border-border rounded-xl divide-y divide-border overflow-hidden bg-background">
                {circuitSummary.stations.map((s) => (
                  <div key={s.station_id} className="p-3 text-xs flex items-center justify-between gap-3">
                    <div>
                      <div className="font-bold text-foreground">{s.area}</div>
                      <div className="text-[11px] text-muted-foreground line-clamp-1">{s.title}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <span className={`px-2 py-0.5 rounded-md font-mono font-bold text-[11px] ${
                        s.approved ? "bg-emerald-500/15 text-emerald-500" : "bg-rose-500/15 text-rose-500"
                      }`}>
                        {s.final_score.toFixed(1)} / 10.0
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-border">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowCircuitModal(false)}
                  className="px-4 py-2 rounded-xl border border-border hover:bg-muted text-xs font-semibold cursor-pointer"
                >
                  Fechar Espelho
                </button>
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="px-3.5 py-2 rounded-xl border border-border bg-card hover:bg-muted text-xs font-bold text-foreground flex items-center gap-1.5 cursor-pointer shadow-sm active:scale-95"
                  title="Imprimir ou Salvar Parecer Consolidado do Circuito em PDF"
                >
                  <Printer className="w-3.5 h-3.5 text-primary" />
                  <span>Imprimir Circuito</span>
                </button>
              </div>
              <button
                type="button"
                onClick={() => router.push("/osce")}
                className="px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 cursor-pointer"
              >
                Concluir e Voltar ao Hub
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
