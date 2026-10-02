"use client";

import React, { useRef, useEffect } from "react";
import { Stethoscope, Sparkles, BookOpen, Send, RotateCcw, Zap, AlertTriangle, Layers, Target, TrendingUp, Clock } from "lucide-react";
import { FormattedContent } from "@/components/FormattedContent";

export interface GroundingSource {
  source_file: string;
  source_type?: string;
  topic?: string;
  subtopic?: string;
  title?: string;
}

export interface WeakTopicItem {
  topic: string;
  area: string;
  attempts: number;
  correct: number;
  wrong: number;
  accuracy_pct: number;
}

export interface ToolCallData {
  name: string;
  data: {
    status?: string;
    has_data?: boolean;
    total_attempts?: number;
    overall_accuracy_pct?: number;
    srs_due_count?: number;
    weak_topics?: WeakTopicItem[];
    message?: string;
  };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  model?: string;
  source?: string;
  grounding_sources?: GroundingSource[];
  tool_call?: ToolCallData;
}

export interface PreceptorSectionProps {
  messages: ChatMessage[];
  preceptorInput: string;
  askingPreceptor: boolean;
  onChangeInput: (value: string) => void;
  onSendMessage: (overrideText?: string) => void;
  onClearChat: () => void;
}

const QUICK_ACTIONS = [
  { label: "/foco", icon: Target, prompt: "/foco", desc: "Diagnóstico adaptativo e temas fracos" },
  { label: "/conduta", icon: Zap, prompt: "/conduta", desc: "Algoritmo de conduta, drogas e doses" },
  { label: "/pegadinhas", icon: AlertTriangle, prompt: "/pegadinhas", desc: "Armadilhas clássicas de bancas" },
  { label: "/round", icon: Stethoscope, prompt: "/round", desc: "Perguntas afiadas beira-leito" },
  { label: "/caso", icon: Layers, prompt: "/caso", desc: "Desafio clínico correlato" },
];

export const PreceptorSection: React.FC<PreceptorSectionProps> = ({
  messages,
  preceptorInput,
  askingPreceptor,
  onChangeInput,
  onSendMessage,
  onClearChat,
}) => {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length > 0) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, askingPreceptor]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!askingPreceptor && preceptorInput.trim()) {
        onSendMessage();
      }
    }
  };

  return (
    <div className="mt-8 bg-blue-500/5 border border-blue-500/20 rounded-2xl p-5 md:p-6 transition-all">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-blue-700 dark:text-blue-400 font-bold flex items-center gap-2 uppercase tracking-wider text-sm">
          <Stethoscope size={18} /> Discussão Clínica & Preceptor IA
        </h4>
        {messages.length > 0 && (
          <button
            onClick={onClearChat}
            disabled={askingPreceptor}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
            title="Reiniciar discussão clínica"
          >
            <RotateCcw size={13} />
            <span>Reiniciar Chat</span>
          </button>
        )}
      </div>

      {messages.length === 0 ? (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Tire dúvidas conceituais, discuta diagnósticos diferenciais ou use comandos socráticos rápidos:
          </p>

          {/* Quick Prompts Bar */}
          <div className="flex flex-wrap gap-2 pt-1">
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.label}
                  type="button"
                  onClick={() => onSendMessage(action.prompt)}
                  disabled={askingPreceptor}
                  className="text-xs font-semibold bg-background hover:bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/30 hover:border-blue-500/60 px-2.5 py-1.5 rounded-xl flex items-center gap-1.5 transition-all shadow-sm cursor-pointer disabled:opacity-50"
                  title={action.desc}
                >
                  <Icon size={14} className="text-blue-600 dark:text-blue-400" />
                  <span>{action.label}</span>
                </button>
              );
            })}
          </div>

          <textarea
            className="w-full bg-background border border-border rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[85px] mt-1"
            placeholder="Qual conduta você tem dúvida? Ex: 'Por que a alternativa D está errada?' ou aperte Enter..."
            value={preceptorInput}
            onChange={(e) => onChangeInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <div className="flex justify-end">
            <button
              onClick={() => onSendMessage()}
              disabled={askingPreceptor || !preceptorInput.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-xl shadow-sm transition-all flex items-center gap-2 text-sm cursor-pointer disabled:cursor-not-allowed"
            >
              {askingPreceptor ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
              {askingPreceptor ? "Consultando Preceptor..." : "Enviar Pergunta"}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Messages Feed */}
          <div className="space-y-3.5 max-h-[550px] overflow-y-auto pr-1">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`rounded-2xl p-4 max-w-[94%] md:max-w-[88%] text-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-background border border-border text-foreground shadow-xs"
                  }`}
                >
                  {/* Grounding Badges (if assistant response has official sources) */}
                  {msg.role === "assistant" && msg.grounding_sources && msg.grounding_sources.length > 0 && (
                    <div className="mb-3.5 pb-2.5 border-b border-border/60">
                      <div className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5 mb-1.5">
                        <BookOpen size={13} />
                        <span>Diretrizes e Fichas Consultadas (Grounding):</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.grounding_sources.map((src, i) => (
                          <span
                            key={i}
                            className="text-[11px] bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-md flex items-center gap-1"
                            title={src.title || src.source_file}
                          >
                            <span className="opacity-70">📄</span>
                            <span className="font-medium">{src.source_file.replace(/\.(pdf|txt)$/i, "")}</span>
                            {src.topic && <span className="opacity-60 text-[10px]">({src.topic})</span>}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tool Calling Diagnostic Card */}
                  {msg.role === "assistant" && msg.tool_call?.name === "get_student_weak_topics" && msg.tool_call.data && (
                    <div className="mb-4 p-3.5 bg-blue-500/5 dark:bg-blue-950/20 border border-blue-500/25 rounded-xl">
                      <div className="flex items-center justify-between mb-2 pb-2 border-b border-blue-500/15">
                        <span className="text-xs font-bold text-blue-700 dark:text-blue-300 flex items-center gap-1.5">
                          <Target size={14} /> Diagnóstico Adaptativo do Aluno
                        </span>
                        {msg.tool_call.data.has_data && (
                          <span className="text-[11px] text-muted-foreground font-medium">
                            {msg.tool_call.data.total_attempts} questões resolvidas
                          </span>
                        )}
                      </div>

                      {msg.tool_call.data.has_data ? (
                        <div className="space-y-2.5">
                          <div className="flex items-center gap-4 text-xs">
                            <div className="flex items-center gap-1.5">
                              <TrendingUp size={13} className="text-blue-600 dark:text-blue-400" />
                              <span>Acurácia Global: <strong>{msg.tool_call.data.overall_accuracy_pct}%</strong></span>
                            </div>
                            {(msg.tool_call.data.srs_due_count ?? 0) > 0 && (
                              <div className="flex items-center gap-1.5 text-amber-700 dark:text-amber-400 font-semibold">
                                <Clock size={13} />
                                <span>{msg.tool_call.data.srs_due_count} revisões FSRS pendentes</span>
                              </div>
                            )}
                          </div>

                          {msg.tool_call.data.weak_topics && msg.tool_call.data.weak_topics.length > 0 && (
                            <div className="mt-2 space-y-1.5">
                              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
                                Subtemas com Maior Risco de Erro:
                              </span>
                              {msg.tool_call.data.weak_topics.map((wt, idx) => (
                                <div key={idx} className="flex items-center justify-between text-xs bg-background/80 p-1.5 rounded-lg border border-border/50">
                                  <span className="font-medium truncate max-w-[60%]">{wt.topic} <span className="opacity-60 text-[10px]">({wt.area})</span></span>
                                  <span className={`font-bold px-1.5 py-0.5 rounded text-[11px] ${
                                    wt.accuracy_pct < 50
                                      ? "bg-red-500/15 text-red-700 dark:text-red-400"
                                      : "bg-amber-500/15 text-amber-700 dark:text-amber-400"
                                  }`}>
                                    {wt.accuracy_pct}% ({wt.wrong} erros)
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          Nenhum dado registrado ainda. Resolva questões no quiz para calibrar seu diagnóstico adaptativo!
                        </p>
                      )}
                    </div>
                  )}

                  {msg.role === "user" ? (
                    <div className="font-medium whitespace-pre-wrap">{msg.content}</div>
                  ) : (
                    <div className="leading-relaxed">
                      <FormattedContent content={msg.content} />
                    </div>
                  )}

                  {msg.role === "assistant" && msg.model && (
                    <div className="mt-2.5 pt-2 border-t border-border/40 text-[10px] text-muted-foreground font-mono flex items-center justify-between">
                      <span>Preceptor FMRP-USP ({msg.model})</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {askingPreceptor && (
              <div className="flex items-start">
                <div className="bg-background border border-border rounded-2xl p-4 flex items-center gap-3 text-muted-foreground text-sm">
                  <div className="w-4 h-4 border-2 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
                  <span>Preceptor analisando condutas e diretrizes...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Quick Actions (Mini) when conversation is ongoing */}
          <div className="flex flex-wrap gap-1.5 pt-1 border-t border-border/40">
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.label}
                  type="button"
                  onClick={() => onSendMessage(action.prompt)}
                  disabled={askingPreceptor}
                  className="text-[11px] font-medium bg-background/80 hover:bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20 hover:border-blue-500/40 px-2 py-1 rounded-lg flex items-center gap-1 transition-all cursor-pointer disabled:opacity-50"
                  title={action.desc}
                >
                  <Icon size={12} className="text-blue-600 dark:text-blue-400" />
                  <span>{action.label}</span>
                </button>
              );
            })}
          </div>

          {/* Multi-turn Input Box */}
          <div className="flex gap-2">
            <textarea
              className="flex-1 bg-background border border-border rounded-xl p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[44px] max-h-[120px]"
              placeholder="Digite sua réplica ou dúvida adicional..."
              rows={1}
              value={preceptorInput}
              onChange={(e) => onChangeInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              onClick={() => onSendMessage()}
              disabled={askingPreceptor || !preceptorInput.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold px-3.5 rounded-xl shadow-sm transition-all flex items-center justify-center cursor-pointer disabled:cursor-not-allowed"
              title="Enviar réplica"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
