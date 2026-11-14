import type { LearningProfileTopic, ThemeProgress } from "@/types/api";

export interface ThemeHubUrls {
  review: string;
  practice: (limit?: number) => string;
}

export function getThemeUrls(subtema: string): ThemeHubUrls {
  const practiceUrl = (params: Record<string, string>) =>
    `/estudar?${new URLSearchParams({ subtema, unanswered_only: "false", ...params })}`;
  return {
    review: practiceUrl({ status: "srs_due", limit: "50" }),
    practice: (limit = 20) => practiceUrl({ mode: "adaptive", limit: String(limit) }),
  };
}

export function themeJourney(
  subtema: string,
  topic?: LearningProfileTopic,
  progress?: Partial<Pick<ThemeProgress, "study_path">>
) {
  const available = topic?.available ?? 0;
  const answered = topic?.answered ?? 0;
  const due = topic?.due_count ?? 0;

  const urls = getThemeUrls(subtema);
  const defaultLimit = progress?.study_path === "essential" ? 10 : 20;
  const practice = urls.practice(defaultLimit);
  const review = urls.review;

  const next = due > 0
    ? {
        href: review,
        label: `Revisar questões pendentes (${due})`,
        reason: `${due} ${due === 1 ? "questão deste tema está" : "questões deste tema estão"} com revisão vencida.`,
      }
    : available > 0
      ? {
          href: practice,
          label: "Praticar este tema",
          reason: "Sessão adaptativa priorizando questões inéditas e lacunas.",
        }
      : {
          href: "/planner",
          label: "Abrir planner",
          reason: "Este tema ainda não tem questões disponíveis no banco.",
        };

  return {
    available,
    answered,
    due,
    urls,
    next,
    review,
    practice,
  };
}
