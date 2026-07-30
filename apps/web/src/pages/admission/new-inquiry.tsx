import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { admissionApi, type AdmissionApplicationCreate } from '../../api/admission/admission-api'
import { Card, Input, Select, Button, Alert, Breadcrumbs, PageHeader, Form } from '../../components/ui'
import { useToast } from '../../components/ui/toast'

export function NewInquiryPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [formData, setFormData] = useState<AdmissionApplicationCreate>({
    applicant_name: '',
    email: '',
    phone: '',
    address: '',
    source: 'website',
    previous_education: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const validate = (): boolean => {
    const errs: Record<string, string> = {}
    if (!formData.applicant_name?.trim()) errs.applicant_name = 'Applicant name is required'
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) errs.email = 'Invalid email format'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    setApiError(null)
    try {
      const created = await admissionApi.createApplication({
        ...formData,
        email: formData.email || null,
        phone: formData.phone || null,
        address: formData.address || null,
        previous_education: formData.previous_education || null,
      })
      showToast('Inquiry created successfully', 'success')
      navigate(`/admissions/${created.id}`)
    } catch (err: any) {
      setApiError(err?.detail || 'Failed to create inquiry')
    } finally {
      setSaving(false)
    }
  }

  const updateField = (field: string, value: string | null) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in-up">
      <Breadcrumbs items={[
        { label: 'Admissions', href: '/admissions' },
        { label: 'Applications', href: '/admissions/applications' },
        { label: 'New Inquiry' },
      ]} />

      <PageHeader
        title="New Admission Inquiry"
        subtitle="Capture basic details to begin the admission process"
      />

      <Card>
        <Form onSubmit={handleSubmit}>
          {apiError && <Alert variant="error" onClose={() => setApiError(null)}>{apiError}</Alert>}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <Input
                label="Applicant Name"
                value={formData.applicant_name ?? ''}
                onChange={(e) => updateField('applicant_name', e.target.value)}
                error={errors.applicant_name}
                required
                placeholder="Full name of the applicant"
              />
            </div>

            <Input
              label="Email"
              type="email"
              value={formData.email ?? ''}
              onChange={(e) => updateField('email', e.target.value)}
              error={errors.email}
              placeholder="Email address"
            />

            <Input
              label="Phone"
              type="tel"
              value={formData.phone ?? ''}
              onChange={(e) => updateField('phone', e.target.value)}
              placeholder="Phone number"
            />

            <Select
              label="Source"
              value={formData.source ?? 'website'}
              onChange={(e) => updateField('source', e.target.value)}
              options={[
                { value: 'website', label: 'Website' },
                { value: 'walk_in', label: 'Walk-in' },
                { value: 'referral', label: 'Referral' },
                { value: 'advertisement', label: 'Advertisement' },
                { value: 'other', label: 'Other' },
              ]}
            />

            <Input
              label="Date of Birth"
              type="date"
              value={formData.date_of_birth ?? ''}
              onChange={(e) => updateField('date_of_birth', e.target.value || null)}
            />
          </div>

          <Input
            label="Address"
            value={formData.address ?? ''}
            onChange={(e) => updateField('address', e.target.value)}
            placeholder="Current address"
          />

          <Input
            label="Previous Education"
            value={formData.previous_education ?? ''}
            onChange={(e) => updateField('previous_education', e.target.value)}
            placeholder="Previous school, college, or qualifications"
          />

          <div className="flex items-center gap-3 pt-2">
            <Button type="submit" loading={saving}>
              Create Inquiry
            </Button>
            <Button variant="outline" onClick={() => navigate('/admissions')}>
              Cancel
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default NewInquiryPage
