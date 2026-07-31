import { useNavigate } from 'react-router-dom'
import { PageHeader, Card } from '../../components/ui'

const feeLinks = [
  { path: '/fees/fee-types', label: 'Fee Types', description: 'Manage fee categories', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10', color: 'from-blue-500 to-blue-600' },
  { path: '/fees/structures', label: 'Fee Structures', description: 'Configure fee amounts by class and year', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01', color: 'from-emerald-500 to-emerald-600' },
  { path: '/fees/dues', label: 'Fee Dues', description: 'View and manage student fee dues', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: 'from-amber-500 to-amber-600' },
  { path: '/fees/payments', label: 'Payments', description: 'Record and view student payments', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z', color: 'from-purple-500 to-purple-600' },
  { path: '/fees/summary', label: 'Financial Summary', description: 'View financial summaries by student or class', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', color: 'from-rose-500 to-rose-600' },
  { path: '/school-finance', label: 'Finance Platform', description: 'Payment methods, fee schedules, receipts, reconciliation, reports', icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z', color: 'from-teal-500 to-teal-600' },
]

export function FeesPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader title="Fees & Payments" subtitle="Manage fee types, structures, dues, and payment records" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {feeLinks.map((link, i) => (
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

export default FeesPage
