import { HubPage } from '../../components/ui/hub-page'

const operationLinks = [
  { label: 'Export Students', description: 'Export student data to CSV', route: '/operations/export/students', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' },
  { label: 'Export Attendance', description: 'Export attendance records to CSV', route: '/operations/export/attendance', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' },
  { label: 'Export Payments', description: 'Export payment records to CSV', route: '/operations/export/payments', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' },
  { label: 'Academic Rollover', description: 'Roll over to the next academic year', route: '/operations/rollover', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
  { label: 'Batch Enrollment', description: 'Enroll multiple students at once', route: '/operations/batch/enroll', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z' },
  { label: 'Batch Fee Dues', description: 'Create fee dues for multiple students', route: '/operations/batch/fee-dues', icon: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z' },
]

export function OperationsHubPage() {
  return (
    <HubPage
      eyebrow="System"
      title="Data Operations"
      subtitle="Export data, run batch operations, and manage academic rollover"
      stats={[]}
      links={operationLinks}
    />
  )
}

export default OperationsHubPage
