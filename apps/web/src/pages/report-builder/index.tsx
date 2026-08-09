import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { reportDefinitionApi } from '../../api/report-builder/report-builder-api'
import { PageHeader, Card, Button, Loading, ErrorState } from '../../components/ui'

export function ReportBuilderPage() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<string[]>([])
  const [definitions, setDefinitions] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // P16 — retry must refetch, not reload the page.
  const loadPage = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cats, defs] = await Promise.all([
        reportDefinitionApi.categories(),
        reportDefinitionApi.list(),
      ])
      setCategories(cats)
      const countMap: Record<string, number> = {}
      for (const d of defs) {
        countMap[d.category] = (countMap[d.category] || 0) + 1
      }
      setDefinitions(countMap)
    } catch (err: any) {
      setError(err?.detail || 'Failed to load report categories')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadPage() }, [loadPage])

  if (loading) return <Loading text="Loading report builder..." />
  if (error) return <ErrorState message={error} onRetry={loadPage} />

  const categoryIcons: Record<string, string> = {
    Attendance: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01',
    Fees: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    Academic: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    Analytics: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  }

  const categoryColors: Record<string, string> = {
    Attendance: 'from-emerald-500 to-emerald-600',
    Fees: 'from-blue-500 to-blue-600',
    Academic: 'from-violet-500 to-violet-600',
    Analytics: 'from-amber-500 to-amber-600',
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Report Builder"
        subtitle="Create, run, and save custom reports"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder/saved')}>
              Saved Reports
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/reports/builder/exports')}>
              Export Jobs
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.map((cat, i) => (
          <Card
            key={cat}
            className="cursor-pointer group hover:shadow-lg hover:-translate-y-1 transition-all duration-[var(--motion-base)] ease-[var(--ease-standard)] overflow-hidden"
            onClick={() => navigate(`/reports/builder/new?category=${encodeURIComponent(cat)}`)}
            style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'both' }}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br ${categoryColors[cat] || 'from-gray-500 to-gray-600'} text-white shadow-sm flex-shrink-0 group-hover:scale-110 group-hover:shadow-md transition-all duration-[var(--motion-fast)] ease-[var(--ease-spring)]`}
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={categoryIcons[cat] || 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4'} />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-brand-accent)] transition-colors duration-[var(--motion-fast)]">
                  {cat}
                </h3>
                <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
                  {definitions[cat] || 0} report{definitions[cat] !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card
          className="cursor-pointer group hover:shadow-lg transition-all duration-[var(--motion-base)]"
          onClick={() => navigate('/reports/builder/saved')}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-brand-accent-subtle)] text-[var(--color-brand-accent)] flex-shrink-0">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Saved Reports</h3>
              <p className="text-xs text-[var(--color-text-tertiary)]">View your saved report configurations</p>
            </div>
          </div>
        </Card>
        <Card
          className="cursor-pointer group hover:shadow-lg transition-all duration-[var(--motion-base)]"
          onClick={() => navigate('/reports/builder/exports')}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--color-success-light)] text-[var(--color-success-dark)] flex-shrink-0">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Export Jobs</h3>
              <p className="text-xs text-[var(--color-text-tertiary)]">Track and download your report exports</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default ReportBuilderPage
