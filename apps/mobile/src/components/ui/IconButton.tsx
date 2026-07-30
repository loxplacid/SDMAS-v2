import React from 'react';
import { TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, touchTarget } from '@theme/tokens';

type IconFamily = 'Ionicons' | 'MaterialIcons' | 'Feather';

interface IconButtonProps {
  icon: keyof typeof Ionicons.glyphMap;
  size?: number;
  color?: string;
  onPress?: () => void;
  disabled?: boolean;
  style?: ViewStyle;
  backgroundColor?: string;
  family?: IconFamily;
}

export function IconButton({
  icon,
  size = 22,
  color = colors.neutral[600],
  onPress,
  disabled = false,
  style,
  backgroundColor,
}: IconButtonProps) {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.6}
      style={[
        styles.base,
        {
          width: touchTarget.icon,
          height: touchTarget.icon,
          opacity: disabled ? 0.4 : 1,
        },
        backgroundColor ? { backgroundColor } : undefined,
        style,
      ]}
      hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
    >
      <Ionicons name={icon} size={size} color={color} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
  },
});
