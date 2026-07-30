import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Screen, Button, LoadingState, ErrorState } from '../../../src/components/ui';
import { colors, typography, spacing, radius, shadows } from '../../../src/theme/tokens';
import { useApiData } from '../../../src/hooks/useApiData';
import { getSectionAttendance, recordDailyAttendance, listSections } from '../../../src/api/attendance';
import type { AttendanceRecordResponse, SectionResponse } from '../../../src/api/attendance/types';

type AttendanceStatus = 'present' | 'absent' | 'late' | 'excused';

export default function MarkAttendanceScreen() {
  const router = useRouter();
  const [step, setStep] = useState<'select' | 'mark' | 'confirm'>('select');
  const [selectedSection, setSelectedSection] = useState<SectionResponse | null>(null);
  const today = new Date().toISOString().split('T')[0];

  const { data: sections, isLoading: sectionsLoading } = useApiData<{ items: SectionResponse[]; total: number }>(
    useCallback(() => listSections(), []),
  );

  const [records, setRecords] = useState<AttendanceRecordResponse[]>([]);
  const [statuses, setStatuses] = useState<Record<number, AttendanceStatus>>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSectionSelect = async (section: SectionResponse) => {
    setSelectedSection(section);
    const resp = await getSectionAttendance(section.id, today);
    if (resp.ok && resp.data) {
      setRecords(resp.data);
      const defaults: Record<number, AttendanceStatus> = {};
      resp.data.forEach((r) => { defaults[r.student_id] = 'present'; });
      setStatuses(defaults);
      setStep('mark');
    } else {
      Alert.alert('Error', 'Failed to load student list for this section.');
    }
  };

  const toggleStatus = (studentId: number) => {
    setStatuses((prev) => {
      const current = prev[studentId] || 'present';
      const order: AttendanceStatus[] = ['present', 'absent', 'late', 'excused'];
      const next = order[(order.indexOf(current) + 1) % order.length];
      return { ...prev, [studentId]: next };
    });
  };

  const markAllPresent = () => {
    const allPresent: Record<number, AttendanceStatus> = {};
    records.forEach((r) => { allPresent[r.student_id] = 'present'; });
    setStatuses(allPresent);
  };

  const handleSubmit = async () => {
    if (!selectedSection) return;
    setSubmitting(true);

    const attendanceData = {
      section_id: selectedSection.id,
      attendance_date: today,
      records: Object.entries(statuses).map(([studentId, status]) => ({
        student_id: Number(studentId),
        status,
      })),
    };

    const resp = await recordDailyAttendance(attendanceData);
    setSubmitting(false);

    if (resp.ok) {
      setStep('confirm');
    } else {
      Alert.alert('Error', resp.error?.message || 'Failed to record attendance');
    }
  };

  const statusColors: Record<AttendanceStatus, { bg: string; text: string; label: string }> = {
    present: { bg: colors.successLight, text: colors.success, label: 'P' },
    absent: { bg: colors.errorLight, text: colors.error, label: 'A' },
    late: { bg: colors.warningLight, text: colors.warning, label: 'L' },
    excused: { bg: colors.infoLight, text: colors.info, label: 'E' },
  };

  if (step === 'select') {
    return (
      <Screen>
        <Text style={styles.title}>Select Section</Text>
        <Text style={styles.subtitle}>Choose a class section to mark attendance for today</Text>
        {sectionsLoading ? (
          <LoadingState message="Loading sections..." />
        ) : !sections?.items?.length ? (
          <ErrorState message="No sections available" />
        ) : (
          <FlatList
            data={sections.items}
            keyExtractor={(item) => String(item.id)}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={styles.sectionCard}
                onPress={() => handleSectionSelect(item)}
                activeOpacity={0.7}
              >
                <View style={styles.sectionInfo}>
                  <Text style={styles.sectionName}>{item.name}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.neutral[300]} />
              </TouchableOpacity>
            )}
            contentContainerStyle={{ gap: spacing.sm, paddingBottom: spacing['4xl'] }}
          />
        )}
      </Screen>
    );
  }

  if (step === 'mark') {
    return (
      <Screen>
        <View style={styles.headerRow}>
          <TouchableOpacity onPress={() => setStep('select')}>
            <Ionicons name="arrow-back" size={22} color={colors.text.primary} />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <Text style={styles.titleSmall}>{selectedSection?.name}</Text>
            <Text style={styles.subtitleSmall}>Tap to toggle: P → A → L → E</Text>
          </View>
          <TouchableOpacity onPress={markAllPresent}>
            <Ionicons name="flash" size={22} color={colors.brand[600]} />
          </TouchableOpacity>
        </View>

        <FlatList
          data={records}
          keyExtractor={(item) => String(item.student_id)}
          renderItem={({ item }) => {
            const status = statuses[item.student_id] || 'present';
            const s = statusColors[status];
            return (
              <TouchableOpacity
                style={styles.studentRow}
                onPress={() => toggleStatus(item.student_id)}
                activeOpacity={0.7}
              >
                <Text style={styles.studentName}>Student #{item.student_id}</Text>
                <View style={[styles.statusBadge, { backgroundColor: s.bg }]}>
                  <Text style={[styles.statusLabel, { color: s.text }]}>{s.label}</Text>
                </View>
              </TouchableOpacity>
            );
          }}
          contentContainerStyle={{ gap: spacing.sm, paddingBottom: spacing.md }}
        />

        <View style={styles.bottomBar}>
          <TouchableOpacity onPress={() => setStep('select')} style={styles.cancelBtn}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
          <Button
            title="Submit Attendance"
            onPress={handleSubmit}
            loading={submitting}
            size="md"
            style={{ flex: 1 }}
          />
        </View>
      </Screen>
    );
  }

  // Confirmation
  return (
    <Screen>
      <View style={styles.confirmContainer}>
        <View style={styles.confirmIcon}>
          <Ionicons name="checkmark-circle" size={64} color={colors.success} />
        </View>
        <Text style={styles.confirmTitle}>Attendance Recorded</Text>
        <Text style={styles.confirmDesc}>
          Attendance for {selectedSection?.name} on {today} has been recorded successfully.
        </Text>
        <View style={styles.confirmStats}>
          <Text style={styles.confirmStat}>
            {Object.values(statuses).filter((s) => s === 'present').length} Present
          </Text>
          <Text style={styles.confirmStat}>
            {Object.values(statuses).filter((s) => s === 'absent').length} Absent
          </Text>
          <Text style={styles.confirmStat}>
            {Object.values(statuses).filter((s) => s === 'late').length} Late
          </Text>
        </View>
        <Button
          title="Back to Attendance"
          onPress={() => router.push('/(tabs)/attendance')}
          style={{ marginTop: spacing.xl }}
        />
      </View>
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
  titleSmall: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    color: colors.text.primary,
  },
  subtitleSmall: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
  },
  sectionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.base,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  sectionInfo: { flex: 1 },
  sectionName: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.text.primary,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.lg,
    gap: spacing.md,
  },
  headerCenter: { flex: 1 },
  studentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface.card,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    justifyContent: 'space-between',
  },
  studentName: {
    fontSize: typography.sizes.base,
    color: colors.text.primary,
    fontWeight: typography.weights.medium,
  },
  statusBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusLabel: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.bold,
  },
  bottomBar: {
    flexDirection: 'row',
    gap: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    marginTop: spacing.sm,
  },
  cancelBtn: {
    paddingHorizontal: spacing.base,
    justifyContent: 'center',
  },
  cancelText: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    fontWeight: typography.weights.medium,
  },
  confirmContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
  },
  confirmIcon: {
    marginBottom: spacing.lg,
  },
  confirmTitle: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  confirmDesc: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    textAlign: 'center',
    lineHeight: typography.sizes.sm * typography.lineHeight.relaxed,
  },
  confirmStats: {
    flexDirection: 'row',
    gap: spacing.xl,
    marginTop: spacing.lg,
  },
  confirmStat: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    fontWeight: typography.weights.medium,
  },
});
