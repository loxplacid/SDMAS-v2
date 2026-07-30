/** Attendance API types. */

export interface AttendanceRecordResponse {
  id: number;
  student_id: number;
  section_id: number;
  attendance_date: string;
  status: 'present' | 'absent' | 'late' | 'excused';
  remarks?: string;
  recorded_by: number;
  created_at: string;
  updated_at: string;
}

export interface DailyAttendanceCreate {
  section_id: number;
  attendance_date: string;
  records: Array<{
    student_id: number;
    status: 'present' | 'absent' | 'late' | 'excused';
    remarks?: string;
  }>;
}

export interface SectionAttendanceSummary {
  section_id: number;
  section_name: string;
  total_students: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  attendance_percentage: number;
}

export interface StudentAttendanceSummary {
  student_id: number;
  total: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  percentage: number;
}

/** Section model for selectors. */
export interface SectionResponse {
  id: number;
  name: string;
  class_id: number;
  status: string;
}
