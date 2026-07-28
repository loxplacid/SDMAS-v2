import { useNavigate } from 'react-router-dom'
import { Card } from '../../components/ui'

export function AnalyticsHubPage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="text-gray-500 mt-1">School performance analytics and insights</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/analytics/attendance')}>
          <div className="text-center py-6">
            <div className="mx-auto w-12 h-12 bg-green-50 rounded-lg flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <p className="text-lg font-semibold">Attendance Analytics</p>
            <p className="text-sm text-gray-500 mt-1">Trends, class comparison, low attendance alerts</p>
          </div>
        </Card>

        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/analytics/finance')}>
          <div className="text-center py-6">
            <div className="mx-auto w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-lg font-semibold">Financial Analytics</p>
            <p className="text-sm text-gray-500 mt-1">Fee overview, collection trends, payment methods</p>
          </div>
        </Card>

        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/analytics/students')}>
          <div className="text-center py-6">
            <div className="mx-auto w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <p className="text-lg font-semibold">Student Analytics</p>
            <p className="text-sm text-gray-500 mt-1">Distribution, enrollment trends, demographics</p>
          </div>
        </Card>

        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/analytics/academic')}>
          <div className="text-center py-6">
            <div className="mx-auto w-12 h-12 bg-indigo-50 rounded-lg flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <p className="text-lg font-semibold">Academic Analytics</p>
            <p className="text-sm text-gray-500 mt-1">Teachers, subjects, academic structure</p>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default AnalyticsHubPage
