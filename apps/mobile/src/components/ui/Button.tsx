import React from 'react';
import {
  TouchableOpacity,
  Text,
  ActivityIndicator,
  StyleSheet,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { colors, typography, spacing, radius, shadows, touchTarget } from '@theme/tokens';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  fullWidth?: boolean;
}

const variantStyles: Record<ButtonVariant, { bg: string; text: string; border?: string }> = {
  primary: { bg: colors.brand[600], text: '#FFFFFF' },
  secondary: { bg: colors.neutral[100], text: colors.neutral[800] },
  outline: { bg: 'transparent', text: colors.brand[600], border: colors.brand[600] },
  ghost: { bg: 'transparent', text: colors.brand[600] },
  danger: { bg: colors.error, text: '#FFFFFF' },
};

const sizeStyles: Record<ButtonSize, { height: number; fontSize: number; paddingHorizontal: number }> = {
  sm: { height: 34, fontSize: typography.sizes.sm, paddingHorizontal: spacing.md },
  md: { height: touchTarget.min, fontSize: typography.sizes.base, paddingHorizontal: spacing.lg },
  lg: { height: 52, fontSize: typography.sizes.md, paddingHorizontal: spacing.xl },
};

export function Button({
  title,
  onPress,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  style,
  textStyle,
  fullWidth = false,
}: ButtonProps) {
  const v = variantStyles[variant];
  const s = sizeStyles[size];
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
      style={[
        styles.base,
        {
          backgroundColor: isDisabled ? colors.neutral[200] : v.bg,
          height: s.height,
          paddingHorizontal: s.paddingHorizontal,
          borderWidth: v.border ? 1.5 : 0,
          borderColor: isDisabled ? colors.neutral[200] : v.border || 'transparent',
          opacity: isDisabled ? 0.6 : 1,
        },
        fullWidth && styles.fullWidth,
        variant === 'primary' && !isDisabled && shadows.sm,
        style,
      ]}
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled }}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={isDisabled ? colors.neutral[400] : v.text}
        />
      ) : (
        <Text
          style={[
            styles.text,
            {
              color: isDisabled ? colors.neutral[400] : v.text,
              fontSize: s.fontSize,
            },
            textStyle,
          ]}
        >
          {title}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    gap: spacing.sm,
  },
  fullWidth: {
    width: '100%',
  },
  text: {
    fontFamily: typography.fontFamily,
    fontWeight: typography.weights.semibold,
  },
});
