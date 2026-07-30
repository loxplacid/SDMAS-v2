import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, typography, spacing, radius, shadows } from '@theme/tokens';

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: keyof typeof Ionicons.glyphMap;
  color?: string;
  trend?: { value: string; positive: boolean };
}

export function StatCard({ label, value, icon, color = colors.brand[600], trend }: StatCardProps) {
  return (
    <View style={[styles.card, shadows.sm]}>
      <View style={[styles.iconContainer, { backgroundColor: color + '15' }]}>
        {icon && <Ionicons name={icon} size={20} color={color} />}
      </View>
      <View style={styles.textContainer}>
        <Text style={styles.value}>{value}</Text>
        <Text style={styles.label}>{label}</Text>
        {trend && (
          <View style={styles.trendRow}>
            <Ionicons
              name={trend.positive ? 'arrow-up' : 'arrow-down'}
              size={12}
              color={trend.positive ? colors.success : colors.error}
            />
            <Text
              style={[
                styles.trendText,
                { color: trend.positive ? colors.success : colors.error },
              ]}
            >
              {trend.value}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.base,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.md,
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  textContainer: {
    flex: 1,
  },
  value: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
    fontFamily: typography.fontFamilyMono,
  },
  label: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    marginTop: 1,
  },
  trendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginTop: 4,
  },
  trendText: {
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.medium,
  },
});
