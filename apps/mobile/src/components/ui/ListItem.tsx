import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, typography, spacing, radius } from '@theme/tokens';
import { Badge } from './Badge';
import { Avatar } from './Avatar';

interface ListItemProps {
  title: string;
  subtitle?: string;
  leftIcon?: keyof typeof Ionicons.glyphMap;
  leftAvatar?: string;
  rightText?: string;
  rightIcon?: keyof typeof Ionicons.glyphMap;
  badge?: { label: string; variant?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' };
  onPress?: () => void;
  style?: ViewStyle;
}

export function ListItem({
  title,
  subtitle,
  leftIcon,
  leftAvatar,
  rightText,
  rightIcon = 'chevron-forward',
  badge,
  onPress,
  style,
}: ListItemProps) {
  const content = (
    <>
      {leftAvatar && (
        <Avatar name={leftAvatar} size={40} style={styles.left} />
      )}
      {leftIcon && (
        <View style={styles.leftIconContainer}>
          <Ionicons name={leftIcon} size={22} color={colors.neutral[400]} />
        </View>
      )}
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
        {subtitle && (
          <Text style={styles.subtitle} numberOfLines={1}>
            {subtitle}
          </Text>
        )}
      </View>
      <View style={styles.right}>
        {badge && <Badge label={badge.label} variant={badge.variant} size="sm" />}
        {rightText && <Text style={styles.rightText}>{rightText}</Text>}
        {rightIcon && onPress && (
          <Ionicons name={rightIcon} size={18} color={colors.neutral[300]} />
        )}
      </View>
    </>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.6} style={[styles.container, style]}>
        {content}
      </TouchableOpacity>
    );
  }

  return <View style={[styles.container, style]}>{content}</View>;
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    backgroundColor: colors.surface.card,
    borderRadius: radius.md,
    gap: spacing.md,
  },
  left: {
    flexShrink: 0,
  },
  leftIconContainer: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.neutral[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    flex: 1,
  },
  title: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.text.primary,
    fontFamily: typography.fontFamily,
  },
  subtitle: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    marginTop: 1,
    fontFamily: typography.fontFamily,
  },
  right: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flexShrink: 0,
  },
  rightText: {
    fontSize: typography.sizes.sm,
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily,
  },
});
