import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { templateApi } from '../../api/communications/communications-api'
import {
  PageHeader, Card, Button, Input, Select, Modal, Loading, ErrorState, useToast, ConfirmDialog,
} from '../../components/ui'

export function TemplatesPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [templates, setTemplates] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<any>(null)

  const [form, setForm] = useState({
    code: '', name: '', subject: '', body: '', message_type: 'announcement', channels: ['in_app'] as string[],
  })
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<any>(null)
  const [deleting, setDeleting] = useState(false)

  const loadTemplates = useCallback(() => {
    setLoading(true)
    templateApi.list()
      .then(setTemplates)
      .catch((err: any) => setError(err?.detail || 'Failed to load templates'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadTemplates() }, [loadTemplates])

  const resetForm = () => setForm({ code: '', name: '', subject: '', body: '', message_type: 'announcement', channels: ['in_app'] })

  const handleCreate = useCallback(async () => {
    if (!form.code.trim() || !form.name.trim() || !form.body.trim()) {
      showToast('Code, name, and body are required', 'error'); return
    }
    setSaving(true)
    try {
      await templateApi.create(form)
      showToast('Template created', 'success')
      setCreateOpen(false)
      resetForm()
      loadTemplates()
    } catch (err: any) { showToast(err?.detail || 'Failed to create template', 'error') }
    finally { setSaving(false) }
  }, [form, showToast, loadTemplates])

  const handleUpdate = useCallback(async () => {
    if (!editingTemplate) return
    if (!form.name.trim() || !form.body.trim()) {
      showToast('Name and body are required', 'error'); return
    }
    setSaving(true)
    try {
      await templateApi.update(editingTemplate.id, form)
      showToast('Template updated', 'success')
      setEditOpen(false)
      setEditingTemplate(null)
      resetForm()
      loadTemplates()
    } catch (err: any) { showToast(err?.detail || 'Failed to update template', 'error') }
    finally { setSaving(false) }
  }, [editingTemplate, form, showToast, loadTemplates])

  const handleDelete = useCallback(async (tpl: any) => {
    setDeleteTarget(tpl)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await templateApi.delete(deleteTarget.id)
      showToast('Template deleted', 'success')
      loadTemplates()
    } catch (err: any) { showToast(err?.detail || 'Failed to delete', 'error') }
    finally { setDeleting(false); setDeleteTarget(null) }
  }, [deleteTarget, showToast, loadTemplates])

  const openEdit = (tpl: any) => {
    setEditingTemplate(tpl)
    setForm({
      code: tpl.code,
      name: tpl.name,
      subject: tpl.subject || '',
      body: tpl.body,
      message_type: tpl.message_type,
      channels: tpl.channels || ['in_app'],
    })
    setEditOpen(true)
  }

  if (loading) return <Loading text="Loading templates..." />
  if (error) return <ErrorState message={error} onRetry={loadTemplates} />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Message Templates"
        subtitle="Create and manage reusable message templates"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/communications')}>
              Back to Hub
            </Button>
            <Button size="sm" onClick={() => { resetForm(); setCreateOpen(true) }}>
              New Template
            </Button>
          </div>
        }
      />

      {templates.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <p className="text-[var(--color-text-tertiary)]">No templates yet. Create one to get started.</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((tpl) => (
            <Card key={tpl.id} className="group">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[var(--color-text-primary)] truncate">{tpl.name}</h3>
                  <p className="text-xs text-[var(--color-text-tertiary)]">Code: {tpl.code}</p>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)] capitalize shrink-0">
                  {tpl.message_type.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-2 line-clamp-2">{tpl.body}</p>
              <div className="flex items-center gap-2 mt-3">
                {tpl.channels?.map((ch: string) => (
                  <span key={ch} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]">
                    {ch}
                  </span>
                ))}
              </div>
              <div className="flex gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button variant="secondary" size="sm" onClick={() => openEdit(tpl)}>Edit</Button>
                <Button variant="secondary" size="sm" onClick={() => handleDelete(tpl)}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={createOpen} onClose={() => { setCreateOpen(false); resetForm() }} title="Create Template" size="lg">
        <TemplateForm form={form} setForm={setForm} />
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="secondary" onClick={() => { setCreateOpen(false); resetForm() }}>Cancel</Button>
          <Button onClick={handleCreate} loading={saving}>Create</Button>
        </div>
      </Modal>

      <Modal open={editOpen} onClose={() => { setEditOpen(false); resetForm() }} title="Edit Template" size="lg">
        <TemplateForm form={form} setForm={setForm} />
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="secondary" onClick={() => { setEditOpen(false); resetForm() }}>Cancel</Button>
          <Button onClick={handleUpdate} loading={saving}>Update</Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        title="Delete Template"
        message={`Are you sure you want to delete "${deleteTarget?.name ?? ''}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        loading={deleting}
      />
    </div>
  )
}

function TemplateForm({ form, setForm }: { form: any; setForm: (f: any) => void }) {
  const update = (key: string, value: any) => setForm({ ...form, [key]: value })
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input label="Code" placeholder="e.g. fee_reminder" value={form.code} onChange={(e) => update('code', e.target.value)} />
        <Input label="Name" placeholder="Fee Reminder" value={form.name} onChange={(e) => update('name', e.target.value)} />
      </div>
      <Input label="Subject (optional)" placeholder="{{student_name}}, your fee is due" value={form.subject} onChange={(e) => update('subject', e.target.value)} />
      <div>
        <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">Body *</label>
        <textarea
          className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)] focus:border-transparent resize-y min-h-[150px]"
          placeholder="Dear {{student_name}}, ..."
          value={form.body}
          onChange={(e) => update('body', e.target.value)}
        />
      </div>
      <Select
        label="Message Type"
        options={['announcement', 'targeted', 'class', 'section', 'parent', 'teacher', 'staff'].map((t) => ({ value: t, label: t.replace(/_/g, ' ') }))}
        value={form.message_type}
        onChange={(e) => update('message_type', e.target.value)}
      />
    </div>
  )
}

export default TemplatesPage
