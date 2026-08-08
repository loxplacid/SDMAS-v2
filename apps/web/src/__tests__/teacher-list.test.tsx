import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'

const listMock = vi.fn()
const createMock = vi.fn()
const updateMock = vi.fn()

vi.mock('../api/academic/teacher-api', () => ({
  teacherApi: {
    list: (...args: unknown[]) => listMock(...args),
    create: (...args: unknown[]) => createMock(...args),
    update: (...args: unknown[]) => updateMock(...args),
  },
}))

// The page celebrates the first teacher — the provider is out of scope here.
vi.mock('../components/delight/delight-provider', () => ({
  useDelight: () => ({ celebrate: vi.fn() }),
}))

const { TeacherListPage } = await import('../pages/teachers/teacher-list')

const teachers = [
  { id: 1, employee_number: 'EMP-101', first_name: 'Amina', last_name: 'Yusuf', email: 'amina@school.edu.ng', status: 'active' },
  { id: 2, employee_number: 'EMP-102', first_name: 'Bello', last_name: 'Musa', email: 'bello@school.edu.ng', status: 'inactive' },
]

function renderPage(route = '/teachers') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="/teachers" element={<TeacherListPage />} />
          <Route path="/teachers/:id" element={<div>Teacher detail</div>} />
          <Route path="/teachers/:id/360" element={<div>Teacher 360</div>} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  listMock.mockResolvedValue({ items: teachers, total: teachers.length, pages: 1, page: 1 })
})

describe('Teacher list — DataWorkspace (local mode)', () => {
  it('loads and renders teacher rows', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('EMP-101')).toBeInTheDocument())
    expect(screen.getByText('Amina')).toBeInTheDocument()
    expect(screen.getByText('Bello')).toBeInTheDocument()
    // status badges render for both teachers
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('filters rows locally from the rail search box', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Amina')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'bello' } })
    await waitFor(() => expect(screen.queryByText('Amina')).not.toBeInTheDocument())
    expect(screen.getByText('Bello')).toBeInTheDocument()
  })

  it('navigates to the detail page on row click', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Amina')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Amina'))
    expect(await screen.findByText('Teacher detail')).toBeInTheDocument()
  })

  it('opens the Add Teacher modal from the primary action', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByRole('button', { name: /Add Teacher/ })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Add Teacher/ }))
    expect(screen.getByLabelText('Employee Number')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })

  it('shows the empty state when there are no teachers', async () => {
    listMock.mockResolvedValueOnce({ items: [], total: 0, pages: 0, page: 1 })
    renderPage()
    await waitFor(() => expect(screen.getByText('No teachers yet')).toBeInTheDocument())
  })
})
