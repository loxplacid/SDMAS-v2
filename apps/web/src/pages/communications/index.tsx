import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { statsApi, metaApi } from '../../api/communications/communications-api'
import { PageHeader, Card, Button, Loading, ErrorState } from '../../components/ui'

export function CommunicationsHubPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<any>(null)
  const [types, setTypes] = useState<string[]>([])
  const [channels, setChannels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      statsApi.get(),
      metaApi.messageTypes(),
      metaApi.channels(),
    ])
      .then(([s, t, c]) => {
        setStats(s)
        setTypes(t)
        setChannels(c)
      })
      .catch((err: any) => setError(err?.detail || 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading Communications Hub..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  const typeIcons: Record<string, string> = {
    announcement: 'M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z',
    targeted: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
    class: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    section: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
    parent: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z',
    teacher: 'M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z M12 14l2.5 1.5v3L12 20l-2.5-1.5v-3L12 14z',
    staff: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Communications"
        subtitle="Create and manage school-wide communications"
        actions={
          <div className="flex gap-2">
            <Button size="sm" onClick={() => navigate('/communications/compose')}>
              New Message
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/communications/templates')}>
              Templates
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/communications/sent')}>
              Sent Messages
            </Button>
          </div>
        }
      />

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="text-center">
            <p className="text-3xl font-bold text-[var(--color-brand-accent)]">{stats.total_sent}</p>
            <p className="text-sm text-[var(--color-text-tertiary)]">Total Sent</p>
          </Card>
          <Card className="text-center">
            <p className="text-3xl font-bold text-[var(--color-success-dark)]">{stats.total_delivered}</p>
            <p className="text-sm text-[var(--color-text-tertiary)]">Delivered</p>
          </Card>
          <Card className="text-center">
            <p className="text-3xl font-bold text-[var(--color-danger)]">{stats.total_failed}</p>
            <p className="text-sm text-[var(--color-text-tertiary)]">Failed</p>
          </Card>
          <Card className="text-center">
            <p className="text-3xl font-bold text-[var(--color-text-primary)]">{stats.total_read}</p>
            <p className="text-sm text-[var(--color-text-tertiary)]">Read</p>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {types.map((type, i) => (
          <Card
            key={type}
            className="cursor-pointer group hover:shadow-lg hover:-translate-y-1 transition-all duration-[var(--motion-base)]"
            onClick={() => navigate(`/communications/compose?type=${encodeURIComponent(type)}`)}
            style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
          >
            <div className="flex items-start gap-4">
              <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 text-white shadow-sm flex-shrink-0 group-hover:scale-110 transition-all">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={typeIcons[type] || 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'} />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)] capitalize group-hover:text-[var(--color-brand-accent)] transition-colors">
                  {type.replace(/_/g, ' ')}
                </h3>
                <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
                  {stats?.by_type?.[type] || 0} messages sent
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card
          className="cursor-pointer group hover:shadow-lg transition-all"
          onClick={() => navigate('/communications/compose')}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)] flex-shrink-0">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">New Message</h3>
              <p className="text-xs text-[var(--color-text-tertiary)]">Compose and send a message</p>
            </div>
          </div>
        </Card>
        <Card
          className="cursor-pointer group hover:shadow-lg transition-all"
          onClick={() => navigate('/communications/templates')}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-warning-light)] text-[var(--color-warning-dark)] flex-shrink-0">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Templates</h3>
              <p className="text-xs text-[var(--color-text-tertiary)]">Manage reusable message templates</p>
            </div>
          </div>
        </Card>
        <Card
          className="cursor-pointer group hover:shadow-lg transition-all"
          onClick={() => navigate('/communications/sent')}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-success-light)] text-[var(--color-success-dark)] flex-shrink-0">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Sent Messages</h3>
              <p className="text-xs text-[var(--color-text-tertiary)]">Track delivery and view history</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default CommunicationsHubPage
