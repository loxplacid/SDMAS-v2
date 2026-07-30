import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, radius, spacing } from '@theme/tokens';

type BadgeVariant = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
}

const variantColors: Record<BadgeVariant, { bg: string; text: string }> = {
  primary: { bg: colors.brand[100], text: colors.brand[700] },
  success: { bg: colors.successLight, text: colors.successDark },
  warning: { bg: colors.warningLight, text: colors.warningDark },
  danger: { bg: colors.errorLight, text: colors.errorDark },
  info: { bg: colors.infoLight, text: colors.infoDark },
  neutral: { bg: colors.neutral[100], text: colors.neutral[600] },
};

export function Badge({ label, variant = 'neutral', size = 'sm' }: BadgeProps) {
  const v = variantColors[variant];
  const isSmall = size === 'sm';

  return (
    <View style={[styles.base, { backgroundColor: v.bg }, isSmall ? styles.small : styles.medium]}>
      <Text style={[styles.text, { color: v.text }, isSmall ? styles.textSmall : styles.textMedium]}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    alignSelf: 'flex-start',
    borderRadius: radius.full,
  },
  small: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  medium: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  text: {
    fontWeight: typography.weights.semibold,
    fontFamily: typography.fontFamily,
  },
  textSmall: {
    fontSize: typography.sizes.xs,
  },
  textMedium: {
    fontSize: typography.sizes.sm,
  },
});
