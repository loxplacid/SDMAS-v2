import api from '../client';
import type { PaymentCreate, PaymentResult, StudentFinancialSummary, FeeDueResponse } from './types';

export async function getStudentDues(studentId: number, academicYearId?: number) {
  return api.get<FeeDueResponse[]>(`/api/fees/students/${studentId}/dues`, {
    params: { academic_year_id: academicYearId },
  });
}

export async function getStudentFinancialSummary(studentId: number, academicYearId: number) {
  return api.get<StudentFinancialSummary>(`/api/fees/students/${studentId}/summary`, {
    params: { academic_year_id: academicYearId },
  });
}

export async function recordPayment(data: PaymentCreate) {
  return api.post<PaymentResult>('/api/fees/payments', data);
}

export async function getStudentPayments(studentId: number) {
  return api.get<{ items: Array<import('./types').PaymentResponse>; total: number }>(
    `/api/fees/students/${studentId}/payments`,
  );
}
