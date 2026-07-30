import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Screen, Badge, Button, EmptyState, ErrorState, ListSkeleton, Divider } from '../../../src/components/ui';
import { colors, typography, spacing, radius } from '../../../src/theme/tokens';
import { useApiData } from '../../../src/hooks/useApiData';
import { listNotifications, markAsRead, markAllAsRead, getUnreadCount } from '../../../src/api/notifications';
import { timeAgo } from '../../../src/utils/format';
import type { NotificationResponse } from '../../../src/api/notifications/types';

const typeIcons: Record<string, keyof typeof Ionicons.glyphMap> = {
  info: 'information-circle',
  success: 'checkmark-circle',
  warning: 'warning',
  error: 'alert-circle',
};

const typeColors: Record<string, string> = {
  info: colors.info,
  success: colors.success,
  warning: colors.warning,
  error: colors.error,
};

export default function NotificationsScreen() {
  const router = useRouter();
  const { data, isLoading, error, refresh } = useApiData<{
    items: NotificationResponse[];
    total: number;
  }>(useCallback(() => listNotifications({ limit: 50 }), []));

  const { data: unreadData, refresh: refreshUnread } = useApiData(
    useCallback(() => getUnreadCount(), []),
  );

  const notifications = data?.items ?? [];
  const unreadCount = unreadData?.count ?? 0;

  const handleMarkRead = async (id: number) => {
    await markAsRead(id);
    refresh();
    refreshUnread();
  };

  const handleMarkAllRead = async () => {
    await markAllAsRead();
    refresh();
    refreshUnread();
  };

  const renderNotification = ({ item }: { item: NotificationResponse }) => (
    <TouchableOpacity
      style={[styles.notifCard, !item.is_read && styles.unreadCard]}
      onPress={() => handleMarkRead(item.id)}
      activeOpacity={0.7}
    >
      <View style={[styles.typeIcon, { backgroundColor: typeColors[item.type] + '20' }]}>
        <Ionicons
          name={typeIcons[item.type] || 'information-circle'}
          size={18}
          color={typeColors[item.type] || colors.neutral[400]}
        />
      </View>
      <View style={styles.notifContent}>
        <View style={styles.notifHeader}>
          <Text style={[styles.notifTitle, !item.is_read && styles.unreadTitle]}>
            {item.title}
          </Text>
          {!item.is_read && <View style={styles.unreadDot} />}
        </View>
        <Text style={styles.notifMessage} numberOfLines={2}>
          {item.message}
        </Text>
        <Text style={styles.notifTime}>{timeAgo(item.created_at)}</Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <Screen>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>Notifications</Text>
          {unreadCount > 0 && (
            <Text style={styles.subtitle}>{unreadCount} unread</Text>
          )}
        </View>
        {unreadCount > 0 && (
          <TouchableOpacity onPress={handleMarkAllRead} style={styles.markAllBtn}>
            <Ionicons name="checkmark-done" size={18} color={colors.brand[600]} />
            <Text style={styles.markAllText}>Mark All Read</Text>
          </TouchableOpacity>
        )}
      </View>

      {isLoading ? (
        <ListSkeleton count={5} />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : notifications.length === 0 ? (
        <EmptyState
          icon="notifications-off-outline"
          title="No Notifications"
          message="You're all caught up! New notifications will appear here."
        />
      ) : (
        <FlatList
          data={notifications}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderNotification}
          contentContainerStyle={{ gap: spacing.sm, paddingBottom: spacing['4xl'] }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={isLoading}
              onRefresh={() => { refresh(); refreshUnread(); }}
              tintColor={colors.brand[600]}
            />
          }
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  title: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
  },
  subtitle: {
    fontSize: typography.sizes.sm,
    color: colors.text.tertiary,
    marginTop: 2,
  },
  markAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.sm,
  },
  markAllText: {
    fontSize: typography.sizes.sm,
    color: colors.brand[600],
    fontWeight: typography.weights.medium,
  },
  notifCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.md,
  },
  unreadCard: {
    backgroundColor: colors.brand[50],
    borderColor: colors.brand[200],
  },
  typeIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  notifContent: {
    flex: 1,
  },
  notifHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  notifTitle: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.medium,
    color: colors.text.primary,
    flex: 1,
  },
  unreadTitle: {
    fontWeight: typography.weights.semibold,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.brand[600],
  },
  notifMessage: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    marginTop: spacing.xs,
    lineHeight: typography.sizes.sm * typography.lineHeight.relaxed,
  },
  notifTime: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    marginTop: spacing.xs + 2,
  },
});
