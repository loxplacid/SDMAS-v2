import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Screen, Card, Button, SectionHeader } from '../../../src/components/ui';
import { colors, typography, spacing, radius, shadows } from '../../../src/theme/tokens';

export default function AttendanceScreen() {
  const router = useRouter();
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <Screen>
      <Text style={styles.title}>Attendance</Text>
      <Text style={styles.subtitle}>{today}</Text>

      <Card padded style={styles.ctaCard}>
        <View style={styles.ctaIcon}>
          <Ionicons name="checkbox-outline" size={32} color={colors.brand[600]} />
        </View>
        <Text style={styles.ctaTitle}>Record Daily Attendance</Text>
        <Text style={styles.ctaDesc}>
          Select a class and section to mark attendance for today or a different date.
        </Text>
        <Button
          title="Mark Attendance"
          onPress={() => router.push('/(tabs)/attendance/mark')}
          size="md"
          fullWidth
        />
      </Card>

      <SectionHeader title="Quick Tips" />
      <Card padded style={{ marginBottom: spacing.sm }}>
        <View style={styles.tipRow}>
          <Ionicons name="checkmark-circle" size={18} color={colors.success} />
          <Text style={styles.tipText}>Tap "Present" to mark a student as present</Text>
        </View>
        <View style={styles.tipRow}>
          <Ionicons name="close-circle" size={18} color={colors.error} />
          <Text style={styles.tipText}>Tap "Absent" to mark a student as absent</Text>
        </View>
        <View style={styles.tipRow}>
          <Ionicons name="time-outline" size={18} color={colors.warning} />
          <Text style={styles.tipText}>Use "Late" for students who arrived after the bell</Text>
        </View>
        <View style={styles.tipRow}>
          <Ionicons name="flash-outline" size={18} color={colors.info} />
          <Text style={styles.tipText}>Use "Mark All Present" to save time</Text>
        </View>
      </Card>

      <View style={{ height: spacing['4xl'] }} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
    marginBottom: 2,
  },
  subtitle: {
    fontSize: typography.sizes.sm,
    color: colors.text.tertiary,
    marginBottom: spacing.lg,
  },
  ctaCard: {
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  ctaIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.brand[50],
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.base,
  },
  ctaTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  ctaDesc: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
    lineHeight: typography.sizes.sm * typography.lineHeight.relaxed,
  },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  tipText: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    flex: 1,
  },
});
