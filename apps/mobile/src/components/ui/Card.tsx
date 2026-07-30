import React from 'react';
import { View, TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { colors, radius, spacing, shadows } from '@theme/tokens';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  padded?: boolean;
  onPress?: () => void;
  elevated?: boolean;
}

export function Card({ children, style, padded = true, onPress, elevated = true }: CardProps) {
  const content = (
    <View
      style={[
        styles.base,
        elevated && shadows.sm,
        padded && styles.padded,
        onPress && styles.pressable,
        style,
      ]}
    >
      {children}
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
        {content}
      </TouchableOpacity>
    );
  }

  return content;
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  padded: {
    padding: spacing.base,
  },
  pressable: {
    cursor: 'pointer',
  },
});
