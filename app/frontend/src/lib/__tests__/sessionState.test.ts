import { deadlineFromNow } from '../sessionState';

describe('deadlineFromNow', () => {
  let originalNow: () => number;

  beforeAll(() => {
    originalNow = Date.now;
  });

  afterAll(() => {
    Date.now = originalNow;
  });

  it('should correctly calculate the deadline in seconds from now', () => {
    const mockNow = 1000000000000; // 2001-09-09T01:46:40.000Z
    Date.now = jest.fn(() => mockNow);

    const seconds = 60;
    const expectedDeadline = mockNow + seconds * 1000;

    const result = deadlineFromNow(seconds);

    expect(result).toBe(expectedDeadline);
  });

  it('should return exactly Date.now() when seconds is 0', () => {
    const mockNow = 1000000000000;
    Date.now = jest.fn(() => mockNow);

    const seconds = 0;
    const expectedDeadline = mockNow;

    const result = deadlineFromNow(seconds);

    expect(result).toBe(expectedDeadline);
  });

  it('should handle negative seconds', () => {
    const mockNow = 1000000000000;
    Date.now = jest.fn(() => mockNow);

    const seconds = -60;
    const expectedDeadline = mockNow + seconds * 1000;

    const result = deadlineFromNow(seconds);

    expect(result).toBe(expectedDeadline);
  });
});
