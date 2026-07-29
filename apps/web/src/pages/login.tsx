import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../api/auth/auth-context'
import { Button, Alert } from '../components/ui'
import { getHomeRoute } from '../types/roles'

export function LoginPage() {
  const { login, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as any)?.from?.pathname || null

  const [loginValue, setLoginValue] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!loginValue.trim()) {
      setError('Enter your username or email to continue.')
      return
    }
    if (!password) {
      setError('Enter your password to continue.')
      return
    }

    try {
      const loggedInUser = await login(loginValue, password)
      // Redirect to role-specific home page or the original requested page
      const redirectTo = from || getHomeRoute(loggedInUser?.role)
      navigate(redirectTo, { replace: true })
    } catch (err: any) {
      if (err?.status === 401) {
        setError('The username or password you entered is incorrect.')
      } else if (err?.status === 403) {
        setError('Your account does not have permission to access this system.')
      } else if (err?.name === 'TypeError' || err?.message?.includes('fetch')) {
        setError('Unable to connect. Check your network connection and try again.')
      } else if (err?.detail) {
        setError(err.detail)
      } else {
        setError('Sign in failed. Please try again.')
      }
    }
  }

  return (
    <div className="min-h-screen flex bg-[var(--color-bg)]">
      {/* Brand Panel */}
      <div className="hidden lg:flex lg:w-[55%] bg-[var(--color-brand-navy)] relative overflow-hidden">
        {/* Abstract grid pattern */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
          }}
        />

        {/* Decorative gradient orbs */}
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-[var(--color-brand-accent)]/8 blur-[120px]" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full bg-[var(--color-brand-accent)]/5 blur-[100px]" />

        <div className="relative flex flex-col justify-between px-16 py-16 w-full">
          {/* Logo */}
          <div>
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center h-11 w-11 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-base shadow-lg shadow-[var(--color-brand-accent)]/20">
                S
              </div>
              <div>
                <h1 className="text-lg font-bold text-white tracking-tight">SDMAS</h1>
                <p className="text-xs text-white/40 font-medium tracking-wide uppercase">School Data Management</p>
              </div>
            </div>
          </div>

          {/* Hero */}
          <div className="max-w-lg">
            <h2 className="text-4xl font-extrabold text-white leading-[1.1] tracking-tight mb-4">
              Your school.<br />
              <span className="text-[var(--color-brand-accent)]">One operating system.</span>
            </h2>
            <p className="text-base text-white/50 leading-relaxed">
              Manage students, academics, attendance, fees, and analytics — a unified platform
              designed for modern educational institutions.
            </p>

            {/* Feature highlights */}
            <div className="mt-10 grid grid-cols-2 gap-4">
              {[
                { label: 'Student Records', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197' },
                { label: 'Attendance Tracking', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
                { label: 'Fee Management', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1' },
                { label: 'Analytics & Reports', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
              ].map((f) => (
                <div key={f.label} className="flex items-center gap-3">
                  <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-white/5">
                    <svg className="h-4.5 w-4.5 text-[var(--color-brand-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={f.icon} />
                    </svg>
                  </div>
                  <span className="text-sm text-white/60 font-medium">{f.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div>
            <p className="text-xs text-white/20">
              &copy; {new Date().getFullYear()} SDMAS. All rights reserved.
            </p>
          </div>
        </div>
      </div>

      {/* Login Panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm animate-fade-in-up">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-sm">
              S
            </div>
            <div>
              <p className="text-base font-bold text-[var(--color-text-primary)]">SDMAS</p>
              <p className="text-xs text-[var(--color-text-tertiary)]">School Management</p>
            </div>
          </div>

          {/* Welcome */}
          <h2 className="text-xl font-bold text-[var(--color-text-primary)] mb-1">
            Sign in
          </h2>
          <p className="text-sm text-[var(--color-text-tertiary)] mb-7">
            Enter your credentials to access the system.
          </p>

          {error && (
            <div className="mb-5">
              <Alert variant="error" onClose={() => setError(null)}>{error}</Alert>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="login-username" className="block text-sm font-medium text-[var(--color-text-primary)]">
                Username / Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <svg className="h-4 w-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <input
                  id="login-username"
                  type="text"
                  value={loginValue}
                  onChange={(e) => setLoginValue(e.target.value)}
                  placeholder="Enter your username"
                  required
                  autoComplete="username"
                  autoFocus
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] pl-10 pr-3.5 py-2.5 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] transition-all duration-150 focus:border-[var(--color-brand-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)]/15 hover:border-[var(--color-text-tertiary)]"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="login-password" className="block text-sm font-medium text-[var(--color-text-primary)]">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <svg className="h-4 w-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] pl-10 pr-3.5 py-2.5 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] transition-all duration-150 focus:border-[var(--color-brand-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)]/15 hover:border-[var(--color-text-tertiary)]"
                />
              </div>
            </div>

            <Button type="submit" className="w-full" size="lg" loading={isLoading}>
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
