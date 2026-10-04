import { auth } from "@clerk/nextjs/server";
import { getGuestSession } from "./session";
import { 
  ThemeProgress, OverviewStats, CoverageResponse, QuestionMeta, PlannerConfig,
  TimelineStat, WeakTopic, Recommendation, BreakdownStat, DistractorStat,
  PlannerPlanResponse, PlannerProgressMap, PlannerTopicProgressMap, PredictiveScore, AtRiskTopic, LearningProfile, ExamReadiness,
  BenchmarkStat, BottleneckTopic, DomainSummaryResponse, ErrorNotebookSummary, InstitutionRadarResponse,
  DashboardSummaryResponse
} from "@/types/api";

export type { QuestionMeta };


const BACKEND_URL = process.env.FLASK_API_URL || process.env.NEXT_PUBLIC_FLASK_API_URL ||
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:5050" : "");
const API_REQUEST_TIMEOUT_MS = process.env.PLAYWRIGHT_TEST ? 1_000 : 15_000;

export function isDynamicServerUsageError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const digest = "digest" in error && typeof error.digest === "string" ? error.digest : "";
  return error.message.includes("DYNAMIC_SERVER_USAGE") || digest.includes("DYNAMIC_SERVER_USAGE");
}

async function serverFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  if (process.env.PLAYWRIGHT_TEST === "true") {
    throw new Error("E2E test environment: SSR fetch bypassed in favor of client mocking.");
  }
  const proxySecret = process.env.FLASK_API_PROXY_SECRET;
  if (!BACKEND_URL) {
    throw new Error("FLASK_API_URL is not configured on server.");
  }
  if (!proxySecret) {
    throw new Error("FLASK_API_PROXY_SECRET is not configured on server.");
  }
  const { getToken } = await auth();
  const token = await getToken();
  const guestId = await getGuestSession();
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> || {}),
  };
  
  if (token) headers["Authorization"] = `Bearer ${token}`;
  else if (guestId) headers["X-Guest-ID"] = guestId;
  
  headers["X-Internal-Proxy-Token"] = proxySecret;

  let response;
  try {
    response = await fetch(`${BACKEND_URL}${endpoint}`, {
      ...options,
      headers,
      // A stalled upstream must not leave the App Router streaming its loading
      // UI forever. Callers can still provide a stricter signal when needed.
      signal: options?.signal ?? AbortSignal.timeout(API_REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    if (isDynamicServerUsageError(error)) {
      throw error; // Re-throw to allow Next.js to handle it
    }
    const message = error instanceof Error ? error.message : "Unknown error";
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new Error(`Backend timeout after ${API_REQUEST_TIMEOUT_MS / 1000}s for ${endpoint}`);
    }
    throw new Error(`Fetch failed for ${BACKEND_URL}${endpoint}: ${message}`);
  }

  if (!response.ok) {
    throw new Error(`Server API error on ${BACKEND_URL}${endpoint}: ${response.status} ${response.statusText}`);
  }

  let data;
  try {
    const text = await response.text();
    try {
      data = JSON.parse(text);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown parse error";
      console.error(`JSON Parse Error for ${BACKEND_URL}${endpoint}. Raw text: ${text.substring(0, 500)}`);
      throw new Error(`JSON parse error on ${BACKEND_URL}${endpoint}: ${message}`);
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown read error";
    throw new Error(`Failed to read response from ${BACKEND_URL}${endpoint}: ${message}`);
  }

  return data;
}

export const serverApi = {
  themes: {
    getProgress: (subtema: string) => serverFetch<ThemeProgress>(`/api/themes/progress?${new URLSearchParams({ subtema })}`, { cache: "no-store" }),
  },
  stats: {
    getOverview: () => serverFetch<OverviewStats>("/api/stats/overview", { cache: "no-store" }),
    getDashboardSummary: () => serverFetch<DashboardSummaryResponse>("/api/dashboard/summary", { cache: "no-store" }),
    getCoverage: () => serverFetch<CoverageResponse>("/api/coverage", { cache: "no-store" }),
    getTimeline: (days: number = 14) => serverFetch<TimelineStat[]>(`/api/stats/timeline?days=${days}`, { next: { tags: ['stats'] } }),
    getWeakTopics: () => serverFetch<WeakTopic[]>("/api/stats/weak-topics", { next: { tags: ['stats'] } }),
    getRecommendations: () => serverFetch<Recommendation[]>("/api/stats/recommendations", { next: { tags: ['stats'] } }),
    getDistractors: () => serverFetch<DistractorStat[]>("/api/stats/distractors", { next: { tags: ['stats'] } }),
    getPredictiveScore: () => serverFetch<PredictiveScore>("/api/stats/predictive-score", { next: { tags: ['stats'] } }),
    getAtRiskTopics: () => serverFetch<AtRiskTopic[]>("/api/stats/at-risk", { next: { tags: ['stats'] } }),
    getLearningProfile: (subtema?: string) => serverFetch<LearningProfile>(`/api/stats/learning-profile${subtema ? `?subtema=${encodeURIComponent(subtema)}` : ""}`, { cache: "no-store" }),
    getExamReadiness: (institution?: string) => serverFetch<ExamReadiness>(`/api/stats/exam-readiness${institution ? `?institution=${encodeURIComponent(institution)}` : ""}`, { next: { tags: ['stats'] } }),
    getBreakdown: (by: 'institution' | 'area' | 'year') => 
      serverFetch<BreakdownStat[]>(`/api/stats/breakdown?by=${by}`, { next: { tags: ['stats'] } }),
    getBenchmark: () => serverFetch<BenchmarkStat>("/api/stats/benchmark", { next: { tags: ['stats'] } }),
    getBottlenecks: (limit: number = 3) => serverFetch<BottleneckTopic[]>(`/api/stats/bottlenecks?limit=${limit}`, { next: { tags: ['stats'] } }),
    getDomainSummary: () => serverFetch<DomainSummaryResponse>("/api/stats/domain-summary", { next: { tags: ['stats'] } }),
    getErrorNotebookSummary: () => serverFetch<ErrorNotebookSummary>("/api/stats/error-notebook-summary", { next: { tags: ['stats'] } }),
    getInstitutionRadar: (institution?: string, compareInstitution?: string) => {
      const params = new URLSearchParams();
      if (institution) params.append("institution", institution);
      if (compareInstitution) params.append("compare_institution", compareInstitution);
      const qs = params.toString();
      return serverFetch<InstitutionRadarResponse>(`/api/stats/institution-radar${qs ? `?${qs}` : ""}`, { next: { tags: ['stats'] } });
    },
  },

  questions: {
    getMeta: () => serverFetch<QuestionMeta>("/api/meta", { cache: 'no-store' }),
  },
  planner: {
    getConfig: () => serverFetch<PlannerConfig>("/api/planner/config", { cache: 'no-store' }),
    generatePlan: (params: Record<string, unknown>) => serverFetch<PlannerPlanResponse>("/api/generate_plan", {
      method: 'POST',
      body: JSON.stringify(params),
      cache: 'no-store'
    }),
    getProgress: () => serverFetch<PlannerProgressMap>("/api/planner", { cache: 'no-store' }),
    getTopicProgress: () => serverFetch<PlannerTopicProgressMap>("/api/planner/topics", { cache: 'no-store' }),
  },
  osce: {
    getStations: (params?: { area?: string; institution?: string; difficulty?: string }) => {
      const search = new URLSearchParams();
      if (params?.area) search.set("area", params.area);
      if (params?.institution) search.set("institution", params.institution);
      if (params?.difficulty) search.set("difficulty", params.difficulty);
      const qs = search.toString();
      return serverFetch<{ stations: import("@/types/api").OsceStation[]; count: number }>(`/api/osce/stations${qs ? `?${qs}` : ""}`, { cache: "no-store" });
    },
    getStation: (stationId: number) => serverFetch<import("@/types/api").OsceStationDetail>(`/api/osce/stations/${stationId}`, { cache: "no-store" }),
    startSession: (stationId: number, circuitSessionId?: string, mode?: "blind" | "guided") => serverFetch<{
      session_id: string;
      station_id: number;
      title: string;
      duration_seconds: number;
      start_time: string;
      transcript: import("@/types/api").OsceTranscriptItem[];
      mode?: "blind" | "guided";
      guided_feedback?: import("@/types/api").OsceLiveFeedback;
    }>("/api/osce/sessions/start", {
      method: "POST",
      body: JSON.stringify({ station_id: stationId, circuit_session_id: circuitSessionId, mode: mode || "blind" }),
      cache: "no-store",
    }),
    interact: (sessionId: string, message: string, elapsedSeconds: number) => serverFetch<{
      reply: string;
      sender: "paciente" | "examinador";
      elapsed_seconds: number;
      transcript_count: number;
      guided_feedback?: import("@/types/api").OsceLiveFeedback;
    }>(`/api/osce/sessions/${sessionId}/interact`, {
      method: "POST",
      body: JSON.stringify({ message, elapsed_seconds: elapsedSeconds }),
      cache: "no-store",
    }),
    executeAction: (sessionId: string, actionType: string, actionTarget: string, elapsedSeconds: number) => serverFetch<{
      action_type: string;
      target: string;
      examiner_message: string;
      payload: Record<string, unknown>;
      elapsed_seconds: number;
      guided_feedback?: import("@/types/api").OsceLiveFeedback;
    }>(`/api/osce/sessions/${sessionId}/action`, {
      method: "POST",
      body: JSON.stringify({ action_type: actionType, action_target: actionTarget, elapsed_seconds: elapsedSeconds }),
      cache: "no-store",
    }),
    finishSession: (sessionId: string, conductNotes?: string) => serverFetch<import("@/types/api").OsceFinishResponse>(`/api/osce/sessions/${sessionId}/finish`, {
      method: "POST",
      body: JSON.stringify({ conduct_notes: conductNotes }),
      cache: "no-store",
    }),
    dispatchSpeech: (sessionId: string, message: string, elapsedSeconds: number) => serverFetch<import("@/types/api").OsceDispatchSpeechResponse>(`/api/osce/sessions/${sessionId}/dispatch_speech`, {
      method: "POST",
      body: JSON.stringify({ message, elapsed_seconds: elapsedSeconds }),
      cache: "no-store",
    }),
    getReport: (sessionId: string) => serverFetch<import("@/types/api").OsceReportResponse>(`/api/osce/sessions/${sessionId}/report`, { cache: "no-store" }),
    exportCards: (sessionId: string) => serverFetch<{ success: boolean; exported_count: number; message: string }>(`/api/osce/sessions/${sessionId}/export_cards`, {
      method: "POST",
      cache: "no-store",
    }),
    getDrugs: () => serverFetch<{ drugs: import("@/types/api").OsceDrugItem[]; count: number }>("/api/osce/drugs", { cache: "no-store" }),
    getProcedures: () => serverFetch<{ procedures: import("@/types/api").OsceProcedureCatalogItem[]; count: number }>("/api/osce/procedures", { cache: "no-store" }),
    prescribe: (sessionId: string, prescription: import("@/types/api").OscePrescriptionItem[], elapsedSeconds: number) => serverFetch<import("@/types/api").OscePrescribeResponse>(`/api/osce/sessions/${sessionId}/prescribe`, {
      method: "POST",
      body: JSON.stringify({ prescription, elapsed_seconds: elapsedSeconds }),
      cache: "no-store",
    }),
    performProcedure: (sessionId: string, procedureType: string, anatomicalSite: string, elapsedSeconds: number) => serverFetch<import("@/types/api").OsceProcedureResponse>(`/api/osce/sessions/${sessionId}/procedure`, {
      method: "POST",
      body: JSON.stringify({ procedure_type: procedureType, anatomical_site: anatomicalSite, elapsed_seconds: elapsedSeconds }),
      cache: "no-store",
    }),
    getLiveFeedback: (sessionId: string, elapsedSeconds: number) => serverFetch<import("@/types/api").OsceLiveFeedback>(`/api/osce/sessions/${sessionId}/live_feedback?elapsed_seconds=${elapsedSeconds}`, { cache: "no-store" }),
    generateStation: (payload?: import("@/types/api").OsceGenerateStationPayload) => serverFetch<import("@/types/api").OsceGenerateStationResponse>("/api/osce/stations/generate", {
      method: "POST",
      body: JSON.stringify(payload || {}),
      cache: "no-store",
    }),
    getCircuitPlan: (institution?: string) => {
      const qs = institution ? `?institution=${encodeURIComponent(institution)}` : "";
      return serverFetch<import("@/types/api").OsceCircuitPlanResponse>(`/api/osce/circuits/plan${qs}`, { cache: "no-store" });
    },
    getCircuitSummary: (circuitId: string) =>
      serverFetch<import("@/types/api").OsceCircuitSummaryResponse>(`/api/osce/circuits/${circuitId}/summary`, { cache: "no-store" }),
  }
};
