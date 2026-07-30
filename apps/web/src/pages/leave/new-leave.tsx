import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { leaveApi, LEAVE_TYPES } from '../../api/leave/leave-api'
import { Card, Input, Select, Button, Alert, Breadcrumbs, PageHeader, Form } from '../../components/ui'
import { useToast } from '../../components/ui/toast'
import { capitalize } from '../../lib/utils'

export function NewLeavePage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [leaveType, setLeaveType] = useState('sick')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const validate = (): boolean => {
    const errs: Record<string, string> = {}
    if (!startDate) errs.start_date = 'Start date is required'
    if (!endDate) errs.end_date = 'End date is required'
    if (startDate && endDate && endDate < startDate) errs.end_date = 'End date must be after start date'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    setApiError(null)
    try {
      const created = await leaveApi.create({ leave_type: leaveType, start_date: startDate, end_date: endDate, reason: reason || null })
      showToast('Leave request submitted', 'success')
      navigate(`/leave/${created.id}`)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to submit leave request')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in-up">
      <Breadcrumbs items={[
        { label: 'Leave', href: '/leave' },
        { label: 'New Leave Request' },
      ]} />

      <PageHeader title="New Leave Request" subtitle="Submit a leave request through the approval workflow" />

      <Card>
        <Form onSubmit={handleSubmit}>
          {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}

          <Select
            label="Leave Type"
            value={leaveType}
            onChange={(e) => setLeaveType(e.target.value)}
            options={LEAVE_TYPES.map((t) => ({ value: t, label: capitalize(t) }))}
            required
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Start Date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              error={errors.start_date}
              required
            />
            <Input
              label="End Date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              error={errors.end_date}
              required
            />
          </div>

          <Input
            label="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional reason for leave"
          />

          <div className="flex items-center gap-3 pt-2">
            <Button type="submit" loading={saving}>Submit Leave Request</Button>
            <Button variant="outline" onClick={() => navigate('/leave')}>Cancel</Button>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default NewLeavePage
