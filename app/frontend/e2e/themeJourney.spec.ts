import { expect, test } from '@playwright/test';
import { themeJourney } from '../src/lib/themeJourney';
import type { LearningProfileTopic } from '../src/types/api';

const topic: LearningProfileTopic = {
  topic: 'Ética & documentação', area: 'Preventiva', available: 30,
  answered: 5, attempts: 8, correct: 4, accuracy: 0.5, coverage: 5 / 30,
  diag_accuracy: null, prac_accuracy: null,
  confidence: 0.8, retrievability: 0.8, due_count: 0, priority_score: 0.5, reasons: [],
};
test('revisões vencidas têm precedência sobre diagnóstico e prática', () => {
  const journey = themeJourney(topic.topic, { ...topic, answered: 1, due_count: 2 });
  expect(journey.next.href).toBe(journey.review);
  const params = new URL(journey.next.href, 'http://localhost').searchParams;
  expect(params.get('subtema')).toBe(topic.topic);
  expect(params.get('status')).toBe('srs_due');
});
test('repetir uma questão não completa diagnóstico', () => {
  const journey = themeJourney(topic.topic, { ...topic, answered: 1, attempts: 20 });
  expect(journey.diagnosticComplete).toBe(false);
  expect(journey.next.href).toBe(journey.diagnostic);
});
test('banco pequeno segue para prática sem exigir cinco questões', () => {
  const journey = themeJourney(topic.topic, { ...topic, available: 2, answered: 2 });
  expect(journey.diagnosticComplete).toBe(true);
  expect(journey.next.href).toBe(journey.practice);
});
test('ausência de questões não indica diagnóstico concluído', () => {
  const journey = themeJourney(topic.topic);
  expect(journey.available).toBe(0);
  expect(journey.diagnosticComplete).toBe(false);
});

test('retoma apenas as questões restantes do diagnóstico', () => {
  const journey = themeJourney(topic.topic, { ...topic, answered: 3 });
  expect(new URL(journey.diagnostic, 'http://localhost').searchParams.get('limit')).toBe('2');
});
test('flashcards vencidos precedem teoria e prática', () => {
  const journey = themeJourney(topic.topic, topic, { study_path: 'essential', theory_completed: false, flashcards_due: 2 });
  expect(journey.next.href).toBe(journey.flashcards);
  expect(new URL(journey.flashcards, 'http://localhost').searchParams.get('subtema')).toBe(topic.topic);
});
test('teoria pendente é recomendada depois do diagnóstico', () => {
  const journey = themeJourney(topic.topic, topic, { study_path: 'complete', theory_completed: false, flashcards_due: 0 });
  expect(journey.next.href).toBe('#roteiro');
});
test('percurso controla tamanho da prática sem alterar revisões', () => {
  const essential = themeJourney(topic.topic, topic, { study_path: 'essential', theory_completed: true, flashcards_due: 0 });
  const complete = themeJourney(topic.topic, topic, { study_path: 'complete', theory_completed: true, flashcards_due: 0 });
  expect(new URL(essential.practice, 'http://localhost').searchParams.get('limit')).toBe('10');
  expect(new URL(complete.practice, 'http://localhost').searchParams.get('limit')).toBe('20');
  expect(essential.next.href).toBe(essential.practice);
  expect(essential.review).toBe(complete.review);
});
test('tema sem questões pode oferecer estudo teórico e flashcards', () => {
  const progress = { study_path: 'essential' as const, theory_completed: false, flashcards_due: 0 };
  expect(themeJourney(topic.topic, undefined, progress).next.href).toBe('#roteiro');
  expect(themeJourney(topic.topic, undefined, { ...progress, flashcards_due: 1 }).next.href).toContain('/revisao-ativa?');
});
