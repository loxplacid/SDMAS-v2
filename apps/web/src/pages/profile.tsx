import { useState } from 'react'
import { useAuth } from '../api/auth/auth-context'
import { authApi } from '../api/auth/auth-api'
import { Card, Input, Button, Alert, useToast } from '../components/ui'

export function ProfilePage() {
  const { user, updateUser } = useAuth()
  const { showToast } = useToast()

  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const updated = await authApi.updateMe({
        display_name: displayName || null,
        email: email || null,
      })
      updateUser(updated)
      showToast('Profile updated', 'success')
    } catch (err: any) {
      setError(err?.detail || 'Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setChangingPassword(true)
    setError(null)
    try {
      await authApi.changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      showToast('Password changed', 'success')
    } catch (err: any) {
      setError(err?.detail || 'Failed to change password')
    } finally {
      setChangingPassword(false)
    }
  }

  return (
    <div className="space-y-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900">Profile</h1>

      {error && <Alert variant="error" onClose={() => setError(null)}>{error}</Alert>}

      <Card title="Account Information">
        <div className="space-y-2 text-sm">
          <p><span className="font-medium text-gray-500">Username:</span> {user?.username}</p>
          <p><span className="font-medium text-gray-500">Role:</span> <span className="capitalize">{user?.role}</span></p>
          <p><span className="font-medium text-gray-500">Status:</span> {user?.is_active ? 'Active' : 'Inactive'}</p>
        </div>
      </Card>

      <Card title="Edit Profile">
        <form onSubmit={handleUpdateProfile} className="space-y-4">
          <Input label="Display Name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" loading={saving}>Save Changes</Button>
        </form>
      </Card>

      <Card title="Change Password">
        <form onSubmit={handleChangePassword} className="space-y-4">
          <Input label="Current Password" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required />
          <Input label="New Password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
          <Button type="submit" loading={changingPassword}>Change Password</Button>
        </form>
      </Card>
    </div>
  )
}