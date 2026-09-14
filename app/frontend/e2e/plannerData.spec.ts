import { test, expect } from '@playwright/test';
import { getSubtemaDetails } from '../src/lib/plannerData';

test.describe('plannerData unit tests', () => {
  test('getSubtemaDetails returns null for unknown subtema', () => {
    const result = getSubtemaDetails('Unknown Subtema xyz123');
    expect(result).toBeNull();
  });

  test('getSubtemaDetails returns null for empty string', () => {
    const result = getSubtemaDetails('');
    expect(result).toBeNull();
  });

  test('getSubtemaDetails returns correct details for known subtema with high yield', () => {
    const result = getSubtemaDetails('Abdome Agudo Inflamatório (Apendicite e Diverticulite Aguda)');
    expect(result).not.toBeNull();
    expect(result?.macroThemeName).toBe('Abdome Agudo Inflamatório (Apendicite e Diverticulite Aguda)');
    expect(result?.highYield).toBe(true);
    expect(Array.isArray(result?.details)).toBe(true);
  });

  test('getSubtemaDetails returns correct details for known subtema with low yield', () => {
    const result = getSubtemaDetails('Abdome Agudo Vascular e Isquemia Mesentérica');
    expect(result).not.toBeNull();
    expect(result?.macroThemeName).toBe('Abdome Agudo Vascular e Isquemia Mesentérica');
    expect(result?.highYield).toBe(false);
    expect(Array.isArray(result?.details)).toBe(true);
  });
});
