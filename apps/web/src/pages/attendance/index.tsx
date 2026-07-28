import { useNavigate } from 'react-router-dom'
import { Card, Button } from '../../components/ui'

export function AttendancePage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Attendance Management</h1>
          <p className="text-gray-500 mt-1">Record and manage student attendance</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/attendance/daily')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Daily Attendance</p>
            <p className="text-sm text-gray-500 mt-1">Record attendance for a section by date</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/attendance/record')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Record Attendance</p>
            <p className="text-sm text-gray-500 mt-1">Record a single attendance entry</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/attendance/records')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Attendance Records</p>
            <p className="text-sm text-gray-500 mt-1">View and search all attendance records</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/attendance/student')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Student Attendance</p>
            <p className="text-sm text-gray-500 mt-1">View attendance for a specific student</p>
          </div>
        </Card>
        <Card className="cursor-pointer hover:shadow-md" onClick={() => navigate('/attendance/section')}>
          <div className="text-center py-4">
            <p className="text-lg font-semibold">Section Attendance</p>
            <p className="text-sm text-gray-500 mt-1">View attendance for a section on a date</p>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default AttendancePage