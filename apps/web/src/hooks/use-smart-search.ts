import { useState, useEffect, useMemo, useCallback } from 'react'
import Fuse from 'fuse.js'
import { studentApi } from '../api/student/student-api'
import { classApi } from '../api/academic/class-api'
import { sectionApi } from '../api/academic/section-api'
import type { StudentResponse } from '../api/generated/types'

interface SmartSearchResult {
  id: string
  label: string
  description: string
  type: 'student' | 'class' | 'section'
  icon: string
  action: () => void
  keywords: string[]
}

interface FuseDocument {
  id: string
  label: string
  description: string
  type: 'student' | 'class' | 'section'
  keywords: string[]
}

const ICONS: Record<string, string> = {
  student: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  class: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  section: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z',
}

export function useSmartSearch(navigate: (path: string) => void) {
  const [students, setStudents] = useState<StudentResponse[]>([])
  const [classes, setClasses] = useState<{ id: number; name: string }[]>([])
  const [sections, setSections] = useState<{ id: number; name: string }[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [studentRes, classRes, sectionRes] = await Promise.all([
          studentApi.list({ size: 200 }),
          classApi.list({ size: 200 }),
          sectionApi.list({ size: 200 }),
        ])
        if (!cancelled) {
          setStudents(studentRes.items)
          setClasses(classRes.items.map((c: any) => ({ id: c.id, name: c.name })))
          setSections(sectionRes.items.map((s: any) => ({ id: s.id, name: s.name })))
          setLoaded(true)
        }
      } catch {
        // Silent fail — search degrades gracefully
        if (!cancelled) setLoaded(true)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // Build Fuse documents
  const documents: FuseDocument[] = useMemo(() => {
    const docs: FuseDocument[] = []

    students.forEach((s) => {
      docs.push({
        id: `student-${s.id}`,
        label: `${s.first_name} ${s.last_name}`,
        description: `Student ${s.student_number} • ${s.status || 'Active'}`,
        type: 'student',
        keywords: [s.student_number, s.first_name, s.last_name, s.email || '', s.status || ''],
      })
    })

    classes.forEach((c) => {
      docs.push({
        id: `class-${c.id}`,
        label: c.name,
        description: 'Class',
        type: 'class',
        keywords: [c.name],
      })
    })

    sections.forEach((s) => {
      docs.push({
        id: `section-${s.id}`,
        label: s.name,
        description: 'Section',
        type: 'section',
        keywords: [s.name],
      })
    })

    return docs
  }, [students, classes, sections])

  // Fuse.js instance
  const fuse = useMemo(() => {
    return new Fuse(documents, {
      keys: ['label', 'keywords'],
      threshold: 0.4,
      distance: 200,
      minMatchCharLength: 1,
      includeScore: true,
    })
  }, [documents])

  const search = useCallback(
    (query: string): SmartSearchResult[] => {
      if (!query || query.length < 1) return []

      const results = fuse.search(query, { limit: 10 })

      return results.map(({ item }) => ({
        id: item.id,
        label: item.label,
        description: item.description,
        type: item.type,
        icon: ICONS[item.type] || '',
        action: () => {
          const idParts = item.id.split('-')
          const entityId = idParts[idParts.length - 1]
          switch (item.type) {
            case 'student':
              navigate(`/students/${entityId}`)
              break
            case 'class':
              navigate('/academic/classes')
              break
            case 'section':
              navigate('/academic/sections')
              break
          }
        },
        keywords: item.keywords,
      }))
    },
    [fuse, navigate]
  )

  return { search, loaded }
}
