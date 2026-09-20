import type { LearningProfileTopic, ThemeProgress } from "@/types/api";

type JourneyProgress = Pick<ThemeProgress, "study_path" | "theory_completed" | "flashcards_due">;

export function themeJourney(subtema: string, topic?: LearningProfileTopic, progress?: JourneyProgress) {
  const available = topic?.available ?? 0;
  const answered = topic?.answered ?? 0;
  const diagnosticTarget = Math.min(5, available);
  const diagnosticComplete = diagnosticTarget > 0 && answered >= diagnosticTarget;
  const practiceUrl = (options: Record<string, string>) =>
    `/estudar?${new URLSearchParams({ subtema, unanswered_only: "false", ...options })}`;
  const diagnostic = practiceUrl({ status: "unanswered", limit: String(Math.max(1, diagnosticTarget - answered)) });
  const practice = practiceUrl({ mode: "adaptive", limit: progress?.study_path === "essential" ? "10" : "20" });
  const review = practiceUrl({ status: "srs_due", limit: "20" });
  const flashcards = `/revisao-ativa?${new URLSearchParams({ subtema })}`;
  const due = topic?.due_count ?? 0;
  const next = due > 0
    ? { href: review, label: "Revisar questões pendentes", reason: `${due} questões deste tema estão com revisão vencida.` }
    : (progress?.flashcards_due ?? 0) > 0
      ? { href: flashcards, label: "Revisar flashcards do tema", reason: `${progress!.flashcards_due} flashcards deste tema aguardam revisão.` }
      : available > 0 && !diagnosticComplete
        ? { href: diagnostic, label: "Continuar diagnóstico", reason: `Responda até ${Math.max(1, diagnosticTarget - answered)} questões inéditas para orientar seu estudo.` }
        : progress && !progress.theory_completed
          ? { href: "#roteiro", label: "Continuar estudo teórico", reason: progress.study_path === "essential" ? "Revise no seu material os conceitos que geraram dúvida ou erro." : "Estude o assunto integralmente no seu material e registre a conclusão." }
          : available > 0
            ? { href: practice, label: "Continuar prática adaptativa", reason: "A sessão considera seus erros, cobertura e risco de esquecimento." }
            : { href: "/planner", label: "Abrir planner", reason: "Este tema ainda não tem questões disponíveis. Organize seu próximo estudo no planner." };
  return { available, answered, diagnosticTarget, diagnosticComplete, diagnostic, practice, review, flashcards, due, next };
}
