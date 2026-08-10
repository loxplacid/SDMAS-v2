import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OrganizationContext } from '../components/layout/organization-context'

const authMock = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
}))
const campusMock = vi.hoisted(() => ({
  campusName: null as string | null,
  isLoading: false,
}))

vi.mock('../api/auth/auth-context', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({ user: authMock.user, logout: vi.fn() }),
}))

vi.mock('../hooks/use-campus', () => ({
  useCampus: () => ({ campusName: campusMock.campusName, isLoading: campusMock.isLoading }),
}))

beforeEach(() => {
  authMock.user = {
    id: 1,
    role: 'accountant',
    roles: ['accountant'],
    display_name: 'Fifi Finance',
    username: 'fifi',
    email: 'fifi@school.edu',
    campus_id: 1,
  }
  campusMock.campusName = 'Nairobi International School'
  campusMock.isLoading = false
})

describe('OrganizationContext (D1 §1)', () => {
  it('renders the real campus name and role badge', () => {
    render(<OrganizationContext />)
    expect(screen.getByText('Organization')).toBeInTheDocument()
    expect(screen.getByText('Nairobi International School')).toBeInTheDocument()
    expect(screen.getByText('Accountant')).toBeInTheDocument()
  })

  it('shows a placeholder when no campus is assigned', () => {
    campusMock.campusName = null
    render(<OrganizationContext />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders a skeleton while the campus fetch is loading', () => {
    campusMock.isLoading = true
    campusMock.campusName = null
    render(<OrganizationContext />)
    expect(screen.getByText('Organization')).toBeInTheDocument()
    // Skeleton renders as an accessible status region; the name is not yet shown.
    expect(screen.queryByText('Nairobi International School')).not.toBeInTheDocument()
  })

  it('omits the role badge for users without a role', () => {
    authMock.user = { id: 1, role: null }
    render(<OrganizationContext />)
    expect(screen.queryByText('Accountant')).not.toBeInTheDocument()
  })
})
