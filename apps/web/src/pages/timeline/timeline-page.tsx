import { BreadcrumbBar, PageHeader } from '../../components/ui'
import { Timeline } from '../../components/timeline/timeline'

export function TimelinePage() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <BreadcrumbBar />

      <div className="flex items-center justify-between gap-4">
        <PageHeader
          title="Operational Timeline"
          subtitle="Unified activity across the school — audit, approvals, payments, enrollments, admissions & risk"
        />
      </div>

      <Timeline />
    </div>
  )
}

export default TimelinePage
