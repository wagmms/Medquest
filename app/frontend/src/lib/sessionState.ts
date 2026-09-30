import { getLocalOwnerId } from "./db";

export type LearningSessionKind = "quiz" | "simulado";

const LEGACY_KEYS: Record<LearningSessionKind, string> = {
  quiz: "medquest_quiz_state",
  simulado: "medquest_simulado_state",
};

export const LEARNING_SESSION_VERSION = 2;

export function getLearningSessionKey(kind: LearningSessionKind): string {
  return `medquest_${kind}_state_v2:${getLocalOwnerId()}`;
}

function removeLegacyState(kind: LearningSessionKind): void {
  localStorage.removeItem(LEGACY_KEYS[kind]);
  sessionStorage.removeItem(LEGACY_KEYS[kind]);
}

export function readLearningSession<T>(
  kind: LearningSessionKind,
  isValid: (value: unknown) => value is T,
): T | null {
  removeLegacyState(kind);
  const key = getLearningSessionKey(kind);
  const raw = localStorage.getItem(key);
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isValid(parsed)) return parsed;
    } catch {
      // Invalid or partial writes are discarded below.
    }
    localStorage.removeItem(key);
  }

  return null;
}

export function removeLearningSession(kind: LearningSessionKind): void {
  removeLegacyState(kind);
  localStorage.removeItem(getLearningSessionKey(kind));

  if (cloudSaveTimeouts[kind]) {
    clearTimeout(cloudSaveTimeouts[kind]);
    delete cloudSaveTimeouts[kind];
  }
  // Broadcast change across tabs
  import("./crossTab").then(({ broadcastCrossTab }) => {
    broadcastCrossTab("learning-session-changed", { kind, state: "REMOVED" });
  }).catch(() => {});

  // Fire and forget cloud delete
  const owner = getLocalOwnerId();
  import("./api").then(({ api }) => {
    if (getLocalOwnerId() !== owner) return;
    api.sessions.delete(kind).catch(() => {});
  });
}

export function clearLearningSessions(): void {
  removeLearningSession("quiz");
  removeLearningSession("simulado");
  try {
    localStorage.removeItem("medquest_last_user_id");
  } catch {
    // Storage error
  }
}

export function deadlineFromNow(seconds: number): number {
  return Date.now() + seconds * 1000;
}

// Helper to debounce cloud writes
const cloudSaveTimeouts: Record<string, ReturnType<typeof setTimeout>> = {};

export function writeLearningSession(kind: LearningSessionKind, value: Record<string, unknown>): boolean {
  try {
    const owner = getLocalOwnerId();
    const data = { ...value, savedAt: Date.now() };
    localStorage.setItem(getLearningSessionKey(kind), JSON.stringify(data));
    
    // Broadcast change across tabs
    import("./crossTab").then(({ broadcastCrossTab }) => {
      broadcastCrossTab("learning-session-changed", { kind, state: value.state });
    }).catch(() => {});

    // Debounce cloud save
    if (cloudSaveTimeouts[kind]) clearTimeout(cloudSaveTimeouts[kind]);
    cloudSaveTimeouts[kind] = setTimeout(() => {
      import("./api").then(({ api }) => {
        if (getLocalOwnerId() !== owner) return;
        api.sessions.save(kind, data).catch((e: unknown) => console.error("Cloud save failed", e));
      });
    }, 2000);
    return true;
  } catch (error) {
    console.error(`Unable to persist ${kind} session`, error);
    return false;
  }
}

/**
 * Async sync session from cloud. Should be called on mount by clients.
 */
export async function syncSessionFromCloud<T>(
  kind: LearningSessionKind, 
  isValid: (value: unknown) => value is T
): Promise<T | null> {
  try {
    const owner = getLocalOwnerId();
    const { api } = await import("./api");
    if (getLocalOwnerId() !== owner) return null;
    const res = await api.sessions.get(kind);
    if (getLocalOwnerId() !== owner || !res || !res.data) return null;
    
    if (isValid(res.data)) {
      const local = readLearningSession(kind, isValid) as Record<string, unknown> | null;
      const remoteSavedAt = typeof res.data === "object" && res.data && "savedAt" in res.data ? (res.data as Record<string, unknown>).savedAt as number : 0;
      const localSavedAt = (local?.savedAt as number) || 0;
      
      // Se a nuvem é mais recente, atualiza o local
      if (remoteSavedAt > localSavedAt) {
        localStorage.setItem(getLearningSessionKey(kind), JSON.stringify(res.data));
        return res.data;
      }
      return local as T | null;
    }
  } catch (e) {
    console.error("Failed to sync session from cloud", e);
  }
  return null;
}
