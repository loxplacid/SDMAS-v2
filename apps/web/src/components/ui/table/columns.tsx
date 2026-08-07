import type { ReactNode } from 'react'
import { Badge, type BadgeVariant } from '../badge'

/**
 * SDMAS Table System v3 — the column type system (§3.1 of TABLE_SYSTEM_V3.md).
 *
 * A column's `type` is a first-class declaration that drives alignment,
 * minimum width, sorting semantics, and default rendering. The contract for
 * this module: **an untyped column renders byte-identically to the legacy
 * Table** — the type system is purely additive. Pages opt in per column.
 */

export type ColumnType =
  | 'text'
  | 'person'
  | 'numeric'
  | 'amount'
  | 'date'
  | 'status'
  | 'progress'
  | 'relation'
  | 'actions'
  | 'expander'
  | 'checkbox'

export type ColumnAlign = 'left' | 'right' | 'center'

/** §6.2 T31 — range presets are authored by the domain, never generic. */
export interface RangePreset {
  label: string
  min?: number | string
  max?: number | string
}

export interface Column<T> {
  /** Stable key; used as the React key and the default accessor. */
  key: string
  /** Header label. */
  header: string
  /** Instrument type (§3.1). Optional — untyped columns behave like legacy. */
  type?: ColumnType
  /** Explicit accessor; defaults to `item[key]` (same as legacy). */
  accessor?: (item: T) => unknown
  /** Full custom renderer — wins over any type renderer. */
  render?: (item: T) => ReactNode
  /** Overrides type-derived alignment. */
  align?: ColumnAlign
  /** Column width; applied as an inline style on the header. */
  width?: number | string
  /** Minimum width; applied as an inline style on the header. */
  minWidth?: number | string
  className?: string
  sortable?: boolean
  hideOnMobile?: boolean
  /** `status` type: maps a status value to a badge variant. */
  statusVariants?: Record<string, BadgeVariant>
  /** `amount` type: ISO currency code (default NGN). */
  currency?: string
  /** `progress` type: suffix after the percentage (default `%`). */
  progressSuffix?: string
  /**
   * §6.1 T27 — search participation. Default: `true` for text/person/
   * relation/numeric (and untyped); `false` for status/amount/date/progress.
   * Set explicitly to opt a column out of search.
   */
  searchable?: boolean
  /** §6.2 T31 — quick range presets shown in the filter panel (e.g. "this term"). */
  rangePresets?: RangePreset[]
}

/** §3.1 type → alignment. */
export const COLUMN_ALIGNMENT: Record<ColumnType, ColumnAlign> = {
  text: 'left',
  person: 'left',
  numeric: 'right',
  amount: 'right',
  date: 'left',
  status: 'left',
  progress: 'left',
  relation: 'left',
  actions: 'right',
  expander: 'left',
  checkbox: 'center',
}

/** §3.1 type → minimum width (px). Only the types with hard floors are listed. */
export const COLUMN_MIN_WIDTH: Partial<Record<ColumnType, number>> = {
  person: 180,
  numeric: 96,
  amount: 120,
  date: 120,
  status: 96,
  actions: 96,
  expander: 28,
  checkbox: 36,
}

export function resolveColumnAlign<T>(col: Column<T>): ColumnAlign {
  if (col.align) return col.align
  return col.type ? COLUMN_ALIGNMENT[col.type] : 'left'
}

export function alignmentClass(align: ColumnAlign): string {
  if (align === 'right') return 'text-right'
  if (align === 'center') return 'text-center'
  return 'text-left'
}

// ---------------------------------------------------------------------------
// value formatters
// ---------------------------------------------------------------------------

export function formatNumber(value: unknown): string {
  if (value == null || value === '') return ''
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return n.toLocaleString('en-US')
}

export function formatAmount(value: unknown, currency = 'NGN'): string {
  if (value == null || value === '') return ''
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  if (n === 0) return '-'
  try {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(n)
  } catch {
    return `${n.toLocaleString('en-US')} ${currency}`
  }
}

export function formatDateValue(value: unknown): string {
  if (value == null || value === '') return ''
  const d = value instanceof Date ? value : new Date(String(value))
  if (Number.isNaN(d.getTime())) return String(value)
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(d)
}

// ---------------------------------------------------------------------------
// type renderers
// ---------------------------------------------------------------------------

function StatusCell({ value, variants }: { value: unknown; variants?: Record<string, BadgeVariant> }) {
  if (value == null || value === '') return null
  const text = String(value)
  return <Badge variant={variants?.[text] ?? 'neutral'}>{text}</Badge>
}

function ProgressCell({ value, suffix = '%' }: { value: unknown; suffix?: string }) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return null
  const pct = Math.min(100, n)
  return (
    <span className="inline-flex items-center gap-2 min-w-[120px]">
      <span className="h-1 w-16 overflow-hidden rounded-full bg-[var(--color-surface-hover)]">
        <span
          className="block h-full rounded-full bg-[var(--color-brand-accent)]"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="text-xs text-[var(--color-text-secondary)] tabular-nums">
        {Math.round(pct)}
        {suffix}
      </span>
    </span>
  )
}

/**
 * §3.1 `person`: avatar (24px) + name. Accepts a plain name string or a
 * `{ name, avatar? }` object — the shape most person-valued domain rows use.
 */
function PersonCell({ value }: { value: unknown }) {
  const raw =
    typeof value === 'object' && value !== null && 'name' in value
      ? (value as { name: unknown }).name
      : value
  const name = typeof raw === 'string' ? raw : ''
  const avatar =
    typeof value === 'object' && value !== null && 'avatar' in value
      ? (value as { avatar: unknown }).avatar
      : undefined
  if (!name) return null
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('')
  return (
    <span className="inline-flex items-center gap-2.5 min-w-0">
      {typeof avatar === 'string' && avatar ? (
        <img src={avatar} alt="" className="h-6 w-6 shrink-0 rounded-full object-cover" />
      ) : (
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-brand-accent-subtle)] text-[10px] font-semibold text-[var(--color-brand-accent)]">
          {initials || '•'}
        </span>
      )}
      <span className="truncate">{name}</span>
    </span>
  )
}

function renderByType<T>(col: Column<T>, value: unknown): ReactNode {
  switch (col.type) {
    case 'numeric':
      return <span className="tabular-nums">{formatNumber(value)}</span>
    case 'amount':
      return <span className="tabular-nums font-medium">{formatAmount(value, col.currency)}</span>
    case 'date':
      return formatDateValue(value)
    case 'status':
      return <StatusCell value={value} variants={col.statusVariants} />
    case 'progress':
      return <ProgressCell value={value} suffix={col.progressSuffix} />
    case 'person':
      return <PersonCell value={value} />
    case 'relation':
    case 'actions':
    case 'expander':
    case 'checkbox':
    case 'text':
    default:
      return value as ReactNode
  }
}

/**
 * Resolve a cell's content. `render` wins; typed columns use their default
 * renderer; untyped columns fall back to raw `item[key]` access — exactly the
 * legacy behavior, byte for byte.
 */
export function renderCell<T>(col: Column<T>, item: T): ReactNode {
  if (col.render) return col.render(item)
  const value = col.accessor ? col.accessor(item) : (item as Record<string, unknown>)[col.key]
  if (!col.type) return value as ReactNode
  return renderByType(col, value)
}

/**
 * Whether a column carries type- or align-derived alignment. Untyped columns
 * must NOT get an alignment class — the legacy Table leaves alignment to the
 * browser default, and this module keeps untyped output byte-identical.
 */
export function hasExplicitAlignment<T>(col: Column<T>): boolean {
  return col.type !== undefined || col.align !== undefined
}
