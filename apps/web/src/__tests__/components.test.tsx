import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Loading } from '../components/ui/loading'
import { EmptyState } from '../components/ui/empty-state'
import { ErrorState } from '../components/ui/error-state'
import { Card } from '../components/ui/card'
import { Alert } from '../components/ui/alert'

describe('Button', () => {
  it('renders with children', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(<Button loading>Loading</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})

describe('Badge', () => {
  it('renders text', () => {
    render(<Badge>Active</Badge>)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })
})

describe('Loading', () => {
  it('renders loading text', () => {
    render(<Loading text="Please wait..." />)
    expect(screen.getByText('Please wait...')).toBeInTheDocument()
  })
})

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="No items" />)
    expect(screen.getByText('No items')).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('renders error message', () => {
    render(<ErrorState message="Something broke" />)
    expect(screen.getByText('Something broke')).toBeInTheDocument()
  })

  it('renders retry button', () => {
    render(<ErrorState message="Error" onRetry={() => {}} />)
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })
})

describe('Card', () => {
  it('renders title and children', () => {
    render(
      <Card title="My Card">
        <p>Content</p>
      </Card>
    )
    expect(screen.getByText('My Card')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
  })
})

describe('Alert', () => {
  it('renders message', () => {
    render(<Alert>Something happened</Alert>)
    expect(screen.getByText('Something happened')).toBeInTheDocument()
  })
})