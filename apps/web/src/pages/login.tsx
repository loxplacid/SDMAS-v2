import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../api/auth/auth-context'
import { Button, Input, Alert } from '../components/ui'

export function LoginPage() {
  const { login, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const [loginValue, setLoginValue] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login(loginValue, password)
      navigate(from, { replace: true })
    } catch (err: any) {
      setError(err?.detail || 'Invalid credentials')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="w-full max-w-sm bg-white rounded-lg shadow-md p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">SDMAS</h1>
        <p className="text-sm text-gray-500 mb-6">School Management System</p>
        {error && <Alert variant="error" onClose={() => setError(null)}>{error}</Alert>}
        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <Input
            label="Username / Email"
            value={loginValue}
            onChange={(e) => setLoginValue(e.target.value)}
            placeholder="Enter your username"
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            required
          />
          <Button type="submit" className="w-full" loading={isLoading}>
            Sign in
          </Button>
        </form>
      </div>
    </div>
  )
}