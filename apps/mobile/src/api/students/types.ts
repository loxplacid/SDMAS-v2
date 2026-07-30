/** Student API types. */

export interface StudentResponse {
  id: number;
  first_name: string;
  last_name: string;
  student_number: string;
  email?: string;
  phone?: string;
  date_of_birth?: string;
  gender?: string;
  address?: string;
  status: string;
  enrollment_date?: string;
  created_at: string;
  updated_at: string;
}

export interface StudentSummary {
  total: number;
  active: number;
  inactive: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
