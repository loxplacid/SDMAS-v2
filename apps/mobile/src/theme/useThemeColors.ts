import { useColorScheme } from 'react-native';
import { colors } from './tokens';

interface ThemeReturn {
  [key: string]: unknown;
  bg: string;
  card: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  border: string;
  borderLight: string;
  surface: typeof colors.surface & { bg: string; card: string; elevated: string; input: string; hover: string; pressed: string };
  textColors: typeof colors.text & { primary: string; secondary: string; tertiary: string };
}

/** Returns theme-aware semantic color overrides for light/dark mode. */
export function useThemeColors() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  if (!isDark) {
    return {
      ...colors,
      bg: colors.surface.bg,
      card: colors.surface.card,
      text: colors.text.primary,
      textSecondary: colors.text.secondary,
      textTertiary: colors.text.tertiary,
      border: colors.border,
      borderLight: colors.borderLight,
      surface: colors.surface,
      textColors: colors.text,
    } as ThemeReturn;
  }

  // Dark mode overrides
  return {
    ...colors,
    bg: colors.neutral[900],
    card: colors.neutral[800],
    text: colors.neutral[50],
    textSecondary: colors.neutral[300],
    textTertiary: colors.neutral[400],
    border: colors.neutral[700],
    borderLight: colors.neutral[800],
    surface: {
      ...colors.surface,
      bg: colors.neutral[900],
      card: colors.neutral[800],
      elevated: colors.neutral[850],
      input: colors.neutral[800],
      hover: colors.neutral[700],
      pressed: colors.neutral[600],
    },
    textColors: {
      ...colors.text,
      primary: colors.neutral[50],
      secondary: colors.neutral[300],
      tertiary: colors.neutral[400],
    },
  } as ThemeReturn;
}

export type ThemeColors = ThemeReturn;
