export interface ClassAttendanceSummaryReport {
  class_id: number
  class_name: string
  academic_year_id: number
  total_students: number
  total_records: number
  present: number
  absent: number
  late: number
  excused: number
  present_percentage: number
}

export interface SectionAttendanceSummaryReport {
  section_id: number
  section_name: string
  class_id: number
  class_name: string
  total_students: number
  total_records: number
  present: number
  absent: number
  late: number
  excused: number
  present_percentage: number
}

export interface CollectionReportItem {
  class_id: number
  class_name: string
  total_students: number
  total_fees_assigned: number
  total_collected: number
  total_outstanding: number
  collection_percentage: number
}

export interface OutstandingReportItem {
  student_id: number
  student_name: string
  student_number: string
  class_name: string
  total_fees: number
  total_paid: number
  outstanding: number
  due_count: number
  unpaid_count: number
  partially_paid_count: number
}

export interface DetailedReceipt {
  payment_id: number
  receipt_number: string | null
  student_id: number
  student_name: string
  student_number: string
  fee_due_id: number
  amount: number
  payment_date: string | null
  payment_method: string | null
  academic_year_name: string
  fee_type_name: string
  created_at: string
}

export interface RolloverPreviewItem {
  type: string
  name: string
  source_id: number
}

export interface RolloverPreview {
  from_year_id: number
  from_year_name: string
  to_year_name: string
  classes: RolloverPreviewItem[]
  sections: RolloverPreviewItem[]
  enrolled_students: number
  total_items: number
}

export interface RolloverExecuteInput {
  from_year_id: number
  to_year_name: string
  to_start_date: string
  to_end_date: string
}

export interface RolloverResult {
  success: boolean
  academic_year_id: number
  academic_year_name: string
  classes_created: number
  sections_created: number
  enrollments_created: number
  message: string
}

export interface BatchEnrollItem {
  student_id: number
  class_id: number
  section_id?: number | null
}

export interface BatchEnrollInput {
  academic_year_id: number
  enrollments: BatchEnrollItem[]
}

export interface BatchEnrollResultItem {
  student_id: number
  success: boolean
  enrollment_id: number | null
  error: string | null
}

export interface BatchEnrollResult {
  academic_year_id: number
  total: number
  succeeded: number
  failed: number
  results: BatchEnrollResultItem[]
}

export interface BatchFeeDueInput {
  academic_year_id: number
  student_ids: number[]
}

export interface BatchFeeDueResultItem {
  student_id: number
  success: boolean
  dues_created: number
  error: string | null
}

export interface BatchFeeDueResult {
  academic_year_id: number
  total: number
  succeeded: number
  failed: number
  results: BatchFeeDueResultItem[]
}