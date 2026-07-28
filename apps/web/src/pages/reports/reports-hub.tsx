import { useNavigate } from 'react-router-dom'
import { Card } from '../../components/ui'

export function ReportsHubPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
          <p className="text-gray-500 mt-1">View attendance and fee reports</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/reports/attendance')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Attendance Report</p>
            <p className="text-sm text-gray-500 mt-1">View attendance summary by class or section</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/reports/fees/collection')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Fee Collection Report</p>
            <p className="text-sm text-gray-500 mt-1">Fee collection summary by class</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/reports/fees/outstanding')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Outstanding Report</p>
            <p className="text-sm text-gray-500 mt-1">View students with outstanding fees</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/reports/receipts')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Receipt Lookup</p>
            <p className="text-sm text-gray-500 mt-1">Look up a payment receipt</p>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default ReportsHubPage