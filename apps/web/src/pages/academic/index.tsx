import { HubPage } from '../../components/ui/hub-page'

const academicLinks = [
  { label: 'Academic Years', description: 'Manage academic years and terms', route: '/academic/years', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { label: 'Classes', description: 'Manage classes and their structure', route: '/academic/classes', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' },
  { label: 'Sections', description: 'Manage class sections', route: '/academic/sections', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
  { label: 'Enrollments', description: 'View and manage student enrollments', route: '/academic/enrollments', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z' },
  { label: 'Terms', description: 'Manage academic terms within years', route: '/academic/terms', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { label: 'Teacher Assignments', description: 'Assign teachers to classes and subjects', route: '/academic/assignments', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
]

export function AcademicPage() {
  return (
    <HubPage
      eyebrow="Academics"
      title="Academic Structure"
      subtitle="Manage academic years, classes, sections, enrollments, and teacher assignments"
      stats={[]}
      links={academicLinks}
    />
  )
}

export default AcademicPage
