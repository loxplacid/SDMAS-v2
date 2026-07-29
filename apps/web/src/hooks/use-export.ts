import { useCallback, useState } from 'react'
import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import * as XLSX from 'xlsx'

interface Column {
  key: string
  header: string
  render?: (row: any) => string
}

function getCellValue(row: any, col: Column): string {
  if (col.render) {
    // Strip HTML tags from rendered values for clean export
    const rendered = col.render(row)
    const div = document.createElement('div')
    div.innerHTML = rendered
    return div.textContent || div.innerText || ''
  }
  return String(row[col.key] ?? '')
}

export function useExport() {
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null)

  const exportPDF = useCallback(async (
    title: string,
    columns: Column[],
    data: any[],
    filename: string
  ) => {
    setExporting('pdf')
    try {
      // Use dynamic import to avoid bundling issues
      const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })

      // Header
      doc.setFontSize(16)
      doc.text(title, 14, 20)
      doc.setFontSize(10)
      doc.setTextColor(100)
      doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 27)
      doc.setTextColor(0)

      // Table
      const headers = columns.map((c) => c.header)
      const rows = data.map((row) => columns.map((col) => getCellValue(row, col)))

      autoTable(doc, {
        head: [headers],
        body: rows,
        startY: 32,
        styles: { fontSize: 8, cellPadding: 2 },
        headStyles: { fillColor: [79, 122, 255], textColor: 255, fontStyle: 'bold' },
        alternateRowStyles: { fillColor: [245, 247, 250] },
        margin: { top: 32 },
      })

      doc.save(`${filename}.pdf`)
    } finally {
      setExporting(null)
    }
  }, [])

  const exportExcel = useCallback(async (
    title: string,
    columns: Column[],
    data: any[],
    filename: string
  ) => {
    setExporting('excel')
    try {
      const headers = columns.map((c) => c.header)
      const rows = data.map((row) => columns.map((col) => getCellValue(row, col)))

      const ws = XLSX.utils.aoa_to_sheet([headers, ...rows])

      // Set column widths
      ws['!cols'] = columns.map(() => ({ wch: 20 }))

      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, 'Report')

      XLSX.writeFile(wb, `${filename}.xlsx`)
    } finally {
      setExporting(null)
    }
  }, [])

  return { exportPDF, exportExcel, exporting }
}
