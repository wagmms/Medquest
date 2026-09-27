import type { PlannerConfig, PlannerTopicProgressMap, PlannerWeek } from "@/types/api";

type TokenResponse = { access_token?: string; error?: string };
declare global {
  interface Window {
    google?: { accounts: { oauth2: { initTokenClient: (config: {
      client_id: string;
      scope: string;
      callback: (response: TokenResponse) => void;
      error_callback?: (error: { type: string }) => void;
    }) => { requestAccessToken: () => void } } } };
  }
}
export interface SyncProgress { current: number; total: number; status: string }
interface CalendarEvent {
  id: string;
  summary?: string;
  colorId?: string;
  extendedProperties?: { private?: Record<string, string> };
}
interface SyncOptions {
  config: PlannerConfig;
  ownerId: string;
  completed: PlannerTopicProgressMap;
  onComplete: (week: number, subtema: string) => Promise<void>;
  onProgress?: (progress: SyncProgress) => void;
}
export interface StudyBlock {
  key: string;
  topicKey: string;
  title: string;
  description: string;
  start: Date;
  end: Date;
}
const topicKey = (week: number, subtema: string, area: string) => JSON.stringify([week, subtema, area]);
const topicTitle = (subtema: string, area: string) => `[MedQuest] 📖 ${subtema} (${area})`;

/** Schedule in the browser's local timezone, Monday through the configured day count. */
export function scheduleStudyBlocks(plan: PlannerWeek[], config: PlannerConfig,
  completed: PlannerTopicProgressMap = {}, now = new Date()): StudyBlock[] {
  const days = Math.max(1, Math.min(7, Math.floor(config.days_per_week || 6)));
  const capacity = Math.max(30, Math.min(16 * 60, Math.round((config.hours_per_day || 4) * 4) * 15));
  const cursor = new Date(now);
  cursor.setHours(8, 0, 0, 0);
  if (cursor < now) cursor.setDate(cursor.getDate() + 1);
  let used = 0;
  const blocks: StudyBlock[] = [];
  const advance = () => { cursor.setDate(cursor.getDate() + 1); used = 0; };
  const ensureDay = () => {
    while ((cursor.getDay() + 6) % 7 >= days) advance();
    if (config.exam_date && cursor >= new Date(`${config.exam_date}T00:00:00`)) {
      throw new Error("O cronograma não cabe antes da prova. Ajuste a carga diária ou os temas pendentes.");
    }
  };
  for (const week of plan) {
    const earliest = new Date(`${week.date.slice(0, 10)}T08:00:00`);
    if (Number.isNaN(earliest.getTime())) throw new Error("Data inválida no cronograma.");
    if (cursor < earliest) { cursor.setTime(earliest.getTime()); used = 0; }
    for (const topic of week.topics) {
      const key = topicKey(week.week, topic.subtema, topic.area);
      if (completed[`${week.week}:${topic.subtema}`] || completed[topic.subtema]) continue;
      let remaining = Math.max(30, Math.round(topic.estimated_hours * 4) * 15);
      if (!Number.isFinite(remaining)) throw new Error("Carga horária inválida no cronograma.");
      let part = 0;
      while (remaining > 0) {
        if (used >= capacity) advance();
        ensureDay();
        const duration = Math.min(remaining, capacity - used);
        const start = new Date(cursor.getTime() + used * 60000);
        blocks.push({ key: `${key}:${part++}`, topicKey: key,
          title: topicTitle(topic.subtema, topic.area),
          description: `Semana ${week.week} • ${topic.area} • ${topic.estimated_hours}h no total`,
          start, end: new Date(start.getTime() + duration * 60000) });
        used += duration;
        remaining -= duration;
      }
    }
  }
  return blocks;
}

let identityScript: Promise<void> | undefined;
async function getAccessToken(): Promise<string> {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) throw new Error("GOOGLE_CLIENT_ID_MISSING");
  if (!window.google?.accounts?.oauth2) {
    identityScript ??= new Promise<void>((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
      const script = existing || document.createElement("script");
      const finish = (error?: Error) => {
        clearTimeout(timer);
        script.removeEventListener("load", loaded);
        script.removeEventListener("error", failed);
        if (error) { script.remove(); reject(error); } else resolve();
      };
      const loaded = () => finish();
      const failed = () => finish(new Error("Falha ao carregar Google Identity Services"));
      const timer = setTimeout(failed, 20000);
      script.addEventListener("load", loaded, { once: true });
      script.addEventListener("error", failed, { once: true });
      if (!existing) {
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true;
        document.body.appendChild(script);
      }
    }).catch(error => { identityScript = undefined; throw error; });
    await identityScript;
  }
  return new Promise((resolve, reject) => {
    window.google!.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: "https://www.googleapis.com/auth/calendar.events",
      callback: response => response.access_token && !response.error
        ? resolve(response.access_token) : reject(new Error(response.error || "Autorização não recebida")),
      error_callback: error => reject(new Error(`Autorização interrompida: ${error.type}`)),
    }).requestAccessToken();
  });
}

async function digest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join("");
}

/** Checked, paginated, repeatable upserts. Existing events are never mass-deleted. */
export async function syncPlanToGoogleCalendar(plan: PlannerWeek[], options: SyncOptions) {
  const token = await getAccessToken();
  const base = "https://www.googleapis.com/calendar/v3/calendars/primary/events";
  const request = async <T>(url: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(url, { ...init, signal: AbortSignal.timeout(20000),
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...init?.headers } });
    if (!response.ok) throw new Error(`Google Agenda: HTTP ${response.status}. A sincronização não foi concluída; tente novamente.`);
    if (response.status === 204) return undefined as T;
    return await response.json() as T;
  };
  const events: CalendarEvent[] = [];
  let pageToken: string | undefined;
  do {
    const params = new URLSearchParams({ maxResults: "2500", showDeleted: "false" });
    if (pageToken) params.set("pageToken", pageToken);
    const page = await request<{ items?: CalendarEvent[]; nextPageToken?: string }>(`${base}?${params}`);
    events.push(...page.items || []);
    pageToken = page.nextPageToken;
  } while (pageToken);

  const namespace = await digest(JSON.stringify([options.ownerId, options.config.start_date, options.config.exam_date]));
  const completed = { ...options.completed };
  const byKey = new Map<string, CalendarEvent>();
  const legacyByTitle = new Map<string, CalendarEvent>();
  for (const event of events) {
    const props = event.extendedProperties?.private;
    if (props?.medquestPlan === namespace && props.medquestBlock) byKey.set(props.medquestBlock, event);
    else if (!props?.medquestPlan && event.summary?.startsWith("[MedQuest] 📖 ")) legacyByTitle.set(event.summary, event);
  }
  for (const week of plan) {
    for (const topic of week.topics) {
      const key = topicKey(week.week, topic.subtema, topic.area);
      const managed = events.filter(e => e.extendedProperties?.private?.medquestPlan === namespace && e.extendedProperties.private.medquestTopic === key);
      const legacy = legacyByTitle.get(topicTitle(topic.subtema, topic.area));
      const expectedParts = Number(managed[0]?.extendedProperties?.private?.medquestParts || managed.length);
      const done = managed.length ? managed.length === expectedParts && managed.every(e => e.colorId === "8") : legacy?.colorId === "8";
      if (done && !completed[`${week.week}:${topic.subtema}`] && !completed[topic.subtema]) {
        await options.onComplete(week.week, topic.subtema);
        completed[`${week.week}:${topic.subtema}`] = true;
      }
      if (completed[`${week.week}:${topic.subtema}`] || completed[topic.subtema]) {
        for (const event of managed.length ? managed : legacy ? [legacy] : []) {
          if (event.colorId !== "8") await request(`${base}/${encodeURIComponent(event.id)}`, { method: "PATCH", body: JSON.stringify({ colorId: "8" }) });
        }
      }
    }
  }
  const blocks = scheduleStudyBlocks(plan, options.config, completed);
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  for (const [index, block] of blocks.entries()) {
    options.onProgress?.({ current: index, total: blocks.length, status: `Sincronizando ${block.title}` });
    const existing = byKey.get(block.key) || (block.key.endsWith(":0") ? legacyByTitle.get(block.title) : undefined);
    if (existing?.colorId === "8") continue;
    const id = existing?.id || await digest(`${namespace}:${block.key}`);
    const body = {
      summary: block.title, description: block.description, colorId: "9",
      start: { dateTime: block.start.toISOString(), timeZone }, end: { dateTime: block.end.toISOString(), timeZone },
      extendedProperties: { private: { medquestPlan: namespace, medquestBlock: block.key, medquestTopic: block.topicKey, medquestParts: String(blocks.filter(b => b.topicKey === block.topicKey).length) } },
    };
    await request(existing ? `${base}/${encodeURIComponent(id)}` : base, {
      method: existing ? "PATCH" : "POST", body: JSON.stringify(existing ? body : { ...body, id }),
    });
  }
  options.onProgress?.({ current: blocks.length, total: blocks.length, status: "Sincronização concluída" });
  return { success: true, calendarId: "primary" };
}
