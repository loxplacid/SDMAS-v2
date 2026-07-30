import api from '../client';
import type { OverviewResponse, AcademicYearResponse, ClassResponse } from './types';

export async function getOverview() {
  return api.get<OverviewResponse>('/api/analytics/overview');
}

export async function listAcademicYears(params?: { status?: string }) {
  return api.get<{ items: AcademicYearResponse[]; total: number; page: number }>(
    '/api/academic-years',
    { params: params as Record<string, string | undefined> },
  );
}

export async function listClasses(params?: { academic_year_id?: number; status?: string }) {
  return api.get<{ items: ClassResponse[]; total: number; page: number }>('/api/classes', {
    params: params as Record<string, string | number | undefined>,
  });
}
