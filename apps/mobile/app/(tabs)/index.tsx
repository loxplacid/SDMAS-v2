import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Screen, Card, StatCard, Button, SectionHeader, LoadingState, ErrorState, Skeleton } from '../../src/components/ui';
import { useAuth } from '../../src/hooks/useAuth';
import { useApiData } from '../../src/hooks/useApiData';
import { getOverview } from '../../src/api/academic';
import { colors, typography, spacing, radius, shadows } from '../../src/theme/tokens';
import { formatCurrency } from '../../src/utils/format';
import type { OverviewResponse } from '../../src/api/academic/types';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

const quickActions = [
  { icon: 'checkbox-outline' as const, label: 'Take\nAttendance', route: '/(tabs)/attendance' },
  { icon: 'wallet-outline' as const, label: 'Record\nPayment', route: '/(tabs)/fees' },
  { icon: 'people-outline' as const, label: 'View\nStudents', route: '/(tabs)/students' },
  { icon: 'notifications-outline' as const, label: 'View\nAlerts', route: '/(tabs)/notifications' },
];

export default function HomeScreen() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const {
    data: overview,
    isLoading,
    error,
    refresh,
  } = useApiData<OverviewResponse>(useCallback(() => getOverview(), []));

  const onRefresh = useCallback(() => {
    refresh();
  }, [refresh]);

  return (
    <Screen padded={false}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={onRefresh}
            tintColor={colors.brand[600]}
            colors={[colors.brand[600]]}
          />
        }
      >
        {/* Header Area */}
        <View style={styles.headerSection}>
          <View style={styles.greetingRow}>
            <View style={styles.greetingText}>
              <Text style={styles.greeting}>{getGreeting()}</Text>
              <Text style={styles.userName} numberOfLines={1}>
                {user?.display_name || user?.username || 'User'}
              </Text>
              {user?.role && (
                <View style={styles.roleBadge}>
                  <Text style={styles.roleText}>
                    {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                  </Text>
                  {overview?.current_academic_year && (
                    <Text style={styles.yearText}> · {overview.current_academic_year}</Text>
                  )}
                </View>
              )}
            </View>
            <TouchableOpacity style={styles.avatarCircle} onPress={() => router.push('/profile')}>
              <Text style={styles.avatarText}>
                {(user?.display_name || user?.username || '?').charAt(0).toUpperCase()}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Quick Actions */}
        <View style={styles.quickActions}>
          {quickActions.map((action) => (
            <TouchableOpacity
              key={action.label}
              style={styles.quickActionCard}
              activeOpacity={0.7}
              onPress={() => router.push(action.route as any)}
            >
              <View style={styles.quickActionIcon}>
                <Ionicons name={action.icon} size={22} color={colors.brand[600]} />
              </View>
              <Text style={styles.quickActionLabel}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* School Snapshot */}
        <SectionHeader title="School Snapshot" />
        {isLoading ? (
          <View style={{ gap: spacing.sm }}>
            <Skeleton height={72} />
            <Skeleton height={72} />
          </View>
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : overview ? (
          <>
            <View style={styles.statsGrid}>
              <View style={styles.statCol}>
                <StatCard
                  label="Students"
                  value={overview.active_students ?? overview.total_students ?? 0}
                  icon="people"
                  color={colors.brand[600]}
                />
                <StatCard
                  label="Attendance"
                  value={`${(overview.overall_attendance_percentage ?? 0).toFixed(1)}%`}
                  icon="checkmark-circle"
                  color={colors.success}
                />
              </View>
              <View style={styles.statCol}>
                <StatCard
                  label="Teachers"
                  value={overview.total_teachers ?? 0}
                  icon="school"
                  color={colors.info}
                />
                <StatCard
                  label="Classes"
                  value={overview.total_classes ?? 0}
                  icon="layers"
                  color={colors.warning}
                />
              </View>
            </View>

            {/* Financial */}
            <Card elevated style={styles.financialCard}>
              <Text style={styles.financialTitle}>Financial Summary</Text>
              <View style={styles.financialRow}>
                <View style={styles.financialItem}>
                  <Text style={styles.financialLabel}>Collected</Text>
                  <Text style={styles.financialValueGreen}>
                    {formatCurrency(overview.total_collected ?? 0)}
                  </Text>
                </View>
                <View style={styles.financialDivider} />
                <View style={styles.financialItem}>
                  <Text style={styles.financialLabel}>Outstanding</Text>
                  <Text style={styles.financialValueOrange}>
                    {formatCurrency(overview.total_outstanding ?? 0)}
                  </Text>
                </View>
              </View>
            </Card>
          </>
        ) : null}

        {/* Low Attendance Attention */}
        {overview && overview.low_attendance_count > 0 && (
          <Card padded style={styles.attentionCard}>
            <View style={styles.attentionItem}>
              <View style={styles.attentionDot} />
              <Text style={styles.attentionText}>
                <Text style={styles.attentionCount}>{overview.low_attendance_count} </Text>
                students have low attendance (below 90%)
              </Text>
            </View>
          </Card>
        )}

        {/* Unpaid dues attention */}
        {overview && (overview.unpaid_count ?? 0) > 0 && (
          <Card padded style={styles.attentionCard}>
            <View style={styles.attentionItem}>
              <View style={[styles.attentionDot, { backgroundColor: colors.error }]} />
              <Text style={styles.attentionText}>
                <Text style={styles.attentionCount}>{overview.unpaid_count} </Text>
                fee dues are unpaid
              </Text>
            </View>
          </Card>
        )}

        {/* Collection Rate */}
        {overview && overview.collection_percentage > 0 && (
          <Card padded style={styles.todayCard}>
            <View style={styles.todayRow}>
              <View style={styles.todayItem}>
                <Text style={styles.todayNumber}>
                  {overview.collection_percentage.toFixed(1)}%
                </Text>
                <Text style={styles.todayLabel}>Collection Rate</Text>
              </View>
              <View style={styles.todayDivider} />
              <View style={styles.todayItem}>
                <Text style={styles.todayNumber}>
                  {overview.partially_paid_count ?? 0}
                </Text>
                <Text style={styles.todayLabel}>Partially Paid</Text>
              </View>
            </View>
          </Card>
        )}

        {/* Logout */}
        <Button
          title="Sign Out"
          onPress={logout}
          variant="ghost"
          size="sm"
          style={styles.logoutButton}
        />

        <View style={{ height: spacing['4xl'] }} />
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    padding: spacing.base,
    paddingTop: spacing.base,
  },
  headerSection: {
    marginBottom: spacing.lg,
  },
  greetingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  greetingText: {
    flex: 1,
  },
  greeting: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
    letterSpacing: -0.3,
  },
  userName: {
    fontSize: typography.sizes.base,
    color: colors.text.secondary,
    marginTop: 2,
    fontFamily: typography.fontFamily,
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
    gap: 4,
  },
  roleText: {
    fontSize: typography.sizes.xs,
    color: colors.brand[600],
    fontWeight: typography.weights.medium,
    backgroundColor: colors.brand[50],
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.full,
    overflow: 'hidden',
  },
  yearText: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    fontWeight: typography.weights.regular,
  },
  avatarCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.brand[600],
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: '#FFFFFF',
  },
  quickActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  quickActionCard: {
    flex: 1,
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    alignItems: 'center',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.sm,
    ...shadows.sm,
  },
  quickActionIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.brand[50],
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickActionLabel: {
    fontSize: typography.sizes.xs,
    color: colors.text.secondary,
    textAlign: 'center',
    fontWeight: typography.weights.medium,
  },
  statsGrid: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  statCol: {
    flex: 1,
    gap: spacing.sm,
  },
  financialCard: {
    marginBottom: spacing.xs,
  },
  financialTitle: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.semibold,
    color: colors.text.primary,
    marginBottom: spacing.md,
  },
  financialRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  financialItem: {
    flex: 1,
    alignItems: 'center',
  },
  financialLabel: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    marginBottom: 4,
  },
  financialValueGreen: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.success,
    fontFamily: typography.fontFamilyMono,
  },
  financialValueOrange: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.warning,
    fontFamily: typography.fontFamilyMono,
  },
  financialDivider: {
    width: 1,
    height: 40,
    backgroundColor: colors.border,
  },
  attentionCard: {
    marginVertical: spacing.xs,
  },
  attentionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  attentionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.warning,
  },
  attentionText: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    flex: 1,
  },
  attentionCount: {
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
  },
  todayCard: {
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  todayRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  todayItem: {
    flex: 1,
    alignItems: 'center',
  },
  todayNumber: {
    fontSize: typography.sizes['2xl'],
    fontWeight: typography.weights.bold,
    color: colors.brand[600],
    fontFamily: typography.fontFamilyMono,
  },
  todayLabel: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    marginTop: 2,
  },
  todayDivider: {
    width: 1,
    height: 44,
    backgroundColor: colors.border,
  },
  logoutButton: {
    marginTop: spacing.sm,
    alignSelf: 'center',
  },
});
