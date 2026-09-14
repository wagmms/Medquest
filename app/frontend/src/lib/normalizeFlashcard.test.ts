import { describe, it, expect } from 'vitest';
import { normalizeFlashcard } from './normalizeFlashcard';

describe('normalizeFlashcard', () => {
  it('handles missing front and back safely', () => {
    const card = { front: '', back: '' };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toBe('');
    expect(normalized.back).toBe('');
  });

  it('non-legacy cards: strips option letters from cloze in front', () => {
    const card = {
      front: 'Qual o exame? {{c1::A) Hemograma}}',
      back: 'Gabarito'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toBe('Qual o exame? {{c1::Hemograma}}');
    expect(normalized.back).toBe('Gabarito');
  });

  it('non-legacy cards: leaves non-option cloze intact', () => {
    const card = {
      front: 'O tratamento é {{c1::Amoxicilina}}',
      back: 'Gabarito'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toBe('O tratamento é {{c1::Amoxicilina}}');
  });

  it('legacy cards: parses term and formats correctly', () => {
    const card = {
      front: 'A alternativa correta era {{c1::B. Metformina}}',
      back: 'Gabarito Oficial: Metformina',
      stem: 'Um paciente chegou com glicemia de 250. Qual a conduta?'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toContain('[Caso Clínico / Conduta]');
    expect(normalized.front).toContain('Um paciente chegou com glicemia de 250.');
    expect(normalized.front).not.toContain('Qual a conduta?'); // Should be stripped
    expect(normalized.front).toContain('👉 Diagnóstico / Conduta indicada: {{c1::Metformina}}');
    expect(normalized.back).toBe('Gabarito Oficial: Metformina'); // Should not add distractor because it doesn't match 'Você marcou'
  });

  it('legacy cards: parses wrong term from back and adds distractor warning', () => {
    const card = {
      front: 'A alternativa correta era {{c1::A. Insulina}}',
      back: 'Você marcou "C. Glibenclamida" em vez de "A. Insulina"',
      stem: 'Paciente idoso apresenta quadro de hiperglicemia severa acompanhada de desidratação extrema e confusão mental. Qual a conduta mais adequada?'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toContain('👉 Diagnóstico / Conduta indicada: {{c1::Insulina}}');
    expect(normalized.front).not.toContain('Qual a conduta mais adequada?'); // Should strip
    expect(normalized.back).toContain('💡 Gabarito Oficial:\nInsulina');
    expect(normalized.back).toContain("⚠️ Atenção ao distrator:\nA opção 'Glibenclamida' é incorreta para este quadro clínico.");
  });

  it('legacy cards: handles "Neste caso clínico, em vez de"', () => {
    const card = {
      front: 'Neste caso clínico, em vez de fazer X, a alternativa correta era {{c1::D. Cirurgia}}',
      back: 'Alternativa correta: D. Você marcou \'A. Observação\'',
      stem: 'Paciente com trauma. O diagnóstico mais provável e a melhor conduta são, respectivamente'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toContain('👉 Diagnóstico / Conduta indicada: {{c1::Cirurgia}}');
    expect(normalized.back).toContain("A opção 'Observação' é incorreta para este quadro clínico.");
  });

  it('legacy cards: handles missing stem', () => {
    const card = {
      front: 'Para este quadro clínico, a alternativa correta era {{c1::E) Nenhuma das anteriores}}',
      back: 'Você marcou "A) Tudo"'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toBe('[Caso Clínico / Conduta]\n\n👉 Diagnóstico / Conduta indicada: {{c1::Nenhuma das anteriores}}');
    expect(normalized.back).toContain("A opção 'Tudo' é incorreta");
  });

  it('legacy cards: formats properly even if term is missing', () => {
    const card = {
      front: 'A alternativa correta era algo...',
      back: 'Você marcou "X"'
    };
    const normalized = normalizeFlashcard(card);
    expect(normalized.front).toContain('{{c1::}}');
    expect(normalized.back).toContain("A opção 'X' é incorreta");
  });
});
