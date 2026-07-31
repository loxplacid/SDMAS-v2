import { useNavigate } from 'react-router-dom'
import { PageHeader, Card } from '../../components/ui'

const intelligenceLinks = [
  { path: '/attendance-intelligence/dashboard', label: 'Intelligence Dashboard', description: 'Real-time attendance KPIs, chronic absenteeism, and alerts', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', color: 'from-indigo-500 to-indigo-600' },
  { path: '/attendance-intelligence/period', label: 'Period Attendance', description: 'Per-period attendance with late/early tracking', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', color: 'from-emerald-500 to-emerald-600' },
  { path: '/attendance-intelligence/corrections', label: 'Corrections', description: 'Attendance correction requests and approval workflow', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z', color: 'from-amber-500 to-amber-600' },
  { path: '/attendance-intelligence/thresholds', label: 'Thresholds', description: 'Configure attendance warning and critical thresholds', icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4', color: 'from-violet-500 to-violet-600' },
]

export function AttendanceIntelligencePage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader title="Attendance Intelligence" subtitle="Advanced attendance analytics, period tracking, corrections, and thresholds" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {intelligenceLinks.map((link, i) => (
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

export default AttendanceIntelligencePage
