import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Screen, Card, Button, Input, Divider, Badge, Avatar } from '../src/components/ui';
import { colors, typography, spacing, radius, shadows } from '../src/theme/tokens';
import { useAuth } from '../src/hooks/useAuth';
import { changeMyPassword } from '../src/api/auth';

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const handleChangePassword = async () => {
    if (!currentPassword || newPassword.length < 8) {
      Alert.alert('Validation', 'New password must be at least 8 characters.');
      return;
    }
    setChangingPassword(true);
    const resp = await changeMyPassword({ current_password: currentPassword, new_password: newPassword });
    setChangingPassword(false);
    if (resp.ok) {
      Alert.alert('Success', 'Password changed successfully.');
      setShowPasswordForm(false);
      setCurrentPassword('');
      setNewPassword('');
    } else {
      Alert.alert('Error', resp.error?.message || 'Failed to change password.');
    }
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing['4xl'] }}>
        {/* Header */}
        <View style={styles.header}>
          <Avatar
            name={user?.display_name || user?.username || '?'}
            size={72}
          />
          <Text style={styles.name}>{user?.display_name || user?.username}</Text>
          <Text style={styles.email}>{user?.email}</Text>
          <Badge
            label={user?.role || 'unknown'}
            variant={user?.role === 'admin' ? 'primary' : 'info'}
            size="md"
          />
          <Text style={styles.joined}>
            Joined {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
          </Text>
        </View>

        {/* Account Info */}
        <Card padded style={styles.section}>
          <Text style={styles.sectionTitle}>Account Information</Text>
          <Divider />
          <InfoRow label="Username" value={user?.username} />
          <InfoRow label="Email" value={user?.email} />
          <InfoRow label="Role" value={user?.role} />
          <InfoRow
            label="Status"
            value={user?.is_active ? 'Active' : 'Inactive'}
            valueColor={user?.is_active ? colors.success : colors.error}
          />
        </Card>

        {/* Change Password */}
        <Card padded style={styles.section}>
          <Text style={styles.sectionTitle}>Security</Text>
          <Divider />
          {!showPasswordForm ? (
            <Button
              title="Change Password"
              onPress={() => setShowPasswordForm(true)}
              variant="outline"
              size="sm"
            />
          ) : (
            <View>
              <Input
                label="Current Password"
                value={currentPassword}
                onChangeText={setCurrentPassword}
                secureTextEntry
                placeholder="Enter current password"
              />
              <Input
                label="New Password"
                value={newPassword}
                onChangeText={setNewPassword}
                secureTextEntry
                placeholder="At least 8 characters"
              />
              <View style={styles.passwordActions}>
                <Button
                  title="Cancel"
                  onPress={() => setShowPasswordForm(false)}
                  variant="ghost"
                  size="sm"
                />
                <Button
                  title="Update Password"
                  onPress={handleChangePassword}
                  size="sm"
                  loading={changingPassword}
                  disabled={!currentPassword || newPassword.length < 8}
                />
              </View>
            </View>
          )}
        </Card>

        {/* Logout */}
        <Button
          title="Sign Out"
          onPress={logout}
          variant="danger"
          fullWidth
          style={{ marginTop: spacing.xl }}
        />

        <Text style={styles.version}>SDMAS Mobile v1.0</Text>
      </ScrollView>
    </Screen>
  );
}

function InfoRow({ label, value, valueColor }: { label: string; value?: string; valueColor?: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, valueColor ? { color: valueColor } : undefined]}>
        {value || 'N/A'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
    marginBottom: spacing.md,
  },
  name: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
    marginTop: spacing.md,
  },
  email: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    marginVertical: spacing.xs,
  },
  joined: {
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    marginTop: spacing.md,
  },
  section: {
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
  },
  infoLabel: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
  },
  infoValue: {
    fontSize: typography.sizes.sm,
    color: colors.text.primary,
    fontWeight: typography.weights.medium,
  },
  passwordActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  version: {
    textAlign: 'center',
    fontSize: typography.sizes.xs,
    color: colors.text.tertiary,
    marginTop: spacing.xl,
  },
});
