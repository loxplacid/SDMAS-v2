import { api } from '../client/http-client'
import type { AnalyticsOverview } from './types'

export const analyticsApi = {
  getOverview: () =>
    api.get<AnalyticsOverview>('/api/analytics/overview'),
}
