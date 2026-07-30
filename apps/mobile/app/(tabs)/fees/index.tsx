import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Screen, Card, Button, SearchInput, SectionHeader, LoadingState, ErrorState } from '../../../src/components/ui';
import { colors, typography, spacing, radius, shadows } from '../../../src/theme/tokens';
import { useApiData } from '../../../src/hooks/useApiData';
import { listStudents } from '../../../src/api/students';
import { formatCurrency } from '../../../src/utils/format';
import type { StudentResponse } from '../../../src/api/students/types';

export default function FeesScreen() {
  const router = useRouter();
  const [search, setSearch] = useState('');

  const { data, isLoading, error, refresh } = useApiData(
    useCallback(() => listStudents({ page: 1, size: 20 }), []),
  );

  const students = data?.items ?? [];
  const filtered = search
    ? students.filter(
        (s) =>
          `${s.first_name} ${s.last_name}`.toLowerCase().includes(search.toLowerCase()) ||
          s.student_number?.toLowerCase().includes(search.toLowerCase()),
      )
    : students;

  return (
    <Screen>
      <Text style={styles.title}>Fees</Text>
      <Text style={styles.subtitle}>View dues and record payments</Text>

      <Card padded style={styles.ctaCard}>
        <View style={styles.ctaIcon}>
          <Ionicons name="wallet-outline" size={28} color={colors.brand[600]} />
        </View>
        <Text style={styles.ctaTitle}>Record a Payment</Text>
        <Text style={styles.ctaDesc}>
          Search for a student below to view their fee details and record payments.
        </Text>
      </Card>

      <SearchInput
        value={search}
        onChangeText={setSearch}
        placeholder="Search student..."
        onClear={() => setSearch('')}
      />

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : filtered.length === 0 ? (
        <View style={{ padding: spacing.xl, alignItems: 'center' }}>
          <Text style={{ color: colors.text.tertiary }}>No students found</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ gap: spacing.sm, paddingBottom: spacing['4xl'] }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={isLoading} onRefresh={refresh} tintColor={colors.brand[600]} />
          }
        >
          {filtered.map((student) => (
            <TouchableOpacity
              key={student.id}
              style={styles.studentRow}
              onPress={() => router.push(`/(tabs)/fees/pay?studentId=${student.id}&name=${student.first_name} ${student.last_name}`)}
              activeOpacity={0.7}
            >
              <View style={styles.avatarSmall}>
                <Text style={styles.avatarText}>
                  {student.first_name.charAt(0)}{student.last_name.charAt(0)}
                </Text>
              </View>
              <View style={styles.studentInfo}>
                <Text style={styles.studentName}>
                  {student.first_name} {student.last_name}
                </Text>
                <Text style={styles.studentNumber}>{student.student_number}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.neutral[300]} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
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
    marginBottom: spacing.lg,
    alignItems: 'center',
  },
  ctaIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.brand[50],
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  ctaTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    color: colors.text.primary,
    marginBottom: spacing.xs,
  },
  ctaDesc: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    textAlign: 'center',
  },
  studentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.md,
  },
  avatarSmall: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.infoLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.bold,
    color: colors.info,
  },
  studentInfo: { flex: 1 },
  studentName: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.text.primary,
  },
  studentNumber: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
  },
});
