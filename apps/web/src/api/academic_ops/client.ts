// Academic Operations API Client
// Thin wrapper around fetch with tenant context and error handling

import {
  Room,
  RoomCreate,
  RoomUpdate,
  RoomPage,
  TimeSlot,
  TimeSlotCreate,
  TimeSlotUpdate,
  TimeSlotPage,
  TimetableEntry,
  TimetableEntryCreate,
  TimetableEntryUpdate,
  TimetableEntryResponse,
  TimetableEntryPage,
  TimetableCheckResult,
  TimetableWeekView,
  Substitution,
  SubstitutionCreate,
  SubstitutionUpdate,
  SubstitutionPage,
  ExamSchedule,
  ExamScheduleCreate,
  ExamScheduleUpdate,
  ExamSchedulePage,
  GradingStructure,
  GradingStructureCreate,
  GradingStructureUpdate,
  GradingStructurePage,
  GradeRecord,
  GradeRecordCreate,
  GradeRecordUpdate,
  GradeRecordPage,
  Curriculum,
  CurriculumCreate,
  CurriculumUpdate,
  CurriculumPage,
} from './types';

const ACADEMIC_BASE = '/api/academic';

interface PaginationParams {
  page?: number;
  size?: number;
}

interface QueryParams extends PaginationParams {
  [key: string]: string | number | boolean | undefined;
}

function buildQuery(params: QueryParams): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      qs.set(k, String(v));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : '';
}

interface ApiError {
  detail?: string;
  message?: string;
  code?: string;
}

class AcademicOpsApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = 'AcademicOpsApiError';
    this.status = status;
    this.code = code;
  }
}

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  });

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    let code: string | undefined;
    try {
      const body = (await res.json()) as ApiError;
      message = body.detail || body.message || message;
      code = body.code;
    } catch {
      // ignore parse errors
    }
    throw new AcademicOpsApiError(res.status, message, code);
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }

  return (await res.json()) as T;
}

// ── Rooms ───────────────────────────────────────────────────────────────

export async function createRoom(data: RoomCreate): Promise<Room> {
  return request<Room>(`${ACADEMIC_BASE}/rooms`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getRoom(id: number): Promise<Room> {
  return request<Room>(`${ACADEMIC_BASE}/rooms/${id}`);
}

export async function listRooms(params: QueryParams = {}): Promise<RoomPage> {
  return request<RoomPage>(`${ACADEMIC_BASE}/rooms${buildQuery(params)}`);
}

export async function updateRoom(id: number, data: RoomUpdate): Promise<Room> {
  return request<Room>(`${ACADEMIC_BASE}/rooms/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteRoom(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/rooms/${id}`, {
    method: 'DELETE',
  });
}

// ── Time Slots ──────────────────────────────────────────────────────────

export async function createTimeSlot(data: TimeSlotCreate): Promise<TimeSlot> {
  return request<TimeSlot>(`${ACADEMIC_BASE}/time-slots`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getTimeSlot(id: number): Promise<TimeSlot> {
  return request<TimeSlot>(`${ACADEMIC_BASE}/time-slots/${id}`);
}

export async function listTimeSlots(params: QueryParams = {}): Promise<TimeSlotPage> {
  return request<TimeSlotPage>(`${ACADEMIC_BASE}/time-slots${buildQuery(params)}`);
}

export async function updateTimeSlot(id: number, data: TimeSlotUpdate): Promise<TimeSlot> {
  return request<TimeSlot>(`${ACADEMIC_BASE}/time-slots/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteTimeSlot(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/time-slots/${id}`, {
    method: 'DELETE',
  });
}

// ── Timetable ───────────────────────────────────────────────────────────

export async function createTimetableEntry(data: TimetableEntryCreate): Promise<TimetableEntryResponse> {
  const res = await request<{ entry: TimetableEntryResponse; conflict_check: TimetableCheckResult }>(
    `${ACADEMIC_BASE}/timetable`,
    { method: 'POST', body: JSON.stringify(data) }
  );
  return res.entry;
}

export async function checkTimetableConflicts(data: TimetableEntryCreate): Promise<TimetableCheckResult> {
  return request<TimetableCheckResult>(`${ACADEMIC_BASE}/timetable/check`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getTimetableEntry(id: number): Promise<TimetableEntryResponse> {
  return request<TimetableEntryResponse>(`${ACADEMIC_BASE}/timetable/${id}`);
}

export async function listTimetableEntries(params: QueryParams = {}): Promise<TimetableEntryPage> {
  return request<TimetableEntryPage>(`${ACADEMIC_BASE}/timetable${buildQuery(params)}`);
}

export async function updateTimetableEntry(id: number, data: TimetableEntryUpdate): Promise<TimetableEntryResponse> {
  const res = await request<{ entry: TimetableEntryResponse; conflict_check: TimetableCheckResult }>(
    `${ACADEMIC_BASE}/timetable/${id}`,
    { method: 'PATCH', body: JSON.stringify(data) }
  );
  return res.entry;
}

export async function deleteTimetableEntry(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/timetable/${id}`, { method: 'DELETE' });
}

export async function getTimetableWeekView(
  scope: 'class' | 'teacher' | 'room',
  scopeId: number,
  academicYearId?: number
): Promise<TimetableWeekView> {
  const params: QueryParams = {};
  if (academicYearId) params.academic_year_id = academicYearId;
  return request<TimetableWeekView>(
    `${ACADEMIC_BASE}/timetable/week/${scope}/${scopeId}${buildQuery(params)}`
  );
}

// ── Substitutions ───────────────────────────────────────────────────────

export async function createSubstitution(data: SubstitutionCreate): Promise<Substitution> {
  return request<Substitution>(`${ACADEMIC_BASE}/substitutions`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getSubstitution(id: number): Promise<Substitution> {
  return request<Substitution>(`${ACADEMIC_BASE}/substitutions/${id}`);
}

export async function listSubstitutions(params: QueryParams = {}): Promise<SubstitutionPage> {
  return request<SubstitutionPage>(`${ACADEMIC_BASE}/substitutions${buildQuery(params)}`);
}

export async function updateSubstitution(id: number, data: SubstitutionUpdate): Promise<Substitution> {
  return request<Substitution>(`${ACADEMIC_BASE}/substitutions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function approveSubstitution(id: number): Promise<Substitution> {
  return request<Substitution>(`${ACADEMIC_BASE}/substitutions/${id}/approve`, {
    method: 'POST',
  });
}

export async function declineSubstitution(id: number, reason?: string): Promise<Substitution> {
  return request<Substitution>(`${ACADEMIC_BASE}/substitutions/${id}/decline`, {
    method: 'POST',
    body: JSON.stringify({ decline_reason: reason }),
  });
}

export async function deleteSubstitution(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/substitutions/${id}`, { method: 'DELETE' });
}

// ── Exam Schedules ──────────────────────────────────────────────────────

export async function createExamSchedule(data: ExamScheduleCreate): Promise<ExamSchedule> {
  return request<ExamSchedule>(`${ACADEMIC_BASE}/exam-schedules`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getExamSchedule(id: number): Promise<ExamSchedule> {
  return request<ExamSchedule>(`${ACADEMIC_BASE}/exam-schedules/${id}`);
}

export async function listExamSchedules(params: QueryParams = {}): Promise<ExamSchedulePage> {
  return request<ExamSchedulePage>(`${ACADEMIC_BASE}/exam-schedules${buildQuery(params)}`);
}

export async function updateExamSchedule(id: number, data: ExamScheduleUpdate): Promise<ExamSchedule> {
  return request<ExamSchedule>(`${ACADEMIC_BASE}/exam-schedules/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteExamSchedule(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/exam-schedules/${id}`, { method: 'DELETE' });
}

// ── Grading Structures ──────────────────────────────────────────────────

export async function createGradingStructure(data: GradingStructureCreate): Promise<GradingStructure> {
  return request<GradingStructure>(`${ACADEMIC_BASE}/grading-structures`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getGradingStructure(id: number): Promise<GradingStructure> {
  return request<GradingStructure>(`${ACADEMIC_BASE}/grading-structures/${id}`);
}

export async function listGradingStructures(params: QueryParams = {}): Promise<GradingStructurePage> {
  return request<GradingStructurePage>(`${ACADEMIC_BASE}/grading-structures${buildQuery(params)}`);
}

export async function updateGradingStructure(id: number, data: GradingStructureUpdate): Promise<GradingStructure> {
  return request<GradingStructure>(`${ACADEMIC_BASE}/grading-structures/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteGradingStructure(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/grading-structures/${id}`, { method: 'DELETE' });
}

// ── Grade Records ───────────────────────────────────────────────────────

export async function createGradeRecord(data: GradeRecordCreate): Promise<GradeRecord> {
  return request<GradeRecord>(`${ACADEMIC_BASE}/grade-records`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getGradeRecord(id: number): Promise<GradeRecord> {
  return request<GradeRecord>(`${ACADEMIC_BASE}/grade-records/${id}`);
}

export async function listGradeRecords(params: QueryParams = {}): Promise<GradeRecordPage> {
  return request<GradeRecordPage>(`${ACADEMIC_BASE}/grade-records${buildQuery(params)}`);
}

export async function updateGradeRecord(id: number, data: GradeRecordUpdate): Promise<GradeRecord> {
  return request<GradeRecord>(`${ACADEMIC_BASE}/grade-records/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteGradeRecord(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/grade-records/${id}`, { method: 'DELETE' });
}

// ── Curricula ───────────────────────────────────────────────────────────

export async function createCurriculum(data: CurriculumCreate): Promise<Curriculum> {
  return request<Curriculum>(`${ACADEMIC_BASE}/curricula`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getCurriculum(id: number): Promise<Curriculum> {
  return request<Curriculum>(`${ACADEMIC_BASE}/curricula/${id}`);
}

export async function listCurricula(params: QueryParams = {}): Promise<CurriculumPage> {
  return request<CurriculumPage>(`${ACADEMIC_BASE}/curricula${buildQuery(params)}`);
}

export async function updateCurriculum(id: number, data: CurriculumUpdate): Promise<Curriculum> {
  return request<Curriculum>(`${ACADEMIC_BASE}/curricula/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteCurriculum(id: number): Promise<void> {
  return request<void>(`${ACADEMIC_BASE}/curricula/${id}`, { method: 'DELETE' });
}

export { AcademicOpsApiError };