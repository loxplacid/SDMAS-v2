export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface UserCreate {
  email: string
  username: string
  password: string
  display_name: string
}

export interface UserLogin {
  login: string
  password: string
}

export interface UserResponse {
  id: number
  email: string
  username: string
  display_name: string
  role: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserUpdate {
  display_name?: string | null
  email?: string | null
}

export interface AdminUserUpdate {
  display_name?: string | null
  email?: string | null
  role?: string | null
  is_active?: boolean | null
}

export interface PasswordChange {
  current_password: string
  new_password: string
}

export interface StudentCreate {
  first_name: string
  last_name: string
  student_number: string
  email?: string | null
  date_of_birth?: string | null
}

export interface StudentResponse {
  id: number
  first_name: string
  last_name: string
  student_number: string
  email: string | null
  date_of_birth: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface StudentUpdate {
  first_name?: string | null
  last_name?: string | null
  email?: string | null
  status?: string | null
  date_of_birth?: string | null
}

export interface AcademicYearCreate {
  name: string
  start_date: string
  end_date: string
}

export interface AcademicYearResponse {
  id: number
  name: string
  start_date: string
  end_date: string
  status: string
  created_at: string
  updated_at: string
}

export interface AcademicYearUpdate {
  name?: string | null
  start_date?: string | null
  end_date?: string | null
  status?: string | null
}

export interface ClassCreate {
  name: string
  academic_year_id: number
}

export interface ClassResponse {
  id: number
  name: string
  academic_year_id: number
  status: string
  created_at: string
  updated_at: string
}

export interface ClassUpdate {
  name?: string | null
  academic_year_id?: number | null
  status?: string | null
}

export interface SectionCreate {
  name: string
  class_id: number
}

export interface SectionResponse {
  id: number
  name: string
  class_id: number
  status: string
  created_at: string
  updated_at: string
}

export interface SectionUpdate {
  name?: string | null
  class_id?: number | null
  status?: string | null
}

export interface EnrollmentCreate {
  student_id: number
  academic_year_id: number
  class_id?: number | null
  section_id?: number | null
}

export interface EnrollmentResponse {
  id: number
  student_id: number
  academic_year_id: number
  class_id: number | null
  section_id: number | null
  status: string
  enrolled_at: string
  created_at: string
  updated_at: string
}

export interface EnrollmentUpdate {
  class_id?: number | null
  section_id?: number | null
  status?: string | null
}

export interface TermCreate {
  name: string
  start_date: string
  end_date: string
}

export interface TermResponse {
  id: number
  academic_year_id: number
  name: string
  start_date: string
  end_date: string
  status: string
  created_at: string
  updated_at: string
}

export interface TermUpdate {
  name?: string | null
  start_date?: string | null
  end_date?: string | null
  status?: string | null
}

export interface SubjectCreate {
  name: string
  code: string
  description?: string | null
}

export interface SubjectResponse {
  id: number
  name: string
  code: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface SubjectUpdate {
  name?: string | null
  code?: string | null
  description?: string | null
  status?: string | null
}

export interface TeacherCreate {
  first_name: string
  last_name: string
  employee_number: string
  email?: string | null
}

export interface TeacherResponse {
  id: number
  first_name: string
  last_name: string
  employee_number: string
  email: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface TeacherUpdate {
  first_name?: string | null
  last_name?: string | null
  email?: string | null
  status?: string | null
}

export interface TeacherAssignmentCreate {
  teacher_id: number
  class_id: number
  subject_id?: number | null
}

export interface TeacherAssignmentResponse {
  id: number
  teacher_id: number
  class_id: number
  subject_id: number | null
  status: string
  created_at: string
  updated_at: string
}

export interface AttendanceRecordCreate {
  student_id: number
  academic_year_id: number
  class_id: number
  section_id: number
  attendance_date: string
  status: string
  notes?: string | null
}

export interface AttendanceRecordResponse {
  id: number
  student_id: number
  academic_year_id: number
  class_id: number
  section_id: number
  attendance_date: string
  status: string
  notes: string | null
  recorded_at: string
  updated_at: string
}

export interface AttendanceRecordUpdate {
  status?: string | null
  notes?: string | null
}

export interface DailyAttendanceItem {
  student_id: number
  status: string
  notes?: string | null
}

export interface DailyAttendanceCreate {
  section_id: number
  attendance_date: string
  records: DailyAttendanceItem[]
}

export interface StudentAttendanceSummary {
  student_id: number
  start_date: string
  end_date: string
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface SectionAttendanceSummary {
  section_id: number
  attendance_date: string
  total_students: number
  total_marked: number
  present: number
  absent: number
  late: number
  excused: number
  present_percentage: number
}

export interface FeeTypeCreate {
  name: string
  description?: string | null
}

export interface FeeTypeResponse {
  id: number
  name: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface FeeTypeUpdate {
  name?: string | null
  description?: string | null
  status?: string | null
}

export interface FeeStructureCreate {
  academic_year_id: number
  class_id: number
  fee_type_id: number
  amount: number
  frequency?: string
}

export interface FeeStructureResponse {
  id: number
  academic_year_id: number
  class_id: number
  fee_type_id: number
  amount: number
  frequency: string
  status: string
  created_at: string
  updated_at: string
}

export interface FeeStructureUpdate {
  academic_year_id?: number | null
  class_id?: number | null
  fee_type_id?: number | null
  amount?: number | null
  frequency?: string | null
  status?: string | null
}

export interface FeeDueResponse {
  id: number
  student_id: number
  academic_year_id: number
  fee_structure_id: number
  original_amount: number
  amount_paid: number
  due_date: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface PaymentCreate {
  student_id: number
  fee_due_id: number
  amount: number
  payment_date?: string | null
  payment_method?: string | null
  receipt_number?: string | null
}

export interface PaymentResponse {
  id: number
  student_id: number
  fee_due_id: number
  amount: number
  payment_date: string | null
  payment_method: string | null
  receipt_number: string | null
  created_at: string
}

export interface PaymentResult {
  payment: PaymentResponse
  fee_due: FeeDueResponse
}

export interface StudentFinancialSummary {
  student_id: number
  academic_year_id: number
  total_fees_assigned: number
  total_paid: number
  total_outstanding: number
  unpaid_count: number
  partially_paid_count: number
  paid_count: number
}

export interface ClassFinancialSummary {
  class_id: number
  academic_year_id: number
  total_students: number
  total_fees_assigned: number
  total_collected: number
  total_outstanding: number
  students_with_outstanding: number
}

export interface HealthResponse {
  status: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ValidationError {
  loc: (string | number)[]
  msg: string
  type: string
  input?: unknown
  ctx?: Record<string, unknown>
}

export interface HTTPValidationError {
  detail?: ValidationError[]
}

export type ApiError = {
  status: number
  detail?: string
  validation_errors?: ValidationError[]
}