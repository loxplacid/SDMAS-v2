import { Select } from '../ui'

interface FilterOption {
  value: string
  label: string
}

interface AnalyticsFilterBarProps {
  academicYears: FilterOption[]
  selectedYearId: string
  onYearChange: (value: string) => void
  classes: FilterOption[]
  selectedClassId: string
  onClassChange: (value: string) => void
  sections: FilterOption[]
  selectedSectionId: string
  onSectionChange: (value: string) => void
  granularity?: string
  onGranularityChange?: (value: string) => void
  showGranularity?: boolean
}

export function AnalyticsFilterBar({
  academicYears,
  selectedYearId,
  onYearChange,
  classes,
  selectedClassId,
  onClassChange,
  sections,
  selectedSectionId,
  onSectionChange,
  granularity,
  onGranularityChange,
  showGranularity = false,
}: AnalyticsFilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 items-end">
      <div className="min-w-[180px]">
        <label className="block text-xs font-medium text-gray-600 mb-1">Academic Year</label>
        <Select
          options={[{ value: '', label: 'All Years' }, ...academicYears]}
          value={selectedYearId}
          onChange={(e) => {
            onYearChange(e.target.value)
            onClassChange('')
            onSectionChange('')
          }}
          placeholder="All Years"
        />
      </div>
      <div className="min-w-[160px]">
        <label className="block text-xs font-medium text-gray-600 mb-1">Class</label>
        <Select
          options={[{ value: '', label: 'All Classes' }, ...classes]}
          value={selectedClassId}
          onChange={(e) => {
            onClassChange(e.target.value)
            onSectionChange('')
          }}
          placeholder="All Classes"
        />
      </div>
      <div className="min-w-[160px]">
        <label className="block text-xs font-medium text-gray-600 mb-1">Section</label>
        <Select
          options={[{ value: '', label: 'All Sections' }, ...sections]}
          value={selectedSectionId}
          onChange={(e) => onSectionChange(e.target.value)}
          placeholder="All Sections"
        />
      </div>
      {showGranularity && onGranularityChange && (
        <div className="min-w-[140px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Granularity</label>
          <Select
            options={[
              { value: 'daily', label: 'Daily' },
              { value: 'weekly', label: 'Weekly' },
              { value: 'monthly', label: 'Monthly' },
            ]}
            value={granularity || 'daily'}
            onChange={(e) => onGranularityChange(e.target.value)}
          />
        </div>
      )}
    </div>
  )
}
