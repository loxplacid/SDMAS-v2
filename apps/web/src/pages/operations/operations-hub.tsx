import { useNavigate } from 'react-router-dom'
import { Card } from '../../components/ui'

export function OperationsHubPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Operations</h1>
          <p className="text-gray-500 mt-1">Export data, rollover academic years, and batch operations</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/operations/export/students')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Export Students</p>
            <p className="text-sm text-gray-500 mt-1">Download student data as CSV</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/operations/export/attendance')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Export Attendance</p>
            <p className="text-sm text-gray-500 mt-1">Download attendance records as CSV</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/operations/export/payments')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Export Payments</p>
            <p className="text-sm text-gray-500 mt-1">Download payment records as CSV</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/operations/rollover')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Academic Year Rollover</p>
            <p className="text-sm text-gray-500 mt-1">Roll over to a new academic year</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/operations/batch/enroll')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Batch Enroll</p>
            <p className="text-sm text-gray-500 mt-1">Enroll multiple students at once</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/operations/batch/fee-dues')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Batch Fee Dues</p>
            <p className="text-sm text-gray-500 mt-1">Create fee dues for multiple students</p>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default OperationsHubPage