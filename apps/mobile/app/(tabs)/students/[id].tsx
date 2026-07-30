import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { Screen, Card, Badge, Button, SectionHeader, StatCard, LoadingState, ErrorState, Skeleton, Divider } from '../../../src/components/ui';
import { colors, typography, spacing, radius, shadows } from '../../../src/theme/tokens';
import { useApiData } from '../../../src/hooks/useApiData';
import { getStudent } from '../../../src/api/students';
import { getStudentAttendanceSummary } from '../../../src/api/attendance';
import { formatCurrency } from '../../../src/utils/format';
import type { StudentAttendanceSummary } from '../../../src/api/attendance/types';

function getDateRange() {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 1);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

export default function StudentDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const studentId = Number(id);
  const { start, end } = getDateRange();

  const { data: student, isLoading, error, refresh } = useApiData(
    useCallback(() => getStudent(studentId), [studentId]),
  );

  const { data: attendanceSummary } = useApiData<StudentAttendanceSummary>(
    useCallback(
      () => getStudentAttendanceSummary(studentId, start, end),
      [studentId, start, end],
    ),
  );

  if (isLoading) {
    return (
      <Screen>
        <View style={{ gap: spacing.md, paddingTop: spacing.base }}>
          <Skeleton height={40} width={120} />
          <Skeleton height={200} />
          <Skeleton height={100} />
        </View>
      </Screen>
    );
  }

  if (error || !student) {
    return (
      <Screen>
        <ErrorState message={error || 'Student not found'} onRetry={refresh} />
      </Screen>
    );
  }

  return (
    <Screen padded={false}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={refresh} tintColor={colors.brand[600]} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.avatarLarge}>
            <Text style={styles.avatarText}>
              {student.first_name.charAt(0)}{student.last_name.charAt(0)}
            </Text>
          </View>
          <Text style={styles.detailName}>{student.first_name} {student.last_name}</Text>
          <Text style={styles.detailNumber}>{student.student_number}</Text>
          <Badge
            label={student.status}
            variant={student.status === 'active' ? 'success' : 'neutral'}
            size="md"
          />
        </View>

        {/* Attendance Summary */}
        <SectionHeader title="Attendance (Last 30 Days)" />
        {attendanceSummary ? (
          <Card padded>
            <Text style={styles.attPercentage}>
              {attendanceSummary.percentage.toFixed(1)}%
            </Text>
            <View style={styles.attStats}>
              <View style={styles.attStatBox}>
                <Text style={[styles.attNum, { color: colors.success }]}>
                  {attendanceSummary.present}
                </Text>
                <Text style={styles.attLabel}>Present</Text>
              </View>
              <View style={styles.attStatBox}>
                <Text style={[styles.attNum, { color: colors.warning }]}>
                  {attendanceSummary.late}
                </Text>
                <Text style={styles.attLabel}>Late</Text>
              </View>
              <View style={styles.attStatBox}>
                <Text style={[styles.attNum, { color: colors.error }]}>
                  {attendanceSummary.absent}
                </Text>
                <Text style={styles.attLabel}>Absent</Text>
              </View>
            </View>
          </Card>
        ) : (
          <Card padded><Text style={{ color: colors.text.tertiary }}>No attendance data yet</Text></Card>
        )}

        {/* Student Details */}
        <SectionHeader title="Student Details" />
        <Card padded>
          <DetailRow label="Email" value={student.email} />
          <Divider />
          <DetailRow label="Phone" value={student.phone} />
          <Divider />
          <DetailRow label="Gender" value={student.gender} />
          <Divider />
          <DetailRow label="Date of Birth" value={student.date_of_birth} />
          <Divider />
          <DetailRow label="Address" value={student.address} />
          <Divider />
          <DetailRow label="Enrolled" value={student.enrollment_date} />
        </Card>

        <View style={{ height: spacing['4xl'] }} />
      </ScrollView>
    </Screen>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    padding: spacing.base,
  },
  header: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
    backgroundColor: colors.surface.card,
    borderRadius: radius.xl,
    marginBottom: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  avatarLarge: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.brand[100],
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  avatarText: {
    fontSize: typography.sizes['2xl'],
    fontWeight: typography.weights.bold,
    color: colors.brand[700],
  },
  detailName: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
  },
  detailNumber: {
    fontSize: typography.sizes.sm,
    color: colors.text.tertiary,
    marginVertical: spacing.xs,
  },
  attPercentage: {
    fontSize: typography.sizes['3xl'],
    fontWeight: typography.weights.bold,
    color: colors.brand[600],
    textAlign: 'center',
    fontFamily: typography.fontFamilyMono,
  },
  attStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: spacing.md,
  },
  attStatBox: {
    alignItems: 'center',
  },
  attNum: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    fontFamily: typography.fontFamilyMono,
  },
  attLabel: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
  },
  detailLabel: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
  },
  detailValue: {
    fontSize: typography.sizes.sm,
    color: colors.text.primary,
    fontWeight: typography.weights.medium,
    textAlign: 'right',
    flex: 1,
  },
});
