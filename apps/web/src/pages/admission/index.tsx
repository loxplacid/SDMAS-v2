import { useNavigate } from 'react-router-dom'
import { PageHeader, Card } from '../../components/ui'

const admissionLinks = [
  {
    path: '/admissions/applications',
    label: 'Applications',
    description: 'View and manage all admission applications through the workflow pipeline',
    icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    color: 'from-blue-500 to-blue-600',
  },
  {
    path: '/admissions/new',
    label: 'New Inquiry',
    description: 'Capture a new admission inquiry — the first step of the admissions workflow',
    icon: 'M12 4v16m8-8H4',
    color: 'from-emerald-500 to-emerald-600',
  },
  {
    path: '/admissions/merit-list',
    label: 'Merit List',
    description: 'View ranked merit lists by program and academic year',
    icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    color: 'from-amber-500 to-amber-600',
  },
]

export function AdmissionsPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admissions"
        subtitle="Manage the complete admissions lifecycle from inquiry to enrollment"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {admissionLinks.map((link, i) => (
          <Card
            key={link.path}
            className="cursor-pointer group hover:shadow-lg hover:-translate-y-1 transition-all duration-[var(--motion-base)] ease-[var(--ease-standard)] overflow-hidden"
            onClick={() => navigate(link.path)}
            style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br ${link.color} text-white shadow-sm flex-shrink-0 group-hover:scale-110 group-hover:shadow-md transition-all duration-[var(--motion-fast)] ease-[var(--ease-spring)]`}
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={link.icon} />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-brand-accent)] transition-colors duration-[var(--motion-fast)]">
                  {link.label}
                </h3>
                <p className="text-sm text-[var(--color-text-muted)] mt-0.5 leading-relaxed">
                  {link.description}
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Workflow diagram */}
      <Card className="mt-8">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Admission Workflow</h3>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {[
            'Inquiry',
            'Application',
            'Documents',
            'Verification',
            'Interview',
            'Merit List',
            'Seat Alloc.',
            'Fee Payment',
            'Enrollment',
            'Student',
          ].map((step, i) => (
            <div key={step} className="flex items-center gap-1.5">
              <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-[var(--color-brand-accent-light)] text-[var(--color-brand-accent)] font-medium whitespace-nowrap">
                {step}
              </span>
              {i < 9 && (
                <svg className="h-4 w-4 text-[var(--color-text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

export default AdmissionsPage
