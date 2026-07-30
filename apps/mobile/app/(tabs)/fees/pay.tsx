import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Screen, Card, Button, Input, LoadingState, ErrorState, Badge } from '../../../src/components/ui';
import { colors, typography, spacing, radius, shadows } from '../../../src/theme/tokens';
import { useApiData } from '../../../src/hooks/useApiData';
import { getStudentDues, recordPayment } from '../../../src/api/fees';
import { formatCurrency } from '../../../src/utils/format';
import type { FeeDueResponse } from '../../../src/api/fees/types';

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash', icon: 'cash-outline' as const },
  { value: 'bank_transfer', label: 'Bank Transfer', icon: 'business-outline' as const },
  { value: 'card', label: 'Card', icon: 'card-outline' as const },
  { value: 'mobile_money', label: 'Mobile Money', icon: 'phone-portrait-outline' as const },
];

export default function PayFeesScreen() {
  const { studentId, name } = useLocalSearchParams<{ studentId: string; name: string }>();
  const router = useRouter();
  const sid = Number(studentId);

  const [selectedDue, setSelectedDue] = useState<FeeDueResponse | null>(null);
  const [amount, setAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [reference, setReference] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [receiptGenerated, setReceiptGenerated] = useState(false);

  const { data: dues, isLoading, error, refresh } = useApiData<FeeDueResponse[]>(
    useCallback(() => getStudentDues(sid), [sid]),
  );

  const pendingDues = dues?.filter((d) => d.status !== 'paid') ?? [];

  const handleRecordPayment = async () => {
    if (!selectedDue) {
      Alert.alert('Select Due', 'Please select a fee due to pay.');
      return;
    }
    const amountNum = parseFloat(amount);
    if (!amountNum || amountNum <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid payment amount.');
      return;
    }

    setSubmitting(true);
    const resp = await recordPayment({
      fee_due_id: selectedDue.id,
      amount: amountNum,
      payment_method: paymentMethod as any,
      reference_number: reference || undefined,
    });
    setSubmitting(false);

    if (resp.ok) {
      setSuccess(true);
      setReceiptGenerated(true);
    } else {
      Alert.alert('Error', resp.error?.message || 'Failed to record payment');
    }
  };

  if (success) {
    return (
      <Screen>
        <View style={styles.successContainer}>
          <View style={styles.successIcon}>
            <Ionicons name="checkmark-circle" size={72} color={colors.success} />
          </View>
          <Text style={styles.successTitle}>Payment Recorded</Text>
          <Text style={styles.successDesc}>
            Payment of {formatCurrency(parseFloat(amount || '0'))} for {name} has been recorded.
          </Text>
          <View style={styles.successDetail}>
            <Text style={styles.successLabel}>Receipt: {receiptGenerated ? 'Generated' : 'N/A'}</Text>
            <Text style={styles.successLabel}>Method: {paymentMethod.replace('_', ' ')}</Text>
          </View>
          <Button
            title="Back to Fees"
            onPress={() => router.push('/(tabs)/fees')}
            style={{ marginTop: spacing.xl }}
          />
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing['4xl'] }}>
        <Text style={styles.title}>Record Payment</Text>
        <Text style={styles.subtitle}>{name}</Text>

        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : pendingDues.length === 0 ? (
          <Card padded style={styles.noDues}>
            <Ionicons name="checkmark-circle-outline" size={40} color={colors.success} />
            <Text style={styles.noDuesText}>No pending dues for this student</Text>
          </Card>
        ) : (
          <>
            {/* Select Due */}
            <Text style={styles.sectionLabel}>Select Fee Due</Text>
            {pendingDues.map((due) => (
              <TouchableOpacity
                key={due.id}
                style={[
                  styles.dueCard,
                  selectedDue?.id === due.id && styles.dueCardSelected,
                ]}
                onPress={() => {
                  setSelectedDue(due);
                  setAmount(String(due.balance));
                }}
                activeOpacity={0.7}
              >
                <View style={styles.dueRow}>
                  <View style={styles.dueInfo}>
                    <Text style={styles.dueFeeType}>{due.fee_type_name || 'Fee'}</Text>
                    <Text style={styles.dueAmount}>Due: {formatCurrency(due.amount)}</Text>
                    {due.balance > 0 && (
                      <Text style={styles.dueBalance}>
                        Balance: {formatCurrency(due.balance)}
                      </Text>
                    )}
                  </View>
                  <Badge
                    label={due.status}
                    variant={
                      due.status === 'paid' ? 'success' : due.status === 'overdue' ? 'danger' : 'warning'
                    }
                    size="sm"
                  />
                </View>
              </TouchableOpacity>
            ))}

            {/* Payment Form */}
            {selectedDue && (
              <Card padded style={styles.formCard}>
                <Text style={styles.formTitle}>Payment Details</Text>

                <Input
                  label="Amount"
                  value={amount}
                  onChangeText={setAmount}
                  placeholder="0.00"
                  keyboardType="decimal-pad"
                  leftIcon="cash-outline"
                />

                <Text style={[styles.sectionLabel, { marginTop: spacing.sm }]}>
                  Payment Method
                </Text>
                <View style={styles.methodGrid}>
                  {PAYMENT_METHODS.map((method) => (
                    <TouchableOpacity
                      key={method.value}
                      style={[
                        styles.methodCard,
                        paymentMethod === method.value && styles.methodCardSelected,
                      ]}
                      onPress={() => setPaymentMethod(method.value)}
                      activeOpacity={0.7}
                    >
                      <Ionicons
                        name={method.icon}
                        size={20}
                        color={
                          paymentMethod === method.value ? colors.brand[600] : colors.neutral[400]
                        }
                      />
                      <Text
                        style={[
                          styles.methodLabel,
                          paymentMethod === method.value && styles.methodLabelSelected,
                        ]}
                      >
                        {method.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                <Input
                  label="Reference Number (optional)"
                  value={reference}
                  onChangeText={setReference}
                  placeholder="Receipt or transaction ref"
                />

                <Button
                  title="Record Payment"
                  onPress={handleRecordPayment}
                  fullWidth
                  loading={submitting}
                  disabled={!amount || parseFloat(amount) <= 0}
                  style={{ marginTop: spacing.md }}
                />
              </Card>
            )}
          </>
        )}
      </ScrollView>
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
  sectionLabel: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.semibold,
    color: colors.text.secondary,
    marginBottom: spacing.md,
    marginTop: spacing.base,
  },
  dueCard: {
    backgroundColor: colors.surface.card,
    borderRadius: radius.lg,
    padding: spacing.base,
    borderWidth: 1.5,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  dueCardSelected: {
    borderColor: colors.brand[600],
    backgroundColor: colors.brand[50],
  },
  dueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  dueInfo: {
    flex: 1,
  },
  dueFeeType: {
    fontSize: typography.sizes.base,
    fontWeight: typography.weights.medium,
    color: colors.text.primary,
  },
  dueAmount: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    marginTop: 2,
  },
  dueBalance: {
    fontSize: typography.sizes.sm,
    color: colors.warning,
    fontWeight: typography.weights.medium,
    marginTop: 2,
  },
  formCard: {
    marginTop: spacing.lg,
  },
  formTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    color: colors.text.primary,
    marginBottom: spacing.base,
  },
  methodGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.base,
  },
  methodCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface.card,
  },
  methodCardSelected: {
    borderColor: colors.brand[600],
    backgroundColor: colors.brand[50],
  },
  methodLabel: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
  },
  methodLabelSelected: {
    color: colors.brand[600],
    fontWeight: typography.weights.medium,
  },
  noDues: {
    alignItems: 'center',
    paddingVertical: spacing['3xl'],
  },
  noDuesText: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    marginTop: spacing.md,
  },
  successContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
  },
  successIcon: {
    marginBottom: spacing.lg,
  },
  successTitle: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
  successDesc: {
    fontSize: typography.sizes.sm,
    color: colors.text.secondary,
    textAlign: 'center',
  },
  successDetail: {
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  successLabel: {
    fontSize: typography.sizes.sm,
    color: colors.text.tertiary,
  },
});
