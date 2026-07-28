import { useNavigate } from 'react-router-dom'
import { Card } from '../../components/ui'

export function AcademicPage() {
  const navigate = useNavigate()

  const sections = [
    { title: 'Academic Years', desc: 'Manage academic years and their terms', path: '/academic/years' },
    { title: 'Classes', desc: 'Manage classes within academic years', path: '/academic/classes' },
    { title: 'Sections', desc: 'Manage sections within classes', path: '/academic/sections' },
    { title: 'Enrollments', desc: 'Manage student enrollments', path: '/academic/enrollments' },
    { title: 'Terms', desc: 'Manage terms within academic years', path: '/academic/terms' },
    { title: 'Subjects', desc: 'Manage subjects offered', path: '/subjects' },
    { title: 'Teachers', desc: 'Manage teacher records', path: '/teachers' },
    { title: 'Teacher Assignments', desc: 'Assign teachers to classes and subjects', path: '/academic/assignments' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Academic Management</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sections.map((s) => (
          <Card key={s.path} title={s.title} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate(s.path)}>
            <p className="text-sm text-gray-500">{s.desc}</p>
          </Card>
        ))}
      </div>
    </div>
  )
}

export { AcademicYearListPage } from './academic-year-list'
export { AcademicYearDetailPage } from './academic-year-detail'
export { ClassListPage } from './class-list'
export { SectionListPage } from './section-list'
export { EnrollmentListPage } from './enrollment-list'
export { TermListPage } from './term-list'
export { TeacherAssignmentListPage } from './teacher-assignment-list'