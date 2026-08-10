import { describe, it, expect } from 'vitest'
import { plural } from '../lib/utils'

describe('plural', () => {
  it('uses singular form for a count of 1', () => {
    expect(plural(1, 'term')).toBe('1 term')
  })

  it('appends s for plural counts', () => {
    expect(plural(3, 'term')).toBe('3 terms')
  })

  it('accepts an explicit plural form for irregular nouns', () => {
    expect(plural(2, 'class', 'classes')).toBe('2 classes')
    expect(plural(1, 'class', 'classes')).toBe('1 class')
  })

  it('locale-formats counts with thousands separators', () => {
    expect(plural(2431, 'student')).toBe('2,431 students')
  })

  it('supports a BCP-47 locale for currency-style grouping', () => {
    expect(plural(12431, 'reconciliation', 'reconciliations', 'en-KE')).toBe('12,431 reconciliations')
  })

  it('handles zero as a plural count', () => {
    expect(plural(0, 'record')).toBe('0 records')
  })
})
