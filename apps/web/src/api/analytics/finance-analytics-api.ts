import { api } from '../client/http-client'
import type {
  FinanceOverview,
  CollectionTrend,
  FeeTypeCollection,
  ClassFeeCollection,
  PaymentMethodDistribution,
  FeeStatusDistribution,
} from './types'

export type FinanceAnalyticsParams = {
  academic_year_id?: number
  granularity?: string
}

export const financeAnalyticsApi = {
  getOverview: (params: FinanceAnalyticsParams = {}) =>
    api.get<FinanceOverview>('/api/analytics/finance/overview', params as any),

  getTrends: (params: FinanceAnalyticsParams = {}) =>
    api.get<CollectionTrend>('/api/analytics/finance/trends', params as any),

  getFeeTypeCollection: (params: FinanceAnalyticsParams = {}) =>
    api.get<FeeTypeCollection[]>('/api/analytics/finance/fee-types', params as any),

  getClassCollection: (params: FinanceAnalyticsParams = {}) =>
    api.get<ClassFeeCollection[]>('/api/analytics/finance/classes', params as any),

  getPaymentMethods: (params: FinanceAnalyticsParams = {}) =>
    api.get<PaymentMethodDistribution[]>('/api/analytics/finance/payment-methods', params as any),

  getStatusDistribution: (params: FinanceAnalyticsParams = {}) =>
    api.get<FeeStatusDistribution[]>('/api/analytics/finance/status', params as any),
}
