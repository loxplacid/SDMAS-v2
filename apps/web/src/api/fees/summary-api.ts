import { api } from '../client/http-client'
import type { StudentFinancialSummary, ClassFinancialSummary } from '../generated/types'

export const summaryApi = {
  getStudentSummary: (studentId: number, academicYearId: number) =>
    api.get<StudentFinancialSummary>(`/api/fees/students/${studentId}/summary`, { academic_year_id: academicYearId }),

  getClassSummary: (classId: number, academicYearId: number) =>
    api.get<ClassFinancialSummary>(`/api/fees/classes/${classId}/summary`, { academic_year_id: academicYearId }),
}