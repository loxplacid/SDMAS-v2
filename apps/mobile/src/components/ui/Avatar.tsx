import React from 'react';
import { View, Text, StyleSheet, Image, ViewStyle } from 'react-native';
import { colors, typography, radius } from '@theme/tokens';
import { getInitials } from '@utils/format';

interface AvatarProps {
  name: string;
  size?: number;
  uri?: string;
  style?: ViewStyle;
}

const bgColors = [
  colors.brand[500],
  colors.info,
  colors.success,
  colors.warning,
  '#EC4899',
  '#8B5CF6',
  '#F97316',
  '#14B8A6',
];

export function Avatar({ name, size = 40, uri, style }: AvatarProps) {
  const initials = getInitials(name);
  const bgColor = bgColors[name.length % bgColors.length];
  const fontSize = size * 0.4;

  return (
    <View
      style={[
        styles.container,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: uri ? colors.neutral[200] : bgColor,
        },
        style,
      ]}
    >
      {uri ? (
        <Image source={{ uri }} style={[styles.image, { borderRadius: size / 2 }]} />
      ) : (
        <Text style={[styles.initials, { fontSize }]}>{initials}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  initials: {
    color: '#FFFFFF',
    fontWeight: typography.weights.bold,
    fontFamily: typography.fontFamily,
  },
});
