/** Fee API types matching FastAPI schemas. */

export interface FeeTypeResponse {
  id: number;
  name: string;
  description?: string;
  status: string;
}

export interface FeeStructureResponse {
  id: number;
  fee_type_id: number;
  fee_type_name?: string;
  amount: number;
  academic_year_id: number;
  class_id: number;
  due_date: string;
  status: string;
}

export interface FeeDueResponse {
  id: number;
  student_id: number;
  fee_structure_id: number;
  fee_type_name?: string;
  amount: number;
  paid_amount: number;
  balance: number;
  due_date: string;
  status: 'pending' | 'partial' | 'paid' | 'overdue' | 'waived';
}

export interface PaymentCreate {
  fee_due_id: number;
  amount: number;
  payment_method: 'cash' | 'bank_transfer' | 'card' | 'cheque' | 'mobile_money';
  reference_number?: string;
  notes?: string;
}

export interface PaymentResponse {
  id: number;
  fee_due_id: number;
  student_id: number;
  amount: number;
  payment_method: string;
  receipt_number: string;
  reference_number?: string;
  notes?: string;
  payment_date: string;
  created_at: string;
}

export interface PaymentResult {
  payment: PaymentResponse;
  fee_due: FeeDueResponse;
}

export interface StudentFinancialSummary {
  total_fees: number;
  total_paid: number;
  total_balance: number;
  due_count: number;
  overdue_count: number;
}
