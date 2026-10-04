"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Stethoscope, Clock, Send, Mic, MicOff, 
  Volume2, VolumeX, FileText, Activity,
  ChevronLeft, Award, Sparkles, AlertTriangle, ShieldCheck,
  Radio, Headphones, Zap, Eye, CheckCircle2, Printer
} from "lucide-react";
import { toast } from "react-hot-toast";
import { OsceStationDetail, OsceTranscriptItem, OsceFinishResponse, OsceSpokenQueueItem, OsceLiveFeedback } from "@/types/api";
import { api } from "@/lib/api";
import { PrescriptionPad } from "./PrescriptionPad";
import { ProcedureMannequin } from "./ProcedureMannequin";
import { GhostPreceptorHUD } from "./GhostPreceptorHUD";
import { OscePostMortemAndRadar } from "./OscePostMortemAndRadar";

interface SpeechRecognitionResultItem {
  transcript: string;
}

interface SpeechRecognitionEventLike {
  resultIndex?: number;
  results: {
    length: number;
    [index: number]: {
      length: number;
      isFinal?: boolean;
      [itemIndex: number]: SpeechRecognitionResultItem;
    };
  };
}

interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
}

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
  const [timeLeft, setTimeLeft] = useState<number>(station.duration_seconds || 480);
  const [transcript, setTranscript] = useState<OsceTranscriptItem[]>([]);
  const [inputText, setInputText] = useState("");
  const [conductText, setConductText] = useState("");
  const [activeTab, setActiveTab] = useState<"physical" | "procedures" | "labs" | "conduct">("physical");
  const [vitals, setVitals] = useState<Record<string, string> | null>(null);
  const [selectedExam, setSelectedExam] = useState<{ title: string; image_url?: string; result_text?: string } | null>(null);
  const [report, setReport] = useState<OsceFinishResponse | null>(null);
  const [isExportingCards, setIsExportingCards] = useState(false);
  const [cardsExported, setCardsExported] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Estados do Modo Duplo (Prova Cega vs Treino Guiado com Preceptor Fantasma)
  const [selectedMode, setSelectedMode] = useState<"blind" | "guided">("guided");
  const [sessionMode, setSessionMode] = useState<"blind" | "guided">("guided");
  const [liveFeedback, setLiveFeedback] = useState<OsceLiveFeedback | null>(null);

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

  // Estados Exclusivos do Modo Hands-Free
  const [handsFreeMode, setHandsFreeMode] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
    return !isOpera;
  });
  const [interimSpeechText, setInterimSpeechText] = useState("");
  const [activeSpeaker, setActiveSpeaker] = useState<"examinador" | "paciente" | null>(null);
  const [micPermission, setMicPermission] = useState<"granted" | "denied" | "prompt" | "unsupported">(() => {
    if (typeof window === "undefined") return "prompt";
    const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
    if (isOpera) return "unsupported";
    const SpeechRecognition = (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance; webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).SpeechRecognition ||
                              (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance; webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).webkitSpeechRecognition;
    if (!SpeechRecognition) return "unsupported";
    return "prompt";
  });
  const [micErrorMsg, setMicErrorMsg] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
    if (isOpera) {
      return "Navegador Opera detectado: O motor Google Speech de transcrição em tempo real requer Google Chrome ou Microsoft Edge. No Opera, você pode realizar a prova normalmente via chat ou atalhos rápidos!";
    }
    const SpeechRecognition = (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance; webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).SpeechRecognition ||
                              (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance; webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      return "Reconhecimento de voz não suportado neste navegador. Recomendamos Google Chrome ou Microsoft Edge.";
    }
    return null;
  });

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isAudioSpeakingRef = useRef<boolean>(false);
  const startListeningRef = useRef<(userTriggered?: boolean) => Promise<void>>(async () => {});
  const handleDispatchSpeechRef = useRef<(spokenText: string) => Promise<void>>(async () => {});

  // Monitoramento assíncrono e reativo das permissões nativas de microfone
  useEffect(() => {
    if (typeof window === "undefined") return;

    const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
    if (isOpera) return;

    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: "microphone" as PermissionName }).then((status) => {
        if (status.state === "granted") {
          setMicPermission("granted");
          setMicErrorMsg(null);
        } else if (status.state === "denied") {
          setMicPermission("denied");
          setMicErrorMsg("Microfone bloqueado nas permissões do navegador. Clique no ícone de cadeado 🔒 na barra de URL para autorizar.");
        } else {
          setMicPermission("prompt");
        }

        status.onchange = () => {
          if (status.state === "granted") {
            setMicPermission("granted");
            setMicErrorMsg(null);
          } else if (status.state === "denied") {
            setMicPermission("denied");
            setMicErrorMsg("Microfone bloqueado nas permissões do navegador. Clique no ícone de cadeado 🔒 na barra de URL para autorizar.");
          } else {
            setMicPermission("prompt");
          }
        };
      }).catch(() => {});
    }
  }, []);

  // Efeito sonoro do sino oficial da banca usando Web Audio API
  const playExamBell = useCallback((type: "warning" | "finish" | "start") => {
    try {
      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);

      if (type === "warning") {
        // Sino duplo aos 5 minutos
        osc.frequency.setValueAtTime(660, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 1.2);
        osc.start();
        osc.stop(audioCtx.currentTime + 1.2);
      } else if (type === "finish") {
        // Sino grave de encerramento
        osc.frequency.setValueAtTime(440, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 2.0);
        osc.start();
        osc.stop(audioCtx.currentTime + 2.0);
      } else {
        // Sinal de início
        osc.frequency.setValueAtTime(880, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.8);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.8);
      }
    } catch {
      // AudioContext não suportado ou bloqueado
    }
  }, []);

  // Autoscroll no transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Síntese de áudio encadeada com vozes distintas para Examinador e Paciente
  const speakSpokenQueue = useCallback((queue: OsceSpokenQueueItem[]) => {
    if (!voiceEnabled || typeof window === "undefined" || !("speechSynthesis" in window) || queue.length === 0) {
      if (handsFreeMode && phase === "exam") {
        setTimeout(() => startListeningRef.current(false), 300);
      }
      return;
    }

    try {
      window.speechSynthesis.cancel();
      isAudioSpeakingRef.current = true;

      // Pausa reconhecimento para não capturar a própria voz do computador
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch {}
      }
      setIsListening(false);

      // Trava de segurança para evitar que a flag fique travada caso o evento onend falhe
      const safetyTimeout = setTimeout(() => {
        if (isAudioSpeakingRef.current) {
          isAudioSpeakingRef.current = false;
          setActiveSpeaker(null);
          if (handsFreeMode && phase === "exam") {
            startListeningRef.current(false);
          }
        }
      }, 9000);

      const voices = window.speechSynthesis.getVoices();
      const ptVoices = voices.filter(v => v.lang.startsWith("pt"));

      let idx = 0;
      const playNext = () => {
        if (idx >= queue.length) {
          clearTimeout(safetyTimeout);
          setActiveSpeaker(null);
          isAudioSpeakingRef.current = false;
          // Ao terminar a fala do sistema, se estiver no modo Hands-Free, reativa o microfone
          if (handsFreeMode && phase === "exam") {
            setTimeout(() => {
              startListeningRef.current(false);
            }, 300);
          }
          return;
        }

        const item = queue[idx];
        idx++;
        setActiveSpeaker(item.speaker);

        const clean = item.text.replace(/[*_#`]/g, "");
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.lang = "pt-BR";

        if (item.speaker === "examinador") {
          utterance.rate = 1.08;
          utterance.pitch = 0.92;
          const maleOrStandard = ptVoices.find(v => {
            const n = v.name.toLowerCase();
            return n.includes("daniel") || n.includes("jorge") || n.includes("male") || n.includes("ricardo");
          });
          if (maleOrStandard) utterance.voice = maleOrStandard;
        } else {
          const isFemale = station.patient_persona.gender?.toLowerCase() === "feminino";
          utterance.rate = 0.98;
          utterance.pitch = isFemale ? 1.15 : 0.92;
          const matchedVoice = ptVoices.find(v => {
            const n = v.name.toLowerCase();
            return isFemale 
              ? (n.includes("maria") || n.includes("francisca") || n.includes("female") || n.includes("luciana"))
              : (n.includes("male") || n.includes("daniel") || n.includes("jorge"));
          });
          if (matchedVoice) utterance.voice = matchedVoice;
        }

        utterance.onend = () => {
          playNext();
        };
        utterance.onerror = () => {
          playNext();
        };

        window.speechSynthesis.speak(utterance);
      };

      playNext();
    } catch {
      setActiveSpeaker(null);
      isAudioSpeakingRef.current = false;
      if (handsFreeMode && phase === "exam") startListeningRef.current(false);
    }
  }, [voiceEnabled, handsFreeMode, phase, station.patient_persona.gender]);

  // Parar microfone e timers
  const stopRecognition = useCallback(() => {
    if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
    if (recognitionRef.current) {
      try { 
        recognitionRef.current.abort(); 
      } catch {}
      recognitionRef.current = null;
    }
    setIsListening(false);
    setInterimSpeechText("");
  }, []);

  // Solicita permissão de microfone explicitamente via getUserMedia
  const requestMicrophonePermission = useCallback(async (): Promise<boolean> => {
    if (typeof window === "undefined") return false;

    // Detecta se o navegador é o Opera (que não possui suporte ao Google Speech API)
    const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
    if (isOpera) {
      setMicPermission("unsupported");
      setMicErrorMsg("Navegador Opera detectado: O motor Google Speech de transcrição contínua requer Google Chrome ou Microsoft Edge. No Opera, você pode realizar a prova normalmente via chat ou atalhos rápidos!");
      toast("Para comandos por voz viva-voz, utilize o Google Chrome ou Edge.", { icon: "💡" });
      return false;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission("unsupported");
      setMicErrorMsg("Seu navegador não suporta captura de microfone. Recomendamos Google Chrome ou Microsoft Edge.");
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission("granted");
      setMicErrorMsg(null);
      toast.success("Microfone autorizado com sucesso!");
      return true;
    } catch (err: unknown) {
      const errorName = err instanceof Error ? err.name : "";
      if (errorName === "NotAllowedError" || errorName === "PermissionDeniedError") {
        setMicPermission("denied");
        setMicErrorMsg("Microfone bloqueado no navegador: Clique no ícone de cadeado 🔒 na barra de URL e mude Microfone para 'Permitir'.");
        toast.error("Microfone bloqueado: libere no ícone de cadeado 🔒.");
      } else {
        setMicPermission("denied");
        setMicErrorMsg("Nenhum microfone encontrado ou dispositivo em uso por outro aplicativo.");
        toast.error("Erro no dispositivo de microfone.");
      }
      return false;
    }
  }, []);

  // Dispatcher Unificado de Voz (Modo Hands-Free)
  const handleDispatchSpeech = useCallback(async (spokenText: string) => {
    const text = spokenText.trim();
    if (!text || !sessionId || isLoading) return;

    const elapsed = (station.duration_seconds || 480) - timeLeft;
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
      } else if (handsFreeMode) {
        setTimeout(() => startListeningRef.current(false), 300);
      }
    } catch (err) {
      console.error("Falha no speech dispatcher:", err);
      if (handsFreeMode) {
        setTimeout(() => startListeningRef.current(false), 300);
      }
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, isLoading, station.duration_seconds, timeLeft, speakSpokenQueue, handsFreeMode]);

  // Iniciar Reconhecimento Contínuo com VAD (Detecção de Silêncio)
  const startListening = useCallback(async (userTriggered = false) => {
    if (typeof window === "undefined") return;

    // Detecta se o navegador é o Opera (sem suporte aos servidores Google Speech)
    const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
    if (isOpera) {
      if (userTriggered) {
        toast("Para falar por viva-voz contínuo, utilize o Google Chrome ou Microsoft Edge.", { icon: "💡" });
      }
      return;
    }

    const SpeechRecognition = (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance; webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).SpeechRecognition ||
                              (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance; webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setMicPermission("unsupported");
      setMicErrorMsg("Reconhecimento de voz não suportado neste navegador. Recomendamos Google Chrome ou Microsoft Edge.");
      if (userTriggered) {
        toast.error("Voz não suportada neste navegador. Use Google Chrome ou Edge.");
      }
      return;
    }

    // REGRA DE OURO: Se a permissão ainda não foi concedida, NUNCA tenta iniciar em background!
    if (micPermission !== "granted") {
      if (userTriggered) {
        const ok = await requestMicrophonePermission();
        if (!ok) return;
      } else {
        // Chamada em segundo plano aborta silenciosamente até que o usuário autorize
        return;
      }
    }

    if (isAudioSpeakingRef.current) return;

    try {
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch {}
        recognitionRef.current = null;
      }

      const rec = new SpeechRecognition();
      rec.lang = "pt-BR";
      rec.continuous = true;
      rec.interimResults = true;

      rec.onstart = () => {
        setIsListening(true);
        setMicErrorMsg(null);
      };

      rec.onend = () => {
        setIsListening(false);
        // Reinício automático seguro no modo Viva-Voz se estiver na fase exam e com permissão confirmada
        if (handsFreeMode && phase === "exam" && !isAudioSpeakingRef.current && !isLoading && micPermission === "granted") {
          setTimeout(() => {
            if (!isAudioSpeakingRef.current && !isLoading) {
              startListeningRef.current(false);
            }
          }, 350);
        }
      };

      rec.onerror = (event: { error?: string }) => {
        setIsListening(false);
        const errType = event?.error;
        if (errType === "not-allowed" || errType === "service-not-allowed") {
          if (userTriggered) {
            setMicPermission("denied");
            setMicErrorMsg("Microfone bloqueado: Clique no ícone de cadeado 🔒 na barra de URL para autorizar.");
            toast.error("Permissão de microfone negada no navegador.");
          }
        } else if (errType === "audio-capture") {
          setMicErrorMsg("Nenhum sinal de microfone detectado no dispositivo.");
        }
      };

      rec.onresult = (event: SpeechRecognitionEventLike) => {
        let interim = "";
        let final = "";

        const resultsObj = event.results;
        for (let i = 0; i < resultsObj.length; ++i) {
          const item = resultsObj[i]?.[0];
          if (item) {
            if (resultsObj[i]?.isFinal) {
              final += item.transcript;
            } else {
              interim += item.transcript;
            }
          }
        }

        const candidateText = (final || interim).trim();
        if (candidateText) {
          setInterimSpeechText(candidateText);

          if (silenceTimeoutRef.current) {
            clearTimeout(silenceTimeoutRef.current);
          }

          // Debounce de 1.4s após o candidato terminar a frase
          silenceTimeoutRef.current = setTimeout(() => {
            if (candidateText.length >= 2 && !isAudioSpeakingRef.current) {
              handleDispatchSpeechRef.current(candidateText);
              setInterimSpeechText("");
            }
          }, 1400);
        }
      };

      recognitionRef.current = rec;
      rec.start();
    } catch {
      setIsListening(false);
    }
  }, [micPermission, requestMicrophonePermission, handsFreeMode, phase, isLoading]);

  // Sincroniza refs para chamadas livres de ciclo
  useEffect(() => {
    startListeningRef.current = startListening;
    handleDispatchSpeechRef.current = handleDispatchSpeech;
  }, [startListening, handleDispatchSpeech]);

  // Toggle do modo Hands-Free (Viva-Voz contínuo)
  const toggleHandsFreeMode = useCallback(() => {
    if (typeof window !== "undefined") {
      const isOpera = /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
      if (isOpera) {
        toast("No Opera, o reconhecimento de fala contínuo não é suportado. Use Google Chrome ou Edge para viva-voz contínuo.", { icon: "💡" });
        return;
      }
    }
    if (handsFreeMode) {
      setHandsFreeMode(false);
      stopRecognition();
      toast("Modo Viva-Voz contínuo desligado. Clique no microfone para falar.", { icon: "🎙️" });
    } else {
      setHandsFreeMode(true);
      toast.success("Modo Viva-Voz contínuo ativado!");
      setTimeout(() => startListening(true), 200);
    }
  }, [handsFreeMode, stopRecognition, startListening]);

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
      setTimeLeft(res.duration_seconds || 480);
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
    if (timerRef.current) clearInterval(timerRef.current);
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
  }, [sessionId, conductText, isLoading, playExamBell, stopRecognition]);

  // Cronômetro de Prova
  useEffect(() => {
    if (phase !== "exam") return;

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          handleFinishExam();
          return 0;
        }
        if (prev === 180) {
          // Aviso aos 5 minutos (faltam 3 min)
          playExamBell("warning");
        }
        if (prev === 60) {
          // Aviso do último minuto (sino oficial + síntese de voz da banca + toast)
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
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [phase, handleFinishExam, playExamBell, voiceEnabled, speakSpokenQueue]);

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
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          window.speechSynthesis.cancel();
          isAudioSpeakingRef.current = false;
          setActiveSpeaker(null);
          if (handsFreeMode) {
            setTimeout(() => startListening(false), 200);
          }
        }
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
  }, [phase, handsFreeMode, isListening, startListening, stopRecognition, setActiveTab, toggleHandsFreeMode]);

  // Enviar mensagem manual por texto ou clique
  const handleSendMessage = async (msgToSend?: string) => {
    const text = (msgToSend || inputText).trim();
    if (!text || !sessionId || isLoading) return;

    setInputText("");
    await handleDispatchSpeech(text);
  };

  // Toggle direto e intuitivo do microfone
  const toggleListening = () => {
    if (isListening) {
      stopRecognition();
    } else {
      startListening(true);
    }
  };

  // Solicitar Ação Clínica (Exame Físico / Sinais Vitais / Exames)
  const handleClinicalAction = async (actionType: "physical_exam" | "vitals" | "lab_imaging", target: string) => {
    if (!sessionId || isLoading) return;
    const elapsed = (station.duration_seconds || 480) - timeLeft;
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

      if (actionType === "vitals" && res.payload.vitals) {
        setVitals(res.payload.vitals as Record<string, string>);
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

    const elapsed = (station.duration_seconds || 480) - timeLeft;
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

    const elapsed = (station.duration_seconds || 480) - timeLeft;
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

  // Polling suave do Preceptor Fantasma para atualizar alertas proativos baseados no tempo restante
  useEffect(() => {
    if (phase !== "exam" || sessionMode !== "guided" || !sessionId) return;

    const interval = setInterval(async () => {
      try {
        const elapsed = (station.duration_seconds || 480) - timeLeft;
        const feedback = await api.osce.getLiveFeedback(sessionId, elapsed);
        if (feedback) {
          setLiveFeedback(feedback);
        }
      } catch {
        // Silencioso em caso de atraso na rede
      }
    }, 20000);

    return () => clearInterval(interval);
  }, [phase, sessionMode, sessionId, station.duration_seconds, timeLeft]);

  // Exportar flashcards de choque
  const handleExportShockCards = async () => {
    if (!sessionId || isExportingCards || cardsExported) return;
    setIsExportingCards(true);
    try {
      const res = await api.osce.exportCards(sessionId);
      if (res.success) {
        setCardsExported(true);
      }
    } catch (err) {
      console.error("Falha ao exportar flashcards:", err);
    } finally {
      setIsExportingCards(false);
    }
  };

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const timeFormatted = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

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

              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-mono text-base font-black border ${
                timeLeft < 60 
                  ? "bg-rose-500/10 text-rose-500 border-rose-500/30 animate-pulse" 
                  : timeLeft < 180 
                  ? "bg-amber-500/10 text-amber-500 border-amber-500/30" 
                  : "bg-emerald-500/10 text-emerald-500 border-emerald-500/30"
              }`}>
                <Clock className="w-4 h-4" />
                <span>{timeFormatted}</span>
              </div>

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

          {/* Grid Principal: Chat com Paciente (Esq) + Painel de Ações Clínicas (Dir) */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
            {/* Coluna Esquerda: Chat & Diálogo com o Paciente (7 cols) */}
            <div className="lg:col-span-7 flex flex-col rounded-2xl border border-border bg-card overflow-hidden min-h-0">
              {/* Header do Paciente */}
              <div className="p-3 bg-muted/30 border-b border-border flex items-center justify-between text-xs">
                <span className="font-bold text-foreground flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-primary" />
                  Paciente Simulado no Leito
                </span>
                <span className="text-muted-foreground text-xs">
                  Queixa: &ldquo;{station.patient_persona.chief_complaint || "Dor aguda"}&rdquo;
                </span>
              </div>

              {/* Histórico da Conversa */}
              <div className="flex-1 p-4 overflow-y-auto space-y-3.5 text-sm">
                {transcript.map((item, idx) => {
                  const isCandidate = item.sender === "candidato";
                  const isExaminer = item.sender === "examinador";

                  if (isExaminer) {
                    return (
                      <div key={idx} className="p-3 rounded-xl bg-muted/60 border border-border text-xs text-muted-foreground space-y-1">
                        <div className="font-bold text-foreground flex items-center gap-1.5">
                          <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                          Examinador Oficial da Banca:
                        </div>
                        <p className="text-foreground/90 font-medium">{item.message}</p>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={idx}
                      className={`flex flex-col ${isCandidate ? "items-end" : "items-start"}`}
                    >
                      <div className="text-[10px] text-muted-foreground mb-1 px-1">
                        {isCandidate ? "Você (Candidato)" : station.patient_persona.name || "Paciente"}
                      </div>
                      <div
                        className={`max-w-[85%] px-4 py-2.5 rounded-2xl leading-relaxed ${
                          isCandidate
                            ? "bg-primary text-primary-foreground rounded-tr-sm"
                            : "bg-muted text-foreground rounded-tl-sm border border-border"
                        }`}
                      >
                        {item.message}
                      </div>
                    </div>
                  );
                })}
                <div ref={transcriptEndRef} />
              </div>

              {/* Caixa de Entrada (Voz + Texto) */}
              <div className="p-3 border-t border-border bg-card flex items-center gap-2">
                <button
                  type="button"
                  onClick={toggleListening}
                  title={
                    micPermission === "unsupported"
                      ? "Voz contínua requer Chrome ou Edge. No Opera, envie mensagens digitando ou pelos botões rápidos!"
                      : isListening
                        ? "Microfone ouvindo você (clique para pausar)"
                        : "Ativar microfone para falar"
                  }
                  className={`p-2.5 rounded-xl border transition-all flex items-center justify-center shrink-0 cursor-pointer ${
                    isListening
                      ? "bg-emerald-500 text-white border-emerald-600 shadow-md ring-2 ring-emerald-500/40 animate-pulse"
                      : micPermission === "unsupported"
                        ? "bg-muted text-muted-foreground border-border hover:bg-muted/80 opacity-70"
                        : "bg-muted hover:bg-muted/80 text-foreground border-border"
                  }`}
                >
                  {isListening ? <Mic className="w-4 h-4 text-white" /> : <MicOff className="w-4 h-4 opacity-70" />}
                </button>

                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                  placeholder={
                    isListening
                      ? "Modo Viva-Voz ouvindo você... (ou digite aqui se preferir)"
                      : micPermission === "unsupported"
                        ? "Digite sua pergunta ao paciente ou examinador..."
                        : "Pergunte ao paciente ou fale com o examinador... (ou aperte Espaço para falar)"
                  }
                  className="flex-1 bg-muted/50 border border-border rounded-xl px-3.5 py-2.5 text-xs md:text-sm focus:outline-none focus:border-primary"
                />

                <button
                  onClick={() => handleSendMessage()}
                  disabled={isLoading || !inputText.trim()}
                  className="p-2.5 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-transform active:scale-95"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
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

                    {/* Sinais Vitais Exibidos */}
                    {vitals && (
                      <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-muted/20 border border-border font-mono text-[11px]">
                        <div>PA: <span className="font-bold text-foreground">{vitals.pa}</span></div>
                        <div>FC: <span className="font-bold text-foreground">{vitals.fc}</span></div>
                        <div>FR: <span className="font-bold text-foreground">{vitals.fr}</span></div>
                        <div>SatO2: <span className="font-bold text-foreground">{vitals.sato2}</span></div>
                        <div>Temp: <span className="font-bold text-foreground">{vitals.temp}</span></div>
                        {vitals.hgt && <div>Glic: <span className="font-bold text-foreground">{vitals.hgt}</span></div>}
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
                        elapsedSeconds={(station.duration_seconds || 480) - timeLeft}
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
                        elapsedSeconds={(station.duration_seconds || 480) - timeLeft}
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

          {/* Header do Espelho na Tela */}
          <div className="text-center space-y-2 border-b border-border pb-6 print:hidden">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase">
              <Award className="w-4 h-4" />
              <span>Espelho Oficial de Correção da Banca</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-black text-foreground">
              {station.title} ({station.institution})
            </h1>
            <div className="text-xs text-muted-foreground font-medium">
              Avaliação e Barema de 2ª Fase Presencial
            </div>
          </div>

          {/* Card da Nota Oficial */}
          <div className={`p-6 rounded-2xl border-2 flex flex-col md:flex-row md:items-center justify-between gap-4 ${
            report.preceptor_feedback.approved
              ? "bg-emerald-500/10 border-emerald-500/30"
              : "bg-rose-500/10 border-rose-500/30"
          }`}>
            <div className="space-y-1">
              <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Nota Final Obtida
              </div>
              <div className={`text-4xl font-black ${
                report.preceptor_feedback.approved ? "text-emerald-500" : "text-rose-500"
              }`}>
                {report.final_score.toFixed(1)} <span className="text-xl text-muted-foreground">/ 10.0</span>
              </div>
              <div className="text-xs font-semibold text-foreground/90">
                {report.preceptor_feedback.approved ? "Aprovado na Estação" : "Pontuação Insuficiente / Reprovado"}
              </div>
            </div>

            <div className="text-xs max-w-md text-foreground/80 leading-relaxed">
              {report.preceptor_feedback.summary}
            </div>
          </div>

          {/* Alertas de Erros Críticos Eliminatórios */}
          {report.preceptor_feedback.critical_warnings?.length > 0 && (
            <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/5 space-y-2">
              <div className="flex items-center gap-2 text-rose-500 font-bold text-xs">
                <AlertTriangle className="w-4 h-4" />
                FALTAS GRAVES / CONDUTAS DE RISCO IDENTIFICADAS:
              </div>
              <ul className="list-disc list-inside text-xs text-rose-400 space-y-1">
                {report.preceptor_feedback.critical_warnings.map((warn, i) => (
                  <li key={i}>{warn}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Radar de Competências Clínicas & Linha do Tempo Beira-Leito (Post-Mortem) */}
          <OscePostMortemAndRadar 
            timeline={report.timeline_post_mortem}
            radar={report.competency_radar}
          />

          {/* Tabela do Barema Item a Item */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-foreground">
              Checklist Oficial do Barema de Correção:
            </h3>

            <div className="border border-border rounded-2xl overflow-hidden divide-y divide-border bg-card">
              {report.evaluated_items.map((item) => (
                <div key={item.id} className="p-4 space-y-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-foreground text-sm">
                      {item.title}
                    </span>
                    <span className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${
                      item.status === "cumprido_total"
                        ? "bg-emerald-500/15 text-emerald-500"
                        : item.status === "cumprido_parcial"
                        ? "bg-amber-500/15 text-amber-500"
                        : "bg-rose-500/15 text-rose-500"
                    }`}>
                      {item.score_earned.toFixed(1)} / {item.weight.toFixed(1)} pts
                    </span>
                  </div>

                  <p className="text-muted-foreground text-xs leading-relaxed">
                    <strong>Evidência:</strong> {item.evidence}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Exportar Flashcards de Choque */}
          {report.shock_cards?.length > 0 && (
            <div className="p-5 rounded-2xl border border-primary/20 bg-primary/5 flex flex-col md:flex-row md:items-center justify-between gap-4 print:hidden">
              <div className="space-y-1">
                <div className="flex items-center gap-2 font-bold text-foreground text-sm">
                  <Sparkles className="w-4 h-4 text-primary" />
                  Flashcards de Choque do Barema
                </div>
                <p className="text-xs text-muted-foreground">
                  Identificamos {report.shock_cards.length} pontos não cumpridos. Adicione-os à sua fila de repetição espaçada FSRS para nunca mais errar em prova.
                </p>
              </div>

              <button
                onClick={handleExportShockCards}
                disabled={isExportingCards || cardsExported}
                className="px-5 py-2.5 rounded-xl font-bold bg-primary text-primary-foreground hover:bg-primary/90 text-xs shadow-sm transition-transform active:scale-95 shrink-0"
              >
                {cardsExported ? "Cards Adicionados ao FSRS ✓" : isExportingCards ? "Exportando..." : "Exportar Flashcards de Choque"}
              </button>
            </div>
          )}

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
