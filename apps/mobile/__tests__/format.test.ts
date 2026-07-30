import {
  formatCurrency,
  formatPercentage,
  getInitials,
  truncate,
  timeAgo,
} from '../src/utils/format';

describe('formatCurrency', () => {
  it('formats whole numbers', () => {
    expect(formatCurrency(1000)).toBe('$1,000');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0');
  });

  it('formats large numbers', () => {
    expect(formatCurrency(1234567)).toBe('$1,234,567');
  });
});

describe('formatPercentage', () => {
  it('formats with default decimal places', () => {
    expect(formatPercentage(94.2)).toBe('94.2%');
  });

  it('formats with custom decimal places', () => {
    expect(formatPercentage(100, 0)).toBe('100%');
  });
});

describe('getInitials', () => {
  it('returns two initials from full name', () => {
    expect(getInitials('John Doe')).toBe('JD');
  });

  it('returns single initial for one-word name', () => {
    expect(getInitials('Admin')).toBe('A');
  });

  it('handles empty string', () => {
    expect(getInitials('')).toBe('');
  });
});

describe('truncate', () => {
  it('returns full text when shorter than max', () => {
    expect(truncate('Hello', 10)).toBe('Hello');
  });

  it('truncates with ellipsis when longer than max', () => {
    expect(truncate('Hello World!', 8)).toBe('Hello W…');
  });
});

describe('timeAgo', () => {
  it('returns "Just now" for recent dates', () => {
    const now = new Date().toISOString();
    expect(timeAgo(now)).toBe('Just now');
  });

  it('returns minutes ago', () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(timeAgo(fiveMinAgo)).toBe('5m ago');
  });

  it('returns hours ago', () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(twoHoursAgo)).toBe('2h ago');
  });

  it('returns days ago', () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(threeDaysAgo)).toBe('3d ago');
  });
});
