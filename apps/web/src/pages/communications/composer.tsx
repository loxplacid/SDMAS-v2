import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  templateApi,
  messageApi,
  metaApi,
  recipientApi,
} from '../../api/communications/communications-api'
import {
  PageHeader, Card, Button, Input, Select, Modal, Loading, ErrorState, useToast,
} from '../../components/ui'

export function ComposerPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [searchParams] = useSearchParams()
  const typeParam = searchParams.get('type')

  const [templates, setTemplates] = useState<any[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [channels, setChannels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [messageType, setMessageType] = useState(typeParam || 'targeted')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [priority, setPriority] = useState('normal')
  const [selectedChannels, setSelectedChannels] = useState<string[]>(['in_app'])

  const [recipientType, setRecipientType] = useState('user')
  const [recipientIds, setRecipientIds] = useState('')
  const [classIds, setClassIds] = useState('')
  const [sectionIds, setSectionIds] = useState('')

  const [scheduleAt, setScheduleAt] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [recurrence, setRecurrence] = useState('none')
  const [timezone, setTimezone] = useState('UTC')

  const [sending, setSending] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [resolvedRecipients, setResolvedRecipients] = useState<any[]>([])
  const [resolving, setResolving] = useState(false)

  useEffect(() => {
    Promise.all([
      templateApi.list(),
      metaApi.messageTypes(),
      metaApi.channels(),
    ])
      .then(([t, ty, ch]) => {
        setTemplates(t)
        setTypes(ty)
        setChannels(ch)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (typeParam && types.includes(typeParam)) {
      setMessageType(typeParam)
    }
  }, [typeParam, types])

  useEffect(() => {
    if (selectedTemplateId) {
      const tpl = templates.find((t: any) => String(t.id) === selectedTemplateId)
      if (tpl) {
        setSubject(tpl.subject || '')
        setBody(tpl.body)
        setMessageType(tpl.message_type)
        setSelectedChannels(tpl.channels || ['in_app'])
      }
    }
  }, [selectedTemplateId, templates])

  const handlePreview = useCallback(async () => {
    setResolving(true)
    try {
      const ids = recipientIds.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
      const cIds = classIds.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
      const sIds = sectionIds.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
      const resp = await recipientApi.resolve({
        recipient_type: recipientType,
        recipient_ids: ids.length > 0 ? ids : undefined,
        class_ids: cIds.length > 0 ? cIds : undefined,
        section_ids: sIds.length > 0 ? sIds : undefined,
      })
      setResolvedRecipients(resp.recipients)
      setPreviewOpen(true)
    } catch (err: any) {
      showToast(err?.detail || 'Failed to resolve recipients', 'error')
    } finally {
      setResolving(false)
    }
  }, [recipientType, recipientIds, classIds, sectionIds, showToast])

  const handleSend = useCallback(async () => {
    if (!body.trim()) {
      showToast('Message body is required', 'error')
      return
    }
    setSending(true)
    try {
      const ids = recipientIds.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
      const cIds = classIds.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
      const sIds = sectionIds.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))

      const payload: any = {
        body: body.trim(),
        message_type: messageType,
        priority,
        channels: selectedChannels,
        template_id: selectedTemplateId ? parseInt(selectedTemplateId) : undefined,
        subject: subject.trim() || undefined,
      }

      if (ids.length > 0) {
        payload.recipients = ids.map((id: number) => ({ recipient_type: recipientType, recipient_id: id }))
      }
      if (cIds.length > 0) payload.class_ids = cIds
      if (sIds.length > 0) payload.section_ids = sIds

      if (scheduleAt && scheduleTime) {
        payload.schedule_at = `${scheduleAt}T${scheduleTime}:00Z`
        payload.timezone = timezone
        payload.recurrence = recurrence
      }

      await messageApi.send(payload)
      showToast('Message sent successfully', 'success')
      navigate('/communications/sent')
    } catch (err: any) {
      showToast(err?.detail || 'Failed to send message', 'error')
    } finally {
      setSending(false)
    }
  }, [body, messageType, priority, selectedChannels, selectedTemplateId, subject,
      recipientType, recipientIds, classIds, sectionIds, scheduleAt, scheduleTime,
      recurrence, timezone, navigate, showToast])

  const toggleChannel = (ch: string) => {
    setSelectedChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch]
    )
  }

  if (loading) return <Loading text="Loading composer..." />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title="Compose Message"
        subtitle="Create and send a new communication"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/communications')}>
              Back to Hub
            </Button>
          </div>
        }
      />

      <Card title="Message Details">
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Template (optional)"
              options={[
                { value: '', label: 'No template — write from scratch' },
                ...templates.map((t: any) => ({ value: String(t.id), label: t.name })),
              ]}
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
            />
            <Select
              label="Message Type"
              options={types.map((t) => ({ value: t, label: t.replace(/_/g, ' ') }))}
              value={messageType}
              onChange={(e) => setMessageType(e.target.value)}
            />
          </div>

          <Input
            label="Subject"
            placeholder="Message subject (optional)"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">Body *</label>
            <textarea
              className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)] focus:border-transparent resize-y min-h-[200px]"
              placeholder="Write your message here. Use {variable_name} for template variables."
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Priority"
              options={[
                { value: 'normal', label: 'Normal' },
                { value: 'high', label: 'High' },
                { value: 'urgent', label: 'Urgent' },
              ]}
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">Channels</label>
            <div className="flex flex-wrap gap-2">
              {channels.map((ch) => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => toggleChannel(ch)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                    selectedChannels.includes(ch)
                      ? 'bg-[var(--color-brand-accent)] text-white border-[var(--color-brand-accent)]'
                      : 'bg-[var(--color-surface)] text-[var(--color-text-tertiary)] border-[var(--color-border)] hover:border-[var(--color-brand-accent)]'
                  }`}
                >
                  {ch.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Recipients">
        <div className="space-y-4">
          <Select
            label="Recipient Type"
            options={[
              { value: 'user', label: 'Users' },
              { value: 'student', label: 'Students' },
              { value: 'teacher', label: 'Teachers' },
              { value: 'parent', label: 'Parents' },
            ]}
            value={recipientType}
            onChange={(e) => setRecipientType(e.target.value)}
          />
          <Input
            label="Recipient IDs (comma-separated)"
            placeholder="e.g. 1, 2, 3"
            value={recipientIds}
            onChange={(e) => setRecipientIds(e.target.value)}
          />
          <Input
            label="Class IDs (comma-separated)"
            placeholder="e.g. 5, 6 — sends to all enrolled students"
            value={classIds}
            onChange={(e) => setClassIds(e.target.value)}
          />
          <Input
            label="Section IDs (comma-separated)"
            placeholder="e.g. 12, 13 — sends to all enrolled students"
            value={sectionIds}
            onChange={(e) => setSectionIds(e.target.value)}
          />
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={handlePreview} loading={resolving}>
              Preview Recipients
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Schedule (optional)">
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Schedule Date"
              type="date"
              value={scheduleAt}
              onChange={(e) => setScheduleAt(e.target.value)}
            />
            <Input
              label="Schedule Time"
              type="time"
              value={scheduleTime}
              onChange={(e) => setScheduleTime(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Recurrence"
              options={[
                { value: 'none', label: 'No recurrence' },
                { value: 'daily', label: 'Daily' },
                { value: 'weekly', label: 'Weekly' },
                { value: 'monthly', label: 'Monthly' },
              ]}
              value={recurrence}
              onChange={(e) => setRecurrence(e.target.value)}
            />
            <Input
              label="Timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            />
          </div>
        </div>
      </Card>

      <div className="flex gap-3 justify-end">
        <Button variant="secondary" onClick={() => navigate('/communications')}>
          Cancel
        </Button>
        <Button onClick={handleSend} loading={sending}>
          {scheduleAt && scheduleTime ? 'Schedule Message' : 'Send Message'}
        </Button>
      </div>

      <Modal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title="Recipient Preview"
        size="lg"
      >
        <div className="space-y-3">
          <p className="text-sm text-[var(--color-text-tertiary)]">
            {resolvedRecipients.length} recipient(s) resolved
          </p>
          <div className="max-h-80 overflow-y-auto space-y-2">
            {resolvedRecipients.slice(0, 100).map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[var(--color-surface-hover)]">
                <span className="text-sm font-medium text-[var(--color-text-primary)]">{r.name || `#${r.recipient_id}`}</span>
                <span className="text-xs text-[var(--color-text-tertiary)]">{r.recipient_type}{r.email ? ` — ${r.email}` : ''}</span>
              </div>
            ))}
            {resolvedRecipients.length > 100 && (
              <p className="text-xs text-[var(--color-text-tertiary)] text-center">
                ...and {resolvedRecipients.length - 100} more
              </p>
            )}
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default ComposerPage
