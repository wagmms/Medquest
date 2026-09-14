import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { triggerConfetti } from './confetti';
import confetti from 'canvas-confetti';

vi.mock('canvas-confetti', () => {
  return {
    default: vi.fn(),
  };
});

describe('triggerConfetti', () => {
  let originalWindow: typeof window | undefined;

  beforeEach(() => {
    // Clear mocks and localStorage before each test
    vi.clearAllMocks();
    localStorage.clear();
    originalWindow = global.window;
  });

  afterEach(() => {
    if (originalWindow !== undefined) {
      global.window = originalWindow;
    } else {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-expect-error
      delete global.window;
    }
  });

  it('should return early if window is undefined', () => {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    delete global.window;
    triggerConfetti();

    expect(confetti).not.toHaveBeenCalled();
    expect(localStorage.getItem('mq_last_confetti')).toBeNull();
  });

  it('should not trigger confetti if already triggered today', () => {
    const today = new Date().toISOString().split('T')[0];
    localStorage.setItem('mq_last_confetti', today);

    triggerConfetti();

    expect(confetti).not.toHaveBeenCalled();
  });

  it('should trigger confetti and save date to localStorage if not triggered today', () => {
    localStorage.setItem('mq_last_confetti', '2020-01-01'); // some past date

    triggerConfetti();

    expect(confetti).toHaveBeenCalledWith({
      particleCount: 100,
      spread: 70,
      origin: { y: 0.6 }
    });

    const today = new Date().toISOString().split('T')[0];
    expect(localStorage.getItem('mq_last_confetti')).toBe(today);
  });

  it('should trigger confetti if never triggered before', () => {
    expect(localStorage.getItem('mq_last_confetti')).toBeNull();

    triggerConfetti();

    expect(confetti).toHaveBeenCalled();
    const today = new Date().toISOString().split('T')[0];
    expect(localStorage.getItem('mq_last_confetti')).toBe(today);
  });
});
