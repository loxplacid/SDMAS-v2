import { useNavigate } from 'react-router-dom'
import { PageHeader, Card } from '../../components/ui'

const reportLinks = [
  { path: '/reports/attendance', label: 'Attendance Report', description: 'View attendance summary by class or section', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01', color: 'from-emerald-500 to-emerald-600' },
  { path: '/reports/fees/collection', label: 'Fee Collection Report', description: 'Fee collection summary by class', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z', color: 'from-blue-500 to-blue-600' },
  { path: '/reports/fees/outstanding', label: 'Outstanding Report', description: 'View students with outstanding fees', icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z', color: 'from-rose-500 to-rose-600' },
  { path: '/reports/receipts', label: 'Receipt Lookup', description: 'Look up a payment receipt by number', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: 'from-purple-500 to-purple-600' },
  { path: '/reports/builder', label: 'Report Builder', description: 'Create, run, and save custom reports', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4', color: 'from-cyan-500 to-cyan-600' },
  { path: '/reports/cards', label: 'Report Cards & Marksheets', description: 'Generate printable report cards with grades, GPA, attendance and remarks', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: 'from-violet-500 to-violet-600' },
]

export function ReportsHubPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" subtitle="View attendance and fee reports" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {reportLinks.map((link, i) => (
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

export default ReportsHubPage
