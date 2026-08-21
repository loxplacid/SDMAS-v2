import { useState, useEffect, useCallback, useRef } from 'react';
import { useToast } from './use-toast';
import type {
  Room,
  RoomCreate,
  RoomUpdate,
  RoomPage,
  TimeSlot,
  TimetableEntryResponse,
  Substitution,
  ExamSchedule,
  GradingStructure,
  GradeRecord,
  Curriculum,
  TimetableCheckResult,
  ConflictDetail,
} from '../api/academic_ops/types';

import {
  listRooms,
  listTimeSlots,
  listTimetableEntries,
  listSubstitutions,
  listExamSchedules,
  listGradingStructures,
  listGradeRecords,
  listCurricula,
  createRoom,
  updateRoom,
  deleteRoom,
  createTimeSlot,
  updateTimeSlot,
  deleteTimeSlot,
  createTimetableEntry,
  updateTimetableEntry,
  deleteTimetableEntry,
  checkTimetableConflicts,
  createSubstitution,
  approveSubstitution,
  declineSubstitution,
  deleteSubstitution,
  createExamSchedule,
  updateExamSchedule,
  deleteExamSchedule,
  createGradingStructure,
  updateGradingStructure,
  deleteGradingStructure,
  createGradeRecord,
  updateGradeRecord,
  deleteGradeRecord,
  createCurriculum,
  updateCurriculum,
  deleteCurriculum,
  AcademicOpsApiError,
} from '../api/academic_ops/client';

// ── Generic useList Hook ───────────────────────────────────────────

interface UseListOptions<T> {
  defaultPageSize?: number;
  onSelect?: (item: T) => void;
}

export function useList<T extends { id: number }>(
  fetchFn: (params: { page: number; size: number; [key: string]: any }) => Promise<{ items: T[]; total: number }>,
  options: UseListOptions<T> = {}
) {
  const { defaultPageSize = 20, onSelect } = options;

  const [data, setData] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size] = useState(defaultPageSize);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (pageNum = 1, pageSize = size, filters: Record<string, any> = {}) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn({ page: pageNum, size: pageSize, ...filters });
      setData(result.items);
      setTotal(result.total);
      setPage(pageNum);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [fetchFn, size]);

  const refresh = useCallback(() => fetchData(page, size), [fetchData, page, size]);

  const selectAndRefresh = useCallback((item: T) => {
    onSelect?.(item);
  }, [onSelect]);

  return {
    data,
    total,
    page,
    size,
    loading,
    error,
    fetchData,
    refresh,
    select: selectAndRefresh,
  };
}

// ── useRooms Hook ─────────────────────────────────────────────────

export function useRooms(pageSize = 20) {
  return useList<Room>((params) => listRooms(params), { defaultPageSize: pageSize });
}

// ── useTimeSlots Hook ────────────────────────────────────────────

export function useTimeSlots(pageSize = 20) {
  return useList<TimeSlot>((params) => listTimeSlots(params), { defaultPageSize: pageSize });
}

// ── useTimetableEntries Hook ────────────────────────────────────

export function useTimetableEntries(pageSize = 20) {
  const [conflictChecks, setConflictChecks] = useState<Map<number, TimetableCheckResult>>(new Map());

  const fetchFn = useCallback((params: any) => listTimetableEntries(params), []);
  const baseResult = useList<TimetableEntryResponse>(fetchFn, { defaultPageSize: pageSize });

  const checkConflicts = useCallback(async (entryData: any) => {
    try {
      const result = await checkTimetableConflicts(entryData);
      setConflictChecks(prev => new Map(prev).set(Date.now(), result));
      return result;
    } catch (err) {
      throw err;
    }
  }, []);

  const createEntryWithCheck = useCallback(async (data: any) => {
    // First check for conflicts
    const conflicts = await checkConflicts(data);
    if (conflicts.has_conflicts) {
      throw new Error('Cannot create entry: timetable conflict detected');
    }
    // Then create
    return await createTimetableEntry(data);
  }, [checkConflicts]);

  return {
    ...baseResult,
    checkConflicts,
    createEntryWithCheck,
    conflictChecks,
  };
}

// ── useSubstitutions Hook ────────────────────────────────────────

export function useSubstitutions(pageSize = 20) {
  return useList<Substitution>((params) => listSubstitutions(params), { defaultPageSize: pageSize });
}

// ── useSubstitutions Actions Hook ─────────────────────────────────┐
export function useSubstitutionActions() {
  const { showToast } = useToast();

  const approve = useCallback(async (id: number) => {
    try {
      const result = await approveSubstitution(id);
      showToast({ title: 'Substitution Approved', status: 'success' });
      return result;
    } catch (err) {
      showToast({
        title: 'Failed to approve substitution',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error'
      });
      throw err;
    }
  }, [showToast]);

  const decline = useCallback(async (id: number, reason?: string) => {
    try {
      const result = await declineSubstitution(id, reason);
      showToast({ title: 'Substitution Declined', status: 'success' });
      return result;
    } catch (err) {
      showToast({
        title: 'Failed to decline substitution',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error'
      });
      throw err;
    }
  }, [showToast]);

  const remove = useCallback(async (id: number) => {
    try {
      await deleteSubstitution(id);
      showToast({ title: 'Substitution removed', status: 'success' });
    } catch (err) {
      showToast({
        title: 'Failed to remove substitution',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error'
      });
      throw err;
    }
  }, [showToast]);

  return { approve, decline, remove };
}

// ── useExamSchedules Hook ───────────────────────────────────────

export function useExamSchedules(pageSize = 20) {
  return useList<ExamSchedule>((params) => listExamSchedules(params), { defaultPageSize: pageSize });
}

// ── useGradingStructures Hook ───────────────────────────────────

export function useGradingStructures(pageSize = 20) {
  return useList<GradingStructure>((params) => listGradingStructures(params), { defaultPageSize: pageSize });
}

// ── useGradeRecords Hook ────────────────────────────────────────

export function useGradeRecords(pageSize = 20) {
  return useList<GradeRecord>((params) => listGradeRecords(params), { defaultPageSize: pageSize });
}

// ── useCurricula Hook ───────────────────────────────────────────

export function useCurricula(pageSize = 20) {
  return useList<Curriculum>((params) => listCurricula(params), { defaultPageSize: pageSize });
}

// ── Conflict Visualization Hook ─────────────────────────────────

export function useConflictVisualization() {
  const getConflictIcon = useCallback((type: ConflictDetail['type']) => {
    const icons: Record<ConflictDetail['type'], string> = {
      room: '🖳️',
      teacher: '👩‍🏫',
      time_slot: '⏰',
    };
    return icons[type] || '⚠️';
  }, []);

  const getConflictColor = useCallback((type: ConflictDetail['type']) => {
    const colors: Record<ConflictDetail['type'], string> = {
      room: 'bg-red-100 border-red-300',
      teacher: 'bg-amber-100 border-amber-300',
      time_slot: 'bg-blue-100 border-blue-300',
    };
    return colors[type] || 'bg-gray-100 border-gray-300';
  }, []);

  const formatConflictExplanation = useCallback((conflict: ConflictDetail) => {
    const parts: string[] = [];

    if (conflict.type === 'room') {
      parts.push(`Room "${conflict.conflicting_details.room?.name || 'Unknown'}" is already in use`);
    } else if (conflict.type === 'teacher') {
      parts.push(`Teacher "${conflict.conflicting_details.teacher?.name || 'Unknown'}" has overlapping assignment`);
    } else if (conflict.type === 'time_slot') {
      parts.push('Time slot overlaps with existing entry');
    }

    parts.push(`See entry #${conflict.conflicting_entry_id}`);
    return parts.join(' • ');
  }, []);

  return { getConflictIcon, getConflictColor, formatConflictExplanation };
}