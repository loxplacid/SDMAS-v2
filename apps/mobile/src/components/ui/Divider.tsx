import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { colors, spacing } from '@theme/tokens';

interface DividerProps {
  style?: ViewStyle;
  inset?: boolean;
}

export function Divider({ style, inset = false }: DividerProps) {
  return (
    <View
      style={[
        styles.divider,
        inset && styles.inset,
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
    marginVertical: spacing.sm,
  },
  inset: {
    marginLeft: spacing.base,
  },
});
