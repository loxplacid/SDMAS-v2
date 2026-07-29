import { useNavigate } from 'react-router-dom'
import { PageHeader, Card } from '../../components/ui'

const academicLinks = [
  { path: '/academic/years', label: 'Academic Years', description: 'Manage academic years and sessions', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4', color: 'from-blue-500 to-blue-600' },
  { path: '/academic/classes', label: 'Classes', description: 'Configure classes for each academic year', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4', color: 'from-emerald-500 to-emerald-600' },
  { path: '/academic/sections', label: 'Sections', description: 'Manage sections within classes', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16', color: 'from-purple-500 to-purple-600' },
  { path: '/academic/enrollments', label: 'Enrollments', description: 'Manage student class enrollments', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', color: 'from-amber-500 to-amber-600' },
  { path: '/academic/terms', label: 'Terms', description: 'Configure academic terms', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z', color: 'from-rose-500 to-rose-600' },
  { path: '/academic/assignments', label: 'Teacher Assignments', description: 'Assign teachers to classes and subjects', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z', color: 'from-cyan-500 to-cyan-600' },
]

export function AcademicPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader title="Academic Management" subtitle="Manage school academic structure and assignments" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {academicLinks.map((link, i) => (
          <Card
            key={link.path}
            className="cursor-pointer group hover:shadow-lg hover:-translate-y-1 transition-all duration-[var(--motion-base)] ease-[var(--ease-standard)] overflow-hidden"
            onClick={() => navigate(link.path)}
            style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
          >
            <div className="flex items-start gap-4">
              <div className={`flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br ${link.color} text-white shadow-sm flex-shrink-0 group-hover:scale-110 group-hover:shadow-md transition-all duration-[var(--motion-fast)] ease-[var(--ease-spring)]`}>
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={link.icon} />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-brand-accent)] transition-colors duration-[var(--motion-fast)]">{link.label}</h3>
                <p className="text-sm text-[var(--color-text-muted)] mt-0.5 leading-relaxed">{link.description}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

export default AcademicPage

// Re-export sub-pages
import { AcademicYearListPage } from './academic-year-list'
import { AcademicYearDetailPage } from './academic-year-detail'
import { ClassListPage } from './class-list'
import { SectionListPage } from './section-list'
import { EnrollmentListPage } from './enrollment-list'
import { TermListPage } from './term-list'
import { TeacherAssignmentListPage } from './teacher-assignment-list'

export { AcademicYearListPage, AcademicYearDetailPage, ClassListPage, SectionListPage, EnrollmentListPage, TermListPage, TeacherAssignmentListPage }
