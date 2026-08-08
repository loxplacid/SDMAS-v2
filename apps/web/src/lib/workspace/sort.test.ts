import { describe, expect, it } from 'vitest'
import { applySort, cycleSort, sortFromQueryString, sortToQueryString } from './sort'
import type { Column } from '../../components/ui/table'

interface PersonRow {
  id: number
  name: string
  amount: number
  joined: string
  status: string | null
  owner: { name: string } | null
}

const rows: PersonRow[] = [
  { id: 1, name: 'Zainab', amount: 5000, joined: '2026-03-01', status: 'Paid', owner: { name: 'Ali Yusuf' } },
  { id: 2, name: 'Bello', amount: 12000, joined: '2026-01-15', status: null, owner: { name: 'Chidi' } },
  { id: 3, name: 'Amina', amount: 8000, joined: '2026-02-10', status: 'Due', owner: { name: 'bello musa' } },
  { id: 4, name: 'Chidi', amount: 2500, joined: '', status: 'Overdue', owner: { name: 'Zainab Ali' } },
]

const columns: Column<PersonRow>[] = [
  { key: 'name', header: 'Name', type: 'text' },
  { key: 'amount', header: 'Amount', type: 'amount' },
  { key: 'joined', header: 'Joined', type: 'date' },
  { key: 'status', header: 'Status', type: 'status' },
  { key: 'owner', header: 'Owner', type: 'person' },
]

const ids = (result: PersonRow[]) => result.map((r) => r.id)

describe('applySort (P8 — multi-column sort engine)', () => {
  it('sorts text ascending and descending', () => {
    expect(ids(applySort(rows, [{ key: 'name', direction: 'asc' }], columns))).toEqual([3, 2, 4, 1])
    expect(ids(applySort(rows, [{ key: 'name', direction: 'desc' }], columns))).toEqual([1, 4, 2, 3])
  })

  it('sorts numeric/amount columns numerically, never lexically', () => {
    expect(ids(applySort(rows, [{ key: 'amount', direction: 'asc' }], columns))).toEqual([4, 1, 3, 2])
    expect(ids(applySort(rows, [{ key: 'amount', direction: 'desc' }], columns))).toEqual([2, 3, 1, 4])
  })

  it('sorts date columns chronologically', () => {
    // id 4 has an empty date → sorts last
    expect(ids(applySort(rows, [{ key: 'joined', direction: 'asc' }], columns))).toEqual([2, 3, 1, 4])
  })

  it('sorts person objects by their name (case-insensitive)', () => {
    // 'ali yusuf' < 'bello musa' < 'chidi' < 'zainab ali' — ids 1, 3, 2, 4
    expect(ids(applySort(rows, [{ key: 'owner', direction: 'asc' }], columns))).toEqual([1, 3, 2, 4])
  })

  it('keeps null/empty values last in BOTH directions', () => {
    expect(ids(applySort(rows, [{ key: 'status', direction: 'asc' }], columns))).toEqual([3, 4, 1, 2])
    expect(ids(applySort(rows, [{ key: 'status', direction: 'desc' }], columns))).toEqual([1, 4, 3, 2])
  })

  it('applies multiple rules in order (primary then secondary)', () => {
    // status asc (null last), then name asc within each bucket
    const sorted = applySort(
      rows,
      [
        { key: 'status', direction: 'asc' },
        { key: 'name', direction: 'asc' },
      ],
      columns
    )
    expect(ids(sorted)).toEqual([3, 4, 1, 2])
  })

  it('returns a copy and leaves the input untouched', () => {
    const before = rows.map((r) => r.id)
    applySort(rows, [{ key: 'amount', direction: 'desc' }], columns)
    expect(rows.map((r) => r.id)).toEqual(before)
  })

  it('is a no-op without rules and with unknown keys', () => {
    expect(ids(applySort(rows, [], columns))).toEqual([1, 2, 3, 4])
    expect(ids(applySort(rows, [{ key: 'ghost', direction: 'asc' }], columns))).toEqual([1, 2, 3, 4])
  })
})

describe('cycleSort (P8 — header-click contract)', () => {
  it('cycles: none → asc → desc → remove', () => {
    let rules = cycleSort([], 'name', false)
    expect(rules).toEqual([{ key: 'name', direction: 'asc' }])
    rules = cycleSort(rules, 'name', false)
    expect(rules).toEqual([{ key: 'name', direction: 'desc' }])
    rules = cycleSort(rules, 'name', false)
    expect(rules).toEqual([])
  })

  it('replaces the primary rule when clicking another column (non-multi)', () => {
    const rules = cycleSort([{ key: 'name', direction: 'asc' }], 'amount', false)
    expect(rules).toEqual([{ key: 'amount', direction: 'asc' }])
  })

  it('adds a secondary rule with Shift-click and toggles its direction', () => {
    let rules = cycleSort([{ key: 'name', direction: 'asc' }], 'amount', true)
    expect(rules).toEqual([
      { key: 'name', direction: 'asc' },
      { key: 'amount', direction: 'asc' },
    ])
    rules = cycleSort(rules, 'amount', true)
    expect(rules[1]).toEqual({ key: 'amount', direction: 'desc' })
    // secondary click on the PRIMARY with multi keeps the ordering
    rules = cycleSort(rules, 'name', true)
    expect(rules[0]).toEqual({ key: 'name', direction: 'desc' })
    expect(rules[1]).toEqual({ key: 'amount', direction: 'desc' })
  })
})

describe('sort serialization (P8 — URL + saved views)', () => {
  it('round-trips rules through the query string', () => {
    const rules = [
      { key: 'status', direction: 'asc' as const },
      { key: 'amount', direction: 'desc' as const },
    ]
    expect(sortToQueryString(rules)).toBe('status:asc,amount:desc')
    expect(sortFromQueryString(sortToQueryString(rules))).toEqual(rules)
  })

  it('ignores malformed segments and empty input', () => {
    expect(sortFromQueryString(null)).toEqual([])
    expect(sortFromQueryString('')).toEqual([])
    expect(sortFromQueryString('name:asc,broken,amount:sideways')).toEqual([
      { key: 'name', direction: 'asc' },
    ])
  })
})
