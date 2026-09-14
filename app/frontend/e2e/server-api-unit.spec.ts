import { test, expect } from '@playwright/test';
import { isDynamicServerUsageError } from '../src/lib/server-api';

test.describe('isDynamicServerUsageError', () => {
  test('returns false for non-Error objects', () => {
    expect(isDynamicServerUsageError(null)).toBe(false);
    expect(isDynamicServerUsageError(undefined)).toBe(false);
    expect(isDynamicServerUsageError("error string")).toBe(false);
    expect(isDynamicServerUsageError(123)).toBe(false);
    expect(isDynamicServerUsageError({ message: "DYNAMIC_SERVER_USAGE" })).toBe(false);
  });

  test('returns false for regular Error objects', () => {
    const error = new Error("Just a regular error");
    expect(isDynamicServerUsageError(error)).toBe(false);
  });

  test('returns true when message contains DYNAMIC_SERVER_USAGE', () => {
    const error = new Error("Some error with DYNAMIC_SERVER_USAGE inside");
    expect(isDynamicServerUsageError(error)).toBe(true);
  });

  test('returns true when digest contains DYNAMIC_SERVER_USAGE', () => {
    const error = new Error("Regular message") as Error & { digest?: string };
    error.digest = "Something_DYNAMIC_SERVER_USAGE_123";
    expect(isDynamicServerUsageError(error)).toBe(true);
  });

  test('handles digest property of different types safely', () => {
    const error = new Error("Regular message") as Error & { digest?: unknown };
    error.digest = 12345;
    expect(isDynamicServerUsageError(error)).toBe(false);

    error.digest = { DYNAMIC_SERVER_USAGE: true };
    expect(isDynamicServerUsageError(error)).toBe(false);
  });
});
