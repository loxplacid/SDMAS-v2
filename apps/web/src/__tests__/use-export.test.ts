import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

// The heavy export libraries (jspdf ~200KB gz, xlsx ~160KB gz) must be
// loaded *on demand* — the hook imports them dynamically inside the export
// callbacks so opening a report page costs nothing until the user exports.
const xlsxWriteFile = vi.fn()
const aoaToSheet = vi.fn(() => ({}))

vi.mock('xlsx', () => ({
  utils: { aoa_to_sheet: aoaToSheet, book_new: vi.fn(() => ({})), book_append_sheet: vi.fn() },
  writeFile: xlsxWriteFile,
}))

vi.mock('jspdf-autotable', () => ({ default: vi.fn() }))

const jsPDFCtor = vi.fn().mockImplementation(() => ({
  setFontSize: vi.fn(),
  setTextColor: vi.fn(),
  text: vi.fn(),
  save: vi.fn(),
}))
vi.mock('jspdf', () => ({ default: jsPDFCtor }))

import { useExport } from '../hooks/use-export'

describe('useExport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  afterEach(() => {
    vi.resetModules()
  })

  it('exports PDF only when requested, loading jspdf dynamically', async () => {
    const { result } = renderHook(() => useExport())
    expect(result.current.exporting).toBeNull()

    await act(async () => {
      await result.current.exportPDF('Report', [{ key: 'name', header: 'Name' }], [{ name: 'Ada' }], 'r1')
    })

    expect(jsPDFCtor).toHaveBeenCalledOnce()
    expect(result.current.exporting).toBeNull()
  })

  it('exports Excel only when requested, loading xlsx dynamically', async () => {
    const { result } = renderHook(() => useExport())

    await act(async () => {
      await result.current.exportExcel('Report', [{ key: 'name', header: 'Name' }], [{ name: 'Ada' }], 'r1')
    })

    expect(aoaToSheet).toHaveBeenCalledWith([
      ['Name'],
      ['Ada'],
    ])
    expect(xlsxWriteFile).toHaveBeenCalledWith(expect.anything(), 'r1.xlsx')
    expect(jsPDFCtor).not.toHaveBeenCalled()
    expect(result.current.exporting).toBeNull()
  })

  it('uses the render function output as the exported cell value', async () => {
    const { result } = renderHook(() => useExport())
    const col = { key: 'score', header: 'Score', render: (row: any) => `<b>${row.score}</b>` }

    await act(async () => {
      await result.current.exportExcel('Report', [col], [{ score: 42 }], 'r2')
    })

    expect(aoaToSheet).toHaveBeenCalledWith([['Score'], ['42']])
  })

  it('clears the exporting flag even when the library throws', async () => {
    jsPDFCtor.mockImplementationOnce(() => {
      throw new Error('pdf boom')
    })
    const { result } = renderHook(() => useExport())

    await act(async () => {
      await expect(
        result.current.exportPDF('Report', [], [], 'r3')
      ).rejects.toThrow('pdf boom')
    })

    expect(result.current.exporting).toBeNull()
  })
})
