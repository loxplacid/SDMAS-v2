import { Link } from 'react-router-dom'
import { Card, PageHeader } from '../../components/ui'

const financeLinks = [
  { path: '/school-finance/dashboard', label: 'Dashboard', description: 'Real-time finance KPIs, collection rates, and outstanding balances', icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z', color: 'from-indigo-500 to-indigo-600' },
  { path: '/school-finance/fee-schedules', label: 'Fee Schedules', description: 'Manage fee structures and schedules', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01', color: 'from-emerald-500 to-emerald-600' },
  { path: '/school-finance/reconciliation', label: 'Reconciliation', description: 'Verify and approve financial reconciliations', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z', color: 'from-amber-500 to-amber-600' },
  { path: '/school-finance/receipts', label: 'Receipts', description: 'Generate and manage payment receipts', icon: 'M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z', color: 'from-violet-500 to-violet-600' },
  { path: '/school-finance/transactions', label: 'Transactions', description: 'View and filter transaction logs', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z', color: 'from-blue-500 to-blue-600' },
  { path: '/school-finance/outstanding-balances', label: 'Outstanding Balances', description: 'Student fee balances and collection tracking', icon: 'M12 1l3.904 7.944L24 9.75l-6 5.849 1.416 8.256L12 20.5l-7.416 3.896L6 15.599 0 9.75l8.096-1.806L12 1z', color: 'from-rose-500 to-rose-600' },
  { path: '/school-finance/reports', label: 'Finance Reports', description: 'Generate and download financial reports', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: 'from-cyan-500 to-cyan-600' },
]

export function SchoolFinancePage() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader title="School Finance" subtitle="Financial management, fee collection, reconciliation, and reporting" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {financeLinks.map((link, i) => (
          <Link key={link.path} to={link.path}>
            <Card
              className="cursor-pointer group hover:shadow-lg hover:-translate-y-1 transition-all duration-[var(--motion-base)] ease-[var(--ease-standard)] overflow-hidden"
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
          </Link>
        ))}
      </div>
    </div>
  )
}

export default SchoolFinancePage
