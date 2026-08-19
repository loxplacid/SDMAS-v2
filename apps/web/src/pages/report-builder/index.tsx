import { HubPage } from '../../components/ui/hub-page'

const builderLinks = [
  { label: 'Create Report', description: 'Build a new custom report from scratch', route: '/reports/builder/new', icon: 'M12 4v16m8-8H4' },
  { label: 'Saved Reports', description: 'View and run your saved report definitions', route: '/reports/builder/saved', icon: 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4' },
  { label: 'Export Jobs', description: 'View status of report export jobs', route: '/reports/builder/exports', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' },
]

export function ReportBuilderPage() {
  return (
    <HubPage
      eyebrow="Reporting"
      title="Report Builder"
      subtitle="Create, run, and save custom reports"
      stats={[]}
      links={builderLinks}
    />
  )
}

export default ReportBuilderPage
