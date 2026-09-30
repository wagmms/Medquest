import { expect, test } from '@playwright/test';
import { themeJourney, getThemeUrls } from '../src/lib/themeJourney';
import type { LearningProfileTopic } from '../src/types/api';

const topic: LearningProfileTopic = {
  topic: 'Ética & documentação',
  area: 'Preventiva',
  available: 30,
  answered: 5,
  attempts: 8,
  correct: 4,
  accuracy: 0.5,
  coverage: 5 / 30,
  diag_accuracy: null,
  prac_accuracy: null,
  confidence: 0.8,
  retrievability: 0.8,
  due_count: 0,
  priority_score: 0.5,
  reasons: [],
};

test('revisões vencidas têm precedência sobre prática quando há pendências', () => {
  const journey = themeJourney(topic.topic, { ...topic, due_count: 3 });
  expect(journey.next.href).toBe(journey.review);
  const params = new URL(journey.next.href, 'http://localhost').searchParams;
  expect(params.get('subtema')).toBe(topic.topic);
  expect(params.get('status')).toBe('srs_due');
});

test('flashcards vencidos têm precedência quando não há questões vencidas', () => {
  const journey = themeJourney(topic.topic, topic, { flashcards_due: 4, flashcards_total: 10 });
  expect(journey.next.href).toBe(journey.flashcards);
  const params = new URL(journey.next.href, 'http://localhost').searchParams;
  expect(params.get('subtema')).toBe(topic.topic);
});

test('prática adaptativa é a ação recomendada quando tudo está em dia', () => {
  const journey = themeJourney(topic.topic, topic, { flashcards_due: 0, flashcards_total: 5 });
  expect(journey.next.href).toBe(journey.practice);
  const params = new URL(journey.next.href, 'http://localhost').searchParams;
  expect(params.get('mode')).toBe('adaptive');
  expect(params.get('limit')).toBe('20');
});

test('getThemeUrls gera parâmetros corretos com limites configuráveis', () => {
  const urls = getThemeUrls(topic.topic);
  const reviewParams = new URL(urls.review, 'http://localhost').searchParams;
  expect(reviewParams.get('subtema')).toBe(topic.topic);
  expect(reviewParams.get('status')).toBe('srs_due');

  const practice10 = new URL(urls.practice(10), 'http://localhost').searchParams;
  expect(practice10.get('limit')).toBe('10');
  expect(practice10.get('mode')).toBe('adaptive');

  const practice30 = new URL(urls.practice(30), 'http://localhost').searchParams;
  expect(practice30.get('limit')).toBe('30');

  const flashcardsParams = new URL(urls.flashcards, 'http://localhost').searchParams;
  expect(flashcardsParams.get('subtema')).toBe(topic.topic);
});

test('tema sem questões e sem flashcards recomenda o planner', () => {
  const emptyTopic = { ...topic, available: 0, answered: 0, due_count: 0 };
  const journey = themeJourney(emptyTopic.topic, emptyTopic, { flashcards_due: 0, flashcards_total: 0 });
  expect(journey.next.href).toBe('/planner');
});
