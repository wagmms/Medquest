import { test, expect } from '@playwright/test';
import { deadlineFromNow } from '../src/lib/sessionState';

test.describe('deadlineFromNow', () => {
  test('should correctly calculate the deadline in seconds from now', () => {
    const before = Date.now();
    const seconds = 60;
    const result = deadlineFromNow(seconds);
    const after = Date.now();

    expect(result).toBeGreaterThanOrEqual(before + seconds * 1000);
    expect(result).toBeLessThanOrEqual(after + seconds * 1000);
  });

  test('should return approximate Date.now() when seconds is 0', () => {
    const before = Date.now();
    const result = deadlineFromNow(0);
    const after = Date.now();

    expect(result).toBeGreaterThanOrEqual(before);
    expect(result).toBeLessThanOrEqual(after);
  });

  test('should handle negative seconds', () => {
    const before = Date.now();
    const seconds = -60;
    const result = deadlineFromNow(seconds);
    const after = Date.now();

    expect(result).toBeGreaterThanOrEqual(before + seconds * 1000);
    expect(result).toBeLessThanOrEqual(after + seconds * 1000);
  });
});
