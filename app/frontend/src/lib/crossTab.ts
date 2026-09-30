/**
 * MedQuest Cross-Tab Event Broker
 * Sincronização em tempo real entre abas e janelas abertas do mesmo navegador
 * utilizando BroadcastChannel com fallback para CustomEvent local e StorageEvent.
 */

const CHANNEL_NAME = "medquest_cross_tab";

let activeChannel: BroadcastChannel | null = null;
let listenerCleanup: (() => void) | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") {
    return null;
  }
  if (!activeChannel) {
    try {
      activeChannel = new BroadcastChannel(CHANNEL_NAME);
    } catch (e) {
      console.warn("[CrossTab] Falha ao instanciar BroadcastChannel:", e);
      return null;
    }
  }
  return activeChannel;
}

/**
 * Dispara um evento tanto na janela atual quanto em todas as outras abas abertas.
 */
export function broadcastCrossTab(name: string, detail?: unknown): void {
  if (typeof window === "undefined") return;

  // Disparo local
  window.dispatchEvent(new CustomEvent(name, { detail }));

  // Disparo para outras abas via BroadcastChannel (BroadcastChannel não ecoa para o emissor)
  const channel = getChannel();
  if (channel) {
    try {
      channel.postMessage({ type: name, detail });
    } catch (err) {
      console.warn("[CrossTab] Erro ao transmitir mensagem cross-tab:", err);
    }
  }
}

/**
 * Inicializa o listener global de eventos entre abas.
 * Deve ser montado no nível do SyncProvider / Layout.
 */
export function initCrossTabListener(): () => void {
  if (typeof window === "undefined") return () => {};

  if (listenerCleanup) {
    return listenerCleanup;
  }

  const channel = getChannel();
  const handleMessage = (event: MessageEvent<{ type?: string; detail?: unknown }>) => {
    if (event.data?.type) {
      window.dispatchEvent(new CustomEvent(event.data.type, { detail: event.data.detail }));
    }
  };

  if (channel) {
    channel.addEventListener("message", handleMessage);
  }

  // Fallback e sincronização via StorageEvent para chaves críticas
  const handleStorage = (e: StorageEvent) => {
    if (!e.key) return;

    if (e.key === "medquest_forced_offline") {
      window.dispatchEvent(new CustomEvent("forced-offline-changed", {
        detail: { forced: e.newValue === "true" }
      }));
    } else if (e.key.includes("medquest_simulado_state") || e.key.includes("medquest_quiz_state")) {
      window.dispatchEvent(new CustomEvent("learning-session-changed", {
        detail: { key: e.key }
      }));
    }
  };

  window.addEventListener("storage", handleStorage);

  listenerCleanup = () => {
    if (channel) {
      channel.removeEventListener("message", handleMessage);
    }
    window.removeEventListener("storage", handleStorage);
    listenerCleanup = null;
  };

  return listenerCleanup;
}
