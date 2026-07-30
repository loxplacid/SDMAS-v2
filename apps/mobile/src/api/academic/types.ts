/** Analytics/overview API types — matches the actual backend AnalyticsOverview schema. */

export interface OverviewResponse {
  total_students: number;
  active_students: number;
  inactive_students: number;
  current_academic_year?: string;
  total_classes: number;
  total_sections: number;
  total_teachers: number;
  total_subjects: number;
  overall_attendance_percentage: number;
  total_collected: number;
  total_outstanding: number;
  collection_percentage: number;
  low_attendance_count: number;
  unpaid_count: number;
  partially_paid_count: number;
}

/** Academic year for mobile pickers. */
export interface AcademicYearResponse {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
}

/** Class response for mobile pickers. */
export interface ClassResponse {
  id: number;
  name: string;
  academic_year_id: number;
  status: string;
}
