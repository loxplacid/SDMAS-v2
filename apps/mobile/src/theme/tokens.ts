import { Platform } from 'react-native';

// ─── Color Palette ───────────────────────────────────────────────────
export const colors = {
  // Brand
  brand: {
    50: '#EEF2FF',
    100: '#E0E7FF',
    200: '#C7D2FE',
    300: '#A5B4FC',
    400: '#818CF8',
    500: '#6366F1',
    600: '#4F46E5',
    700: '#4338CA',
    800: '#3730A3',
    900: '#312E81',
  },

  // Neutrals
  neutral: {
    50: '#F8FAFC',
    100: '#F1F5F9',
    150: '#E9EEF4',
    200: '#E2E8F0',
    300: '#CBD5E1',
    400: '#94A3B8',
    500: '#64748B',
    600: '#475569',
    700: '#334155',
    800: '#1E293B',
    850: '#172032',
    900: '#0F172A',
    950: '#020617',
  },

  // Semantic
  success: '#10B981',
  successLight: '#D1FAE5',
  successDark: '#065F46',

  warning: '#F59E0B',
  warningLight: '#FEF3C7',
  warningDark: '#92400E',

  error: '#EF4444',
  errorLight: '#FEE2E2',
  errorDark: '#991B1B',

  info: '#3B82F6',
  infoLight: '#DBEAFE',
  infoDark: '#1E40AF',

  // Surface (light mode)
  surface: {
    bg: '#FFFFFF',
    card: '#FFFFFF',
    elevated: '#FFFFFF',
    modal: '#FFFFFF',
    input: '#F8FAFC',
    hover: '#F1F5F9',
    pressed: '#E2E8F0',
    disabled: '#F1F5F9',
  },

  // Text (light mode)
  text: {
    primary: '#0F172A',
    secondary: '#475569',
    tertiary: '#94A3B8',
    inverse: '#FFFFFF',
    disabled: '#CBD5E1',
    link: '#4F46E5',
    success: '#065F46',
    warning: '#92400E',
    error: '#991B1B',
    info: '#1E40AF',
  },

  // Borders
  border: '#E2E8F0',
  borderLight: '#F1F5F9',
  borderFocus: '#6366F1',

  // Misc
  backdrop: 'rgba(15, 23, 42, 0.5)',
  overlay: 'rgba(0, 0, 0, 0.05)',
  shadow: 'rgba(15, 23, 42, 0.08)',
};

// ─── Typography ──────────────────────────────────────────────────────
export const typography = {
  fontFamily: Platform.select({
    ios: 'System',
    android: 'Roboto',
    default: 'System',
  }),
  fontFamilyMono: Platform.select({
    ios: 'Menlo',
    android: 'monospace',
    default: 'monospace',
  }),
  weights: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
  },
  sizes: {
    xs: 11,
    sm: 13,
    base: 15,
    md: 17,
    lg: 20,
    xl: 24,
    '2xl': 30,
    '3xl': 36,
  },
  lineHeight: {
    tight: 1.2,
    normal: 1.4,
    relaxed: 1.6,
  },
};

// ─── Spacing ─────────────────────────────────────────────────────────
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  '2xl': 32,
  '3xl': 40,
  '4xl': 48,
  '5xl': 64,
};

// ─── Border Radius ───────────────────────────────────────────────────
export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
  xl: 20,
  full: 9999,
};

// ─── Shadows / Elevation ─────────────────────────────────────────────
export const shadows = {
  sm: {
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 2,
    elevation: 1,
  },
  md: {
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 6,
    elevation: 3,
  },
  lg: {
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 5,
  },
};

// ─── Motion ──────────────────────────────────────────────────────────
export const motion = {
  fast: 150,
  normal: 250,
  slow: 350,
  easing: {
    standard: { type: 'timing' as const, duration: 250 },
    emphasize: { type: 'spring' as const, damping: 15, stiffness: 200 },
  },
};

// ─── Touch Targets ───────────────────────────────────────────────────
export const touchTarget = {
  min: 44,
  icon: 40,
};

// ─── Export all as a single tokens object ────────────────────────────
export const tokens = {
  colors,
  typography,
  spacing,
  radius,
  shadows,
  motion,
  touchTarget,
} as const;

export default tokens;
