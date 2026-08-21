// Academic Operations API Types
// Generated from backend schemas in app.domains.academic_ops.schemas

export interface Room {
  id: number;
  name: string;
  code: string;
  room_type: string;
  capacity: number;
  floor: number | null;
  building: string | null;
  equipment: string[];
  status: 'active' | 'inactive' | 'maintenance';
  created_at: string;
  updated_at: string;
  campus_id: number | null;
}

export interface RoomCreate {
  name: string;
  code: string;
  room_type: string;
  capacity: number;
  floor?: number;
  building?: string;
  equipment?: string[];
}

export interface RoomUpdate {
  name?: string;
  code?: string;
  capacity?: number;
  floor?: number;
  building?: string;
  equipment?: string[];
  status?: 'active' | 'inactive' | 'maintenance';
}

export interface RoomPage {
  items: Room[];
  total: number;
  page: number;
  size: number;
}

export interface TimeSlot {
  id: number;
  name: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_type: 'period' | 'break' | 'lunch';
  duration_minutes: number;
  status: 'active' | 'inactive';
  academic_year_id: number;
  created_at: string;
  updated_at: string;
  campus_id: number | null;
}

export interface TimeSlotCreate {
  name: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_type: 'period' | 'break' | 'lunch';
  duration_minutes: number;
  academic_year_id: number;
}

export interface TimeSlotUpdate {
  name?: string;
  start_time?: string;
  end_time?: string;
  status?: 'active' | 'inactive';
}

export interface TimeSlotPage {
  items: TimeSlot[];
  total: number;
  page: number;
  size: number;
}

export type TimetableEntryStatus = 'scheduled' | 'completed' | 'cancelled' | 'conflict';

export interface TimetableEntry {
  id: number;
  class_id: number;
  section_id: number | null;
  teacher_id: number;
  time_slot_id: number;
  room_id: number;
  academic_year_id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  subject_id: number;
  topic: string | null;
  status: TimetableEntryStatus;
  created_at: string;
  updated_at: string;
  campus_id: number | null;
}

export interface TimetableEntryCreate {
  class_id: number;
  section_id?: number;
  teacher_id: number;
  time_slot_id: number;
  room_id: number;
  academic_year_id: number;
  subject_id: number;
  topic?: string;
}

export interface TimetableEntryUpdate {
  teacher_id?: number;
  room_id?: number;
  time_slot_id?: number;
  subject_id?: number;
  topic?: string;
  status?: TimetableEntryStatus;
}

export interface TimetableEntryResponse extends TimetableEntry {
  class_name?: string;
  section_name?: string;
  teacher_name?: string;
  subject_name?: string;
  time_slot_name?: string;
  room_name?: string;
  conflict_check?: TimetableCheckResult;
}

export interface TimetableEntryPage {
  items: TimetableEntryResponse[];
  total: number;
  page: number;
  size: number;
}

export interface TimetableCheckResult {
  has_conflicts: boolean;
  conflicts: ConflictDetail[];
  warnings: string[];
}

export interface ConflictDetail {
  type: 'room' | 'teacher' | 'time_slot';
  description: string;
  conflicting_entry_id: number;
  conflicting_details: {
    room?: Room;
    teacher?: { id: number; name: string };
    time_slot?: TimeSlot;
  };
}

export interface TimetableWeekView {
  days: DayOfWeekEntry[];
  class_id: number;
  academic_year_id: number;
}

export interface DayOfWeekEntry {
  day: number;
  date: string;
  slots: TimetableEntryResponse[];
}

export interface Substitution {
  id: number;
  timetable_entry_id: number;
  original_teacher_id: number;
  substitute_teacher_id: number;
  reason: string;
  status: 'pending' | 'approved' | 'declined' | 'cancelled';
  requested_at: string;
  approved_at: string | null;
  declined_at: string | null;
  approved_by?: number;
  decline_reason?: string | null;
  campus_id: number | null;
}

export interface SubstitutionCreate {
  timetable_entry_id: number;
  substitute_teacher_id: number;
  reason: string;
}

export interface SubstitutionUpdate {
  reason?: string;
  status?: 'pending' | 'approved' | 'declined' | 'cancelled';
}

export interface SubstitutionPage {
  items: Substitution[];
  total: number;
  page: number;
  size: number;
}

export interface ExamSchedule {
  id: number;
  class_id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  room_id: number | null;
  academic_year_id: number;
  term_id: number | null;
  status: 'scheduled' | 'published' | 'cancelled';
  created_at: string;
  updated_at: string;
  campus_id: number | null;
}

export interface ExamScheduleCreate {
  class_id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  room_id?: number;
  academic_year_id: number;
  term_id?: number;
}

export interface ExamScheduleUpdate {
  exam_name?: string;
  exam_date?: string;
  start_time?: string;
  end_time?: string;
  room_id?: number;
  status?: 'scheduled' | 'published' | 'cancelled';
}

export interface ExamSchedulePage {
  items: ExamSchedule[];
  total: number;
  page: number;
  size: number;
}

export interface GradingStructure {
  id: number;
  name: string;
  description: string | null;
  academic_year_id: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  campus_id: number | null;
  components?: GradingComponent[];
}

export interface GradingComponent {
  id: number;
  name: string;
  max_points: number;
  weight: number;
  grading_type: 'numeric' | 'letter' | 'pass_fail';
  is_extra_credit: boolean;
  order: number;
}

export interface GradingStructureCreate {
  name: string;
  academic_year_id: number;
  description?: string;
  components?: Omit<GradingComponent, 'id' | 'grading_type'>[];
}

export interface GradingStructureUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
  components?: Array<Omit<GradingComponent, 'id' | 'grading_type'> & { id?: number }>;
}

export interface GradingStructurePage {
  items: GradingStructure[];
  total: number;
  page: number;
  size: number;
}

export interface GradeRecord {
  id: number;
  enrollment_id: number;
  subject_id: number;
  grading_structure_id: number;
  academic_year_id: number;
  term_id: number | null;
  components?: GradeComponentScore[];
  final_grade: string | number;
  status: 'draft' | 'pending' | 'approved' | 'published';
  recorded_at: string | null;
  recorded_by?: number | null;
  created_at: string;
  updated_at: string;
  campus_id: number | null;
}

export interface GradeComponentScore {
  id: number;
  component_name: string;
  points_earned: number;
  points_possible: number;
  percentage: number;
  feedback: string | null;
}

export interface GradeRecordCreate {
  enrollment_id: number;
  subject_id: number;
  grading_structure_id: number;
  academic_year_id: number;
  components?: Omit<GradeComponentScore, 'id' | 'percentage'>[];
  term_id?: number;
}

export interface GradeRecordUpdate {
  components?: Array<Omit<GradeComponentScore, 'id' | 'percentage'> & { id?: number }>;
  status?: 'draft' | 'pending' | 'approved' | 'published';
}

export interface GradeRecordPage {
  items: GradeRecord[];
  total: number;
  page: number;
  size: number;
}

export interface Curriculum {
  id: number;
  name: string;
  code: string;
  description: string | null;
  academic_year_id: number;
  status: 'draft' | 'published' | 'archived';
  created_at: string;
  updated_at: string;
  campus_id: number | null;
  subjects?: CurriculumSubject[];
}

export interface CurriculumSubject {
  id: number;
  curriculum_id: number;
  subject_id: number;
  subject_name: string;
  credits: number;
  duration_hours: number;
  semester_order: number;
  status: 'active' | 'inactive';
}

export interface CurriculumCreate {
  name: string;
  code: string;
  academic_year_id: number;
  description?: string;
  subjects?: Omit<CurriculumSubject, 'id' | 'curriculum_id'>[];
}

export interface CurriculumUpdate {
  name?: string;
  code?: string;
  description?: string;
  status?: 'draft' | 'published' | 'archived';
  subjects?: Array<Omit<CurriculumSubject, 'id' | 'curriculum_id'> & { id?: number; status?: 'active' | 'inactive' }>;
}

export interface CurriculumPage {
  items: Curriculum[];
  total: number;
  page: number;
  size: number;
}