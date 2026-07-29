import { useNavigate } from 'react-router-dom'
import { PageHeader, Card } from '../../components/ui'

const attendanceLinks = [
  { path: '/attendance/records', label: 'All Records', description: 'View and search attendance records', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01', color: 'from-blue-500 to-blue-600' },
  { path: '/attendance/daily', label: 'Daily Attendance', description: 'Record attendance for a section by date', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z', color: 'from-emerald-500 to-emerald-600' },
  { path: '/attendance/record', label: 'Individual Record', description: 'Record attendance for individual students', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', color: 'from-purple-500 to-purple-600' },
  { path: '/attendance/student', label: 'Student Attendance', description: 'View attendance by student', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z', color: 'from-amber-500 to-amber-600' },
  { path: '/attendance/section', label: 'Section Attendance', description: 'View attendance summary by section', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16', color: 'from-rose-500 to-rose-600' },
]

export function AttendancePage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader title="Attendance" subtitle="Manage attendance records and daily tracking" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {attendanceLinks.map((link, i) => (
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

export default AttendancePage
