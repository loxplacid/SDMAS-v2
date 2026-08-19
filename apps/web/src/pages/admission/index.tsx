import { HubPage } from '../../components/ui/hub-page'

const admissionLinks = [
  { label: 'Applications', description: 'View and manage all admission applications', route: '/admissions/applications', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { label: 'New Inquiry', description: 'Capture a new admission inquiry', route: '/admissions/new', icon: 'M12 4v16m8-8H4' },
  { label: 'Merit List', description: 'View ranked merit lists by program', route: '/admissions/merit-list', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
]

export function AdmissionsPage() {
  return (
    <HubPage
      eyebrow="People"
      title="Admissions"
      subtitle="Manage the complete admissions lifecycle from inquiry to enrollment"
      stats={[]}
      links={admissionLinks}
    />
  )
}

export default AdmissionsPage
