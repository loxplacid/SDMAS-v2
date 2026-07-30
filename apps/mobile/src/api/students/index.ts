import api from '../client';
import type { StudentResponse, PaginatedResponse } from './types';

const BASE = '/students';

export async function listStudents(params?: {
  page?: number;
  size?: number;
  search?: string;
  status?: string;
}) {
  return api.get<PaginatedResponse<StudentResponse>>(BASE, {
    params: params as Record<string, string | number | undefined>,
  });
}

export async function getStudent(id: number) {
  return api.get<StudentResponse>(`${BASE}/${id}`);
}

export async function searchStudents(query: string, params?: { page?: number; size?: number }) {
  return api.get<PaginatedResponse<StudentResponse>>(BASE, {
    params: { search: query, ...params } as Record<string, string | number | undefined>,
  });
}
