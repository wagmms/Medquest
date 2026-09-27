import { localDb } from "./db";
import type { Flashcard, FlashcardGenerateResponse } from "@/types/api";

/** Cache only confirmed server IDs; local storage failures cannot undo a server save. */
export async function cacheCreatedFlashcards(response: unknown, owner: string): Promise<void> {
  if (!localDb || !response || typeof response !== "object") return;
  const candidates = "flashcards" in response ? response.flashcards : [response];
  if (!Array.isArray(candidates)) return;
  try {
    const cards: Array<Flashcard & { _owner_id: string }> = [];
    for (const value of candidates) {
      if (!value || typeof value.id !== "number" || typeof value.question_id !== "number" || typeof value.front !== "string") continue;
      const card = value as FlashcardGenerateResponse;
      const question = await localDb.questions.get([card.question_id, owner]);
      cards.push({ id: card.id, question_id: card.question_id, front: card.front, back: card.back,
        source_context: card.context, is_ai_generated: true, next_review_date: new Date().toISOString(),
        stem: question?.stem, subtema: question?.subtema, deck_name: "Geral", _owner_id: owner });
    }
    await localDb.flashcards.bulkPut(cards);
  } catch (error) {
    console.warn("Flashcards salvos no servidor; cache local indisponível", error);
  }
}
