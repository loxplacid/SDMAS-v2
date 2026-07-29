import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminUserApi } from '../../api/auth/auth-api'
import type { UserResponse, UserCreate } from '../../api/generated/types'
import { Card, Table, Pagination, Input, Select, Button, Badge, Modal, Form, Alert, ErrorState, useToast } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'
import { capitalize, formatDateTime } from '../../lib/utils'

const roleBadge: Record<string, 'info' | 'success'> = { admin: 'info', staff: 'success' }
const activeBadge: Record<string, 'success' | 'danger'> = { true: 'success', false: 'danger' }

export function UserListPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  useKeyboardShortcut({ 'n': () => openCreateModal() }, [])

  const [data, setData] = useState<UserResponse[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [roleFilter, setRoleFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<UserResponse | null>(null)
  const [formData, setFormData] = useState<UserCreate>({ email: '', username: '', password: '', display_name: '' })
  const [editRole, setEditRole] = useState('staff')
  const [editActive, setEditActive] = useState(true)
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const fetchIdRef = useRef(0)

  const fetch = useCallback(async (params: { page?: number; size?: number; role?: string }) => {
    const fetchId = ++fetchIdRef.current
    setLoading(true); setError(null)
    try {
      const result = await adminUserApi.list(params)
      if (fetchId === fetchIdRef.current) {
        setData(result.items); setTotal(result.total); setPages(result.pages); setPage(result.page)
      }
    } catch (err: any) {
      if (fetchId === fetchIdRef.current) setError(err?.detail || 'Failed to load users')
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch({ page, size, role: roleFilter || undefined })
  }, [page, size, roleFilter, fetch])

  const openCreateModal = () => {
    setEditing(null); setFormData({ email: '', username: '', password: '', display_name: '' })
    setEditRole('staff'); setEditActive(true)
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const openEditModal = (user: UserResponse) => {
    setEditing(user)
    setFormData({ email: user.email, username: user.username, password: '', display_name: user.display_name })
    setEditRole(user.role); setEditActive(user.is_active)
    setFormErrors({}); setApiError(null); setModalOpen(true)
  }

  const validate = () => {
    const e: Record<string, string> = {}
    if (!formData.display_name.trim()) e.display_name = 'Display name is required'
    if (!editing) {
      if (!formData.username.trim()) e.username = 'Username is required'
      else if (formData.username.trim().length < 3) e.username = 'At least 3 characters'
      if (!formData.email.trim()) e.email = 'Email is required'
      if (!formData.password) e.password = 'Password is required'
      else if (formData.password.length < 8) e.password = 'At least 8 characters'
    }
    setFormErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setSaving(true); setApiError(null)
    try {
      if (editing) {
        const updated = await adminUserApi.update(editing.id, {
          display_name: formData.display_name || null,
          email: formData.email || null,
          role: editRole,
          is_active: editActive,
        })
        setData((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
        showToast('User updated', 'success')
      } else {
        const created = await adminUserApi.create(formData)
        setData((prev) => [created, ...prev]); setTotal((t) => t + 1)
        showToast('User created', 'success')
      }
      setModalOpen(false)
    } catch (err: any) { setApiError(err?.detail || 'Failed to save user') }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-brand-accent)] tracking-wide mb-1">Administration</p>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] tracking-tight">Users</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{total} user{total !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={openCreateModal}>
          Add User
          <kbd className="ml-2 hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-medium text-white/80">N</kbd>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <Select
          options={[{ value: 'admin', label: 'Admin' }, { value: 'staff', label: 'Staff' }]}
          placeholder="All roles"
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(1) }}
        />
      </div>

      <Card className="hover:shadow-sm transition-shadow duration-[var(--motion-fast)] motion-reduce:transition-none">
        {error ? <ErrorState message={error} onRetry={() => fetch({ page, size })} /> : (
          <>
            <Table
              columns={[
                { key: 'username', header: 'Username' },
                { key: 'display_name', header: 'Display Name' },
                { key: 'email', header: 'Email' },
                { key: 'role', header: 'Role', render: (u: UserResponse) => <Badge variant={roleBadge[u.role] || 'default'}>{capitalize(u.role)}</Badge> },
                { key: 'is_active', header: 'Status', render: (u: UserResponse) => <Badge variant={activeBadge[String(u.is_active)] || 'default'}>{u.is_active ? 'Active' : 'Inactive'}</Badge> },
                { key: 'created_at', header: 'Created', render: (u: UserResponse) => formatDateTime(u.created_at) },
                {
                  key: 'actions', header: 'Actions',
                  render: (u: UserResponse) => (
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => openEditModal(u)}>Edit</Button>
                    </div>
                  ),
                },
              ]}
              data={data}
              keyExtractor={(u) => u.id}
              emptyMessage="No users found."
              loading={loading}
            />
            <Pagination page={page} size={size} total={total} pages={pages} onPageChange={setPage} onSizeChange={(s) => { setSize(s); setPage(1) }} />
          </>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)}
        title={editing ? 'Edit User' : 'Add User'}
        footer={
          <>
            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} loading={saving}>{editing ? 'Save Changes' : 'Create User'}</Button>
          </>
        }
      >
        {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}
        <Form onSubmit={handleSubmit}>
          <Input label="Username" value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            error={formErrors.username} disabled={!!editing} required={!editing} />
          <Input label="Display Name" value={formData.display_name}
            onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
            error={formErrors.display_name} required />
          <Input label="Email" type="email" value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            error={formErrors.email} required />
          {!editing && (
            <Input label="Password" type="password" value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              error={formErrors.password} required />
          )}
          {editing && (
            <>
              <Select label="Role" value={editRole} onChange={(e) => setEditRole(e.target.value)}
                options={[{ value: 'staff', label: 'Staff' }, { value: 'admin', label: 'Admin' }]} />
              <Select label="Status" value={String(editActive)} onChange={(e) => setEditActive(e.target.value === 'true')}
                options={[{ value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' }]} />
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}