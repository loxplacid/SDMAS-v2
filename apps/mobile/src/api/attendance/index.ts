import api from '../client';
import type {
  AttendanceRecordResponse,
  DailyAttendanceCreate,
  SectionAttendanceSummary,
  StudentAttendanceSummary,
  SectionResponse,
} from './types';

const BASE = '/attendance';

export async function recordDailyAttendance(data: DailyAttendanceCreate) {
  return api.post<AttendanceRecordResponse[]>(`${BASE}/daily`, data);
}

export async function getSectionAttendance(sectionId: number, attendanceDate: string) {
  return api.get<AttendanceRecordResponse[]>(`${BASE}/section/${sectionId}`, {
    params: { attendance_date: attendanceDate },
  });
}

export async function getSectionSummary(sectionId: number, attendanceDate: string) {
  return api.get<SectionAttendanceSummary>(`${BASE}/section/${sectionId}/summary`, {
    params: { attendance_date: attendanceDate },
  });
}

export async function getStudentAttendanceSummary(
  studentId: number,
  startDate: string,
  endDate: string,
) {
  return api.get<StudentAttendanceSummary>(`${BASE}/student/${studentId}/summary`, {
    params: { start_date: startDate, end_date: endDate },
  });
}

/* ─── Academic sections (for the picker) ─────────────────────────── */

export async function listSections(classId?: number) {
  return api.get<{ items: SectionResponse[]; total: number }>('/api/sections', {
    params: { class_id: classId },
  });
}
