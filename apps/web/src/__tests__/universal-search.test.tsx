import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import {
  tokenize,
  expandSynonyms,
  buildMatchQuery,
  correctToken,
  levenshtein,
  harvestVocabulary,
} from '../lib/search/query-pipeline'
import {
  combinedRank,
  frequencyBoost,
  recencyBoost,
  normaliseBm25,
} from '../lib/search/ranking'
import { UniversalSearchModal } from '../components/ui/universal-search-modal'

// ---------------------------------------------------------------------------
// Query pipeline
// ---------------------------------------------------------------------------

describe('tokenize', () => {
  it('splits plain tokens', () => {
    expect(tokenize('amina kante')).toEqual([
      { text: 'amina', quoted: false },
      { text: 'kante', quoted: false },
    ])
  })

  it('preserves quoted phrases (straight quotes)', () => {
    expect(tokenize('student:"Amina Kante"')).toEqual([
      { text: 'student', quoted: false },
      { text: 'Amina Kante', quoted: true },
    ])
  })

  it('preserves quoted phrases (curly smart quotes from mobile keyboards)', () => {
    expect(tokenize('student:“Amina Kante”')).toEqual([
      { text: 'student', quoted: false },
      { text: 'Amina Kante', quoted: true },
    ])
  })

  it('returns [] for empty input', () => {
    expect(tokenize('   ')).toEqual([])
  })
})

describe('expandSynonyms', () => {
  it('expands teacher to faculty family', () => {
    const family = expandSynonyms('teacher')
    expect(family).toContain('faculty')
    expect(family).toContain('instructor')
    expect(family[0]).toBe('teacher')
  })

  it('expands student to pupil', () => {
    expect(expandSynonyms('student')).toContain('pupil')
  })

  it('returns the token alone when no synonyms exist', () => {
    expect(expandSynonyms('zebra')).toEqual(['zebra'])
  })
})

describe('levenshtein', () => {
  it('handles identity and empty', () => {
    expect(levenshtein('abc', 'abc')).toBe(0)
    expect(levenshtein('', 'abc')).toBe(3)
  })

  it('measures substitutions', () => {
    expect(levenshtein('kitten', 'sitting')).toBe(3)
    expect(levenshtein('amina', 'amina')).toBe(0)
  })
})

describe('correctToken', () => {
  it('finds a near match within distance', () => {
    expect(correctToken('amin', ['amina', 'kante'])).toBe('amina')
  })

  it('rejects words too far away', () => {
    expect(correctToken('zzzzzz', ['amina'])).toBeNull()
  })
})

describe('buildMatchQuery', () => {
  it('ANDs unquoted tokens with prefix matching', () => {
    const q = buildMatchQuery('amina kante')
    expect(q).toContain('amina*')
    expect(q).toContain('kante*')
    expect(q).toContain(' AND ')
  })

  it('expands synonyms into OR groups', () => {
    const q = buildMatchQuery('teacher')
    expect(q).toMatch(/teacher\*/)
    expect(q).toMatch(/faculty\*/)
    expect(q).toMatch(/ OR /)
  })

  it('keeps quoted phrases intact', () => {
    const q = buildMatchQuery('"Amina Kante"')
    expect(q).toContain('"Amina Kante"')
    expect(q).not.toContain(' AND ')
  })

  it('falls back to typo correction when no direct match', () => {
    // 'amena' is one edit from 'amina' and has no direct prefix in the vocab.
    const vocab = ['amina', 'kante', 'student']
    const q = buildMatchQuery('amena', { vocabulary: vocab, typoDistance: 2 })
    expect(q).toContain('amina*')
  })
})

describe('harvestVocabulary', () => {
  it('collects unique terms with a cap', () => {
    const vocab = harvestVocabulary(['Amina Kante', 'Amina John'], 10)
    expect(vocab).toContain('amina')
    expect(vocab).toContain('kante')
    expect(vocab.length).toBeLessThanOrEqual(10)
  })
})

// ---------------------------------------------------------------------------
// Ranking
// ---------------------------------------------------------------------------

describe('recencyBoost', () => {
  it('is 0 without a timestamp', () => {
    expect(recencyBoost(null)).toBe(0)
  })

  it('boosts recent items and decays with age', () => {
    const now = Date.now()
    const recent = recencyBoost(new Date(now - 3 * 86_400_000).toISOString())
    const old = recencyBoost(new Date(now - 300 * 86_400_000).toISOString())
    expect(recent).toBeGreaterThan(old)
    expect(recent).toBeLessThanOrEqual(0.5)
  })
})

describe('frequencyBoost', () => {
  it('is 0 with no opens', () => {
    expect(frequencyBoost(0)).toBe(0)
  })

  it('grows with opens up to the cap', () => {
    const once = frequencyBoost(1)
    const many = frequencyBoost(100)
    expect(many).toBeGreaterThan(once)
    expect(many).toBeLessThanOrEqual(0.5)
  })
})

describe('normaliseBm25', () => {
  it('maps bm25 to [0,1]', () => {
    expect(normaliseBm25(-8)).toBe(0)
    expect(normaliseBm25(0)).toBe(1)
    const mid = normaliseBm25(-4)
    expect(mid).toBeGreaterThan(0)
    expect(mid).toBeLessThan(1)
  })
})

describe('combinedRank', () => {
  it('combines signals within [0,1]', () => {
    const rank = combinedRank(
      { id: 'student-1', bm25: -3, changedAt: new Date().toISOString() },
      5,
    )
    expect(rank).toBeGreaterThanOrEqual(0)
    expect(rank).toBeLessThanOrEqual(1)
  })

  it('frequently opened recent items outrank cold items', () => {
    const hot = combinedRank(
      { id: 'a', bm25: -2, changedAt: new Date().toISOString() },
      10,
    )
    const cold = combinedRank(
      { id: 'b', bm25: -2, changedAt: null },
      0,
    )
    expect(hot).toBeGreaterThan(cold)
  })
})

// ---------------------------------------------------------------------------
// Modal integration (search mocked — worker is not available in jsdom)
// ---------------------------------------------------------------------------

describe('UniversalSearchModal', () => {
  const mockSearch = vi.fn(async (q: string) => ({
    query: q,
    total: 2,
    tookMs: 3,
    mode: 'fts' as const,
    results: [
      {
        id: 'student-1',
        entity_type: 'student',
        entity_id: 1,
        label: 'Amina Kante',
        description: 'STU-001 • active',
        route: '/students/1',
        match_field: null,
        score: 0.92,
      },
      {
        id: 'payment-9',
        entity_type: 'payment',
        entity_id: 9,
        label: 'Payment #INV-234',
        description: 'Amount: 50000',
        route: '/fees/payments',
        match_field: null,
        score: 0.61,
      },
    ],
    grouped: [
      {
        entity_type: 'student',
        label: 'Students',
        icon: '',
        items: [
          {
            id: 'student-1',
            entity_type: 'student',
            entity_id: 1,
            label: 'Amina Kante',
            description: 'STU-001 • active',
            route: '/students/1',
            match_field: null,
            score: 0.92,
          },
        ],
      },
      {
        entity_type: 'payment',
        label: 'Payments',
        icon: '',
        items: [
          {
            id: 'payment-9',
            entity_type: 'payment',
            entity_id: 9,
            label: 'Payment #INV-234',
            description: 'Amount: 50000',
            route: '/fees/payments',
            match_field: null,
            score: 0.61,
          },
        ],
      },
    ],
  }))

  beforeEach(() => {
    mockSearch.mockClear()
  })

  it('renders results grouped by entity type after typing', async () => {
    const onNavigate = vi.fn()
    render(
      <UniversalSearchModal
        open
        onClose={vi.fn()}
        search={mockSearch}
        status={{ ready: true, inProgress: false, error: null, lastSyncedAt: Date.now() }}
        onNavigate={onNavigate}
      />,
    )

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'kante' } })
    await waitFor(() => {
      expect(screen.getByText('Amina Kante')).toBeInTheDocument()
    })
    expect(screen.getByText('Payment #INV-234')).toBeInTheDocument()
    // 'Students'/'Payments' appear in both the tab bar and the group headers.
    expect(screen.getAllByText('Students').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Payments').length).toBeGreaterThanOrEqual(1)
  })

  it('navigates and records the open on Enter', async () => {
    const onNavigate = vi.fn()
    render(
      <UniversalSearchModal
        open
        onClose={vi.fn()}
        search={mockSearch}
        status={{ ready: true, inProgress: false, error: null, lastSyncedAt: Date.now() }}
        onNavigate={onNavigate}
      />,
    )

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'kante' } })
    await waitFor(() => {
      expect(screen.getByText('Amina Kante')).toBeInTheDocument()
    })
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    expect(onNavigate).toHaveBeenCalledWith('/students/1', 'student-1')
  })

  it('shows sync status in the footer', () => {
    render(
      <UniversalSearchModal
        open
        onClose={vi.fn()}
        search={mockSearch}
        status={{ ready: true, inProgress: true, error: null, lastSyncedAt: null }}
        onNavigate={vi.fn()}
      />,
    )
    expect(screen.getByText('Syncing…')).toBeInTheDocument()
  })
})
