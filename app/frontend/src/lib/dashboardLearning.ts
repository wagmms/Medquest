import type { LearningAnalysis, LearningTopic } from "@/types/api";

export const topicKey = (topic: LearningTopic) => JSON.stringify([topic.area, topic.topic, topic.legacy_topic]);

// Reserve room for a correction follow-up and an assessment gap instead of
// letting the largest backlog consume every slot. Keep the shared ranking.
export function dashboardPriorities(data: LearningAnalysis): LearningTopic[] {
  const selected: LearningTopic[] = [];
  const add = (topic?: LearningTopic) => {
    if (topic && !selected.some(item => topicKey(item) === topicKey(topic))) selected.push(topic);
  };
  add(data.priorities.find(t => ["unresolved", "reviews_due", "low_accuracy"].includes(t.reason)));
  add(data.topics.find(t => t.pending_checks > 0));
  add(data.priorities.find(t => t.reason === "needs_assessment"));
  for (const topic of data.priorities) if (selected.length < 3) add(topic);
  return selected;
}

export function topicAction(topic: LearningTopic): { href: string; label: string } | null {
  if (topic.unresolved && topic.actions.errors) return { href: topic.actions.errors, label: "Revisar erros" };
  if (topic.due && topic.actions.reviews) return { href: topic.actions.reviews, label: "Revisar questões vencidas" };
  if (topic.actions.new) return { href: topic.actions.new, label: "Praticar questões inéditas" };
  return null;
}

export function topicReason(topic: LearningTopic): string {
  if (topic.unresolved) return `${topic.unresolved} questões com última resposta incorreta · ${topic.recurring} com erro repetido`;
  if (topic.pending_checks) return `${topic.pending_checks} correções aguardam uma verificação após intervalo`;
  if (topic.due) return `${topic.due} questões com revisão vencida`;
  if (topic.reason === "needs_assessment") return "Poucas primeiras respostas no período; tema a avaliar";
  if (topic.reason === "low_accuracy") return "Baixo acerto nas primeiras respostas do período";
  return "Acompanhar com novas evidências";
}
