import React, { useState, useCallback } from 'react';
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

import { Screen, Card, SearchInput, Badge, LoadingState, ErrorState, EmptyState, ListSkeleton } from '../../../src/components/ui';
import { colors, typography, spacing, radius } from '../../../src/theme/tokens';
import { useApiData } from '../../../src/hooks/useApiData';
import { listStudents } from '../../../src/api/students';
import type { StudentResponse } from '../../../src/api/students/types';

export default function StudentListScreen() {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const fetchStudents = useCallback(
    () => listStudents({ page, size: 20, search: search || undefined }),
    [page, search],
  );

  const { data, isLoading, error, refresh } = useApiData(fetchStudents, [page, search]);

  const students = data?.items ?? [];
  const total = data?.total ?? 0;

  const renderStudent = ({ item }: { item: StudentResponse }) => (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={() => router.push(`/(tabs)/students/${item.id}`)}
      style={styles.studentCard}
    >
      <View style={styles.avatarBox}>
        <Text style={styles.avatarInitial}>
          {item.first_name.charAt(0)}{item.last_name.charAt(0)}
        </Text>
      </View>
      <View style={styles.studentInfo}>
        <Text style={styles.studentName}>
          {item.first_name} {item.last_name}
        </Text>
        <Text style={styles.studentNumber}>{item.student_number}</Text>
      </View>
      <Badge
        label={item.status === 'active' ? 'Active' : 'Inactive'}
        variant={item.status === 'active' ? 'success' : 'neutral'}
        size="sm"
      />
      <Ionicons name="chevron-forward" size={16} color={colors.neutral[300]} />
    </TouchableOpacity>
  );

  return (
    <Screen>
      <Text style={styles.title}>Students</Text>
      <Text style={styles.subtitle}>{total} total students</Text>

      <SearchInput
        value={search}
        onChangeText={(text) => { setSearch(text); setPage(1); }}
        placeholder="Search by name or number..."
        onClear={() => { setSearch(''); setPage(1); }}
      />

      {isLoading && students.length === 0 ? (
        <ListSkeleton count={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : students.length === 0 ? (
        <EmptyState
          icon="people-outline"
          title="No Students Found"
          message={search ? 'Try a different search term' : 'No students have been added yet'}
        />
      ) : (
        <FlatList
          data={students}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderStudent}
          contentContainerStyle={{ paddingBottom: spacing['4xl'], gap: spacing.sm }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={isLoading}
              onRefresh={refresh}
              tintColor={colors.brand[600]}
            />
          }
          ListFooterComponent={
            total > page * 20 ? (
              <TouchableOpacity
                style={styles.loadMore}
                onPress={() => setPage((p) => p + 1)}
              >
                <Text style={styles.loadMoreText}>Load More</Text>
              </TouchableOpacity>
            ) : null
          }
        />
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
    marginBottom: spacing.base,
  },
  studentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: spacing.md,
  },
  avatarBox: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.brand[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.bold,
    color: colors.brand[700],
  },
  studentInfo: {
    flex: 1,
  },
  studentName: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.text.primary,
  },
  studentNumber: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    marginTop: 1,
  },
  loadMore: {
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  loadMoreText: {
    fontSize: typography.sizes.sm,
    color: colors.brand[600],
    fontWeight: typography.weights.medium,
  },
});
