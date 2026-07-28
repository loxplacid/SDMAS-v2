export interface AnalyticsOverview {
  total_students: number
  active_students: number
  inactive_students: number
  current_academic_year: string | null
  total_classes: number
  total_sections: number
  total_teachers: number
  total_subjects: number
  overall_attendance_percentage: number
  total_collected: number
  total_outstanding: number
  collection_percentage: number
  low_attendance_count: number
  unpaid_count: number
  partially_paid_count: number
}

export interface AttendanceOverview {
  total_records: number
  present: number
  absent: number
  late: number
  excused: number
  attendance_percentage: number
}

export interface AttendanceTrendPoint {
  date: string
  present: number
  absent: number
  late: number
  excused: number
  total: number
}

export interface AttendanceTrend {
  trend: AttendanceTrendPoint[]
  granularity: string
}

export interface ClassAttendanceComparison {
  class_id: number
  class_name: string
  total_records: number
  present: number
  absent: number
  late: number
  excused: number
  attendance_percentage: number
}

export interface SectionAttendanceComparison {
  section_id: number
  section_name: string
  class_name: string
  total_records: number
  present: number
  absent: number
  late: number
  excused: number
  attendance_percentage: number
}

export interface LowAttendanceStudent {
  student_id: number
  student_name: string
  student_number: string
  total_records: number
  present_count: number
  attendance_percentage: number
  threshold: number
}

export interface TermAttendanceAnalytics {
  term_id: number
  term_name: string
  total_records: number
  present: number
  absent: number
  late: number
  excused: number
  attendance_percentage: number
}

export interface FinanceOverview {
  total_fees_amount: number
  total_collected: number
  total_outstanding: number
  collection_percentage: number
  students_with_outstanding: number
  fully_paid_students: number
  partially_paid_students: number
  unpaid_students: number
}

export interface CollectionTrendPoint {
  date: string
  amount: number
  count: number
}

export interface CollectionTrend {
  trend: CollectionTrendPoint[]
  granularity: string
}

export interface FeeTypeCollection {
  fee_type_id: number
  fee_type_name: string
  total_expected: number
  total_collected: number
  outstanding: number
  collection_percentage: number
}

export interface ClassFeeCollection {
  class_id: number
  class_name: string
  total_expected: number
  total_collected: number
  outstanding: number
  collection_percentage: number
}

export interface PaymentMethodDistribution {
  payment_method: string
  transaction_count: number
  total_amount: number
}

export interface FeeStatusDistribution {
  status: string
  count: number
  total_amount: number
}

export interface StudentOverview {
  total_students: number
  active_students: number
  inactive_students: number
}

export interface StudentsByClass {
  class_id: number
  class_name: string
  student_count: number
}

export interface StudentsBySection {
  section_id: number
  section_name: string
  class_name: string
  student_count: number
}

export interface EnrollmentTrend {
  academic_year_id: number
  academic_year_name: string
  enrollment_count: number
}

export interface AcademicOverview {
  active_academic_year: string | null
  total_classes: number
  total_sections: number
  total_teachers: number
  total_subjects: number
  total_terms: number
}

export interface TeacherWorkload {
  teacher_id: number
  teacher_name: string
  employee_number: string
  assignment_count: number
  subjects: string[]
  classes: string[]
}

export interface SubjectDistribution {
  subject_id: number
  subject_name: string
  subject_code: string
  assignment_count: number
}
