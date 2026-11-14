"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "react-hot-toast";
import { OsceSpokenQueueItem } from "@/types/api";

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

type SpeechRecognitionWindow = {
  SpeechRecognition?: new () => SpeechRecognitionInstance;
  webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
};

function isOperaBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  return /OPR\//i.test(navigator.userAgent) || /Opera/i.test(navigator.userAgent);
}

function getSpeechRecognitionConstructor(): (new () => SpeechRecognitionInstance) | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as SpeechRecognitionWindow;
  return w.SpeechRecognition || w.webkitSpeechRecognition;
}

export interface UseOsceAudioOptions {
  phase: "door" | "exam" | "finished";
  patientGender?: string;
  isLoading: boolean;
  onDispatchSpeech: (spokenText: string) => Promise<void>;
}

/**
 * Encapsula a camada de áudio da estação OSCE:
 * - Sino de prova (Web Audio API)
 * - Síntese de fala encadeada Examinador/Paciente (Web Speech Synthesis)
 * - Reconhecimento de voz contínuo Hands-Free com debounce de silêncio e permissões
 */
export function useOsceAudio({
  phase,
  patientGender,
  isLoading,
  onDispatchSpeech,
}: UseOsceAudioOptions) {
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [handsFreeMode, setHandsFreeMode] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return !isOperaBrowser();
  });
  const [interimSpeechText, setInterimSpeechText] = useState("");
  const [activeSpeaker, setActiveSpeaker] = useState<"examinador" | "paciente" | null>(null);
  const [micPermission, setMicPermission] = useState<"granted" | "denied" | "prompt" | "unsupported">(() => {
    if (typeof window === "undefined") return "prompt";
    if (isOperaBrowser() || !getSpeechRecognitionConstructor()) return "unsupported";
    return "prompt";
  });
  const [micErrorMsg, setMicErrorMsg] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    if (isOperaBrowser()) {
      return "Navegador Opera detectado: O motor Google Speech de transcrição em tempo real requer Google Chrome ou Microsoft Edge. No Opera, você pode realizar a prova normalmente via chat ou atalhos rápidos!";
    }
    if (!getSpeechRecognitionConstructor()) {
      return "Reconhecimento de voz não suportado neste navegador. Recomendamos Google Chrome ou Microsoft Edge.";
    }
    return null;
  });

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isAudioSpeakingRef = useRef<boolean>(false);
  const startListeningRef = useRef<(userTriggered?: boolean) => Promise<void>>(async () => {});
  const onDispatchSpeechRef = useRef(onDispatchSpeech);

  useEffect(() => {
    onDispatchSpeechRef.current = onDispatchSpeech;
  }, [onDispatchSpeech]);

  useEffect(() => {
    if (typeof window === "undefined" || isOperaBrowser()) return;

    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: "microphone" as PermissionName }).then((status) => {
        const applyState = (state: PermissionState) => {
          if (state === "granted") {
            setMicPermission("granted");
            setMicErrorMsg(null);
          } else if (state === "denied") {
            setMicPermission("denied");
            setMicErrorMsg("Microfone bloqueado nas permissões do navegador. Clique no ícone de cadeado 🔒 na barra de URL para autorizar.");
          } else {
            setMicPermission("prompt");
          }
        };
        applyState(status.state);
        status.onchange = () => applyState(status.state);
      }).catch(() => {});
    }
  }, []);

  const playExamBell = useCallback((type: "warning" | "finish" | "start") => {
    try {
      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);

      if (type === "warning") {
        osc.frequency.setValueAtTime(660, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 1.2);
        osc.start();
        osc.stop(audioCtx.currentTime + 1.2);
      } else if (type === "finish") {
        osc.frequency.setValueAtTime(440, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 2.0);
        osc.start();
        osc.stop(audioCtx.currentTime + 2.0);
      } else {
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

      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch {}
      }
      setIsListening(false);

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
          const isFemale = patientGender?.toLowerCase() === "feminino";
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

        utterance.onend = () => playNext();
        utterance.onerror = () => playNext();
        window.speechSynthesis.speak(utterance);
      };

      playNext();
    } catch {
      setActiveSpeaker(null);
      isAudioSpeakingRef.current = false;
      if (handsFreeMode && phase === "exam") startListeningRef.current(false);
    }
  }, [voiceEnabled, handsFreeMode, phase, patientGender]);

  const requestMicrophonePermission = useCallback(async (): Promise<boolean> => {
    if (typeof window === "undefined") return false;

    if (isOperaBrowser()) {
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

  const startListening = useCallback(async (userTriggered = false) => {
    if (typeof window === "undefined") return;

    if (isOperaBrowser()) {
      if (userTriggered) {
        toast("Para falar por viva-voz contínuo, utilize o Google Chrome ou Microsoft Edge.", { icon: "💡" });
      }
      return;
    }

    const SpeechRecognition = getSpeechRecognitionConstructor();
    if (!SpeechRecognition) {
      setMicPermission("unsupported");
      setMicErrorMsg("Reconhecimento de voz não suportado neste navegador. Recomendamos Google Chrome ou Microsoft Edge.");
      if (userTriggered) {
        toast.error("Voz não suportada neste navegador. Use Google Chrome ou Edge.");
      }
      return;
    }

    if (micPermission !== "granted") {
      if (userTriggered) {
        const ok = await requestMicrophonePermission();
        if (!ok) return;
      } else {
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

          silenceTimeoutRef.current = setTimeout(() => {
            if (candidateText.length >= 2 && !isAudioSpeakingRef.current) {
              onDispatchSpeechRef.current(candidateText);
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

  useEffect(() => {
    startListeningRef.current = startListening;
  }, [startListening]);

  const toggleHandsFreeMode = useCallback(() => {
    if (isOperaBrowser()) {
      toast("No Opera, o reconhecimento de fala contínuo não é suportado. Use Google Chrome ou Edge para viva-voz contínuo.", { icon: "💡" });
      return;
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

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopRecognition();
    } else {
      startListening(true);
    }
  }, [isListening, stopRecognition, startListening]);

  const resumeAfterSpeechFailure = useCallback(() => {
    if (handsFreeMode) {
      setTimeout(() => startListeningRef.current(false), 300);
    }
  }, [handsFreeMode]);

  const cancelSpeechSynthesis = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    isAudioSpeakingRef.current = false;
    setActiveSpeaker(null);
    if (handsFreeMode) {
      setTimeout(() => startListeningRef.current(false), 200);
    }
  }, [handsFreeMode]);

  return {
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
  };
}
