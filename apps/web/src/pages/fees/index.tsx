import { useNavigate } from 'react-router-dom'
import { Card } from '../../components/ui'

export function FeesPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fees & Financial Management</h1>
          <p className="text-gray-500 mt-1">Manage fee types, structures, dues, payments, and financial summaries</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/fees/fee-types')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Fee Types</p>
            <p className="text-sm text-gray-500 mt-1">Manage fee type definitions</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/fees/structures')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Fee Structures</p>
            <p className="text-sm text-gray-500 mt-1">Define fee amounts by class and year</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/fees/student-fees')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Student Fees</p>
            <p className="text-sm text-gray-500 mt-1">View applicable fees and dues per student</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/fees/dues')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Fee Dues</p>
            <p className="text-sm text-gray-500 mt-1">Generate and manage fee dues</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/fees/payments')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Payments</p>
            <p className="text-sm text-gray-500 mt-1">Record and view payments</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/fees/summary')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Financial Summary</p>
            <p className="text-sm text-gray-500 mt-1">View student and class financial summaries</p>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default FeesPage