import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card,
  Button,
  Input,
  Select,
  Table,
  Badge,
  Modal,
  Form,
  Alert,
  DataTable,
  PageHeader,
  StatusBadge,
  useToast,
} from '../../components/ui';
import { ChevronLeft, ChevronRight, LayoutDashboard } from 'lucide-react';
import type {
  TimetableEntryResponse,
  TimetableCheckResult,
  TimeSlot,
  Room,
  TimetableEntryCreate,
} from '../../api/academic_ops/types';
import { useTimetableEntries, useTimeSlots, useRooms, useConflictVisualization } from '../../hooks/academic-ops';
import { listAcademicYears } from '../../api/academic/academic-year-api';
import type { AcademicYearResponse } from '../../api/generated/types';

// Time slot grid constants
const DAYS = [
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
];

const TIME_FORMAT = 'HH:mm';

interface TimetableWeekView {
  days: Array<{
    day: number;
    date: string;
    slots: TimetableEntryResponse[];
  }>;
  class_id: number;
  academic_year_id: number;
}

interface ConflictOverlayProps {
  conflicts: Array<{
    type: 'room' | 'teacher' | 'time_slot';
    entry_id: number;
    description: string;
  }>;
  onClose: () => void;
}

function ConflictOverlay({ conflicts, onClose }: ConflictOverlayProps) {
  if (conflicts.length === 0) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-md mx-4">
        <Card.Title>Timetable Conflicts Detected</Card.Title>
        <Card.Body>
          <ul className="space-y-2">
            {conflicts.map((c, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-2xl">⚠️</span>
                <span>{c.description}</span>
              </li>
            ))}
          </ul>
        </Card.Body>
        <Card.Footer>
          <Button variant="outline" onClick={onClose}>Close</Button>
          <Button color="primary">Resolve Conflicts</Button>
        </Card.Footer>
      </Card>
    </div>
  );
}

function TimetableCell({
  entry,
  onEdit,
  onConflictCheck,
}: {
  entry?: TimetableEntryResponse;
  onEdit: (entry: TimetableEntryResponse) => void;
  onConflictCheck: (entryId: number) => void;
}) {
  if (!entry) {
    return (
      <div
        className="h-full min-h-[60px] border border-gray-100 rounded bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
        onClick={() => {
          // Would open create dialog
        }}
      >
        <div className="p-2 text-xs font-medium text-gray-500">{''}</div>
      </div>
    );
  }

  return (
    <div
      className="h-full min-h-[60px] border border-blue-200 rounded bg-blue-50 hover:bg-blue-100 cursor-pointer transition-colors"
      onClick={() => onEdit(entry)}
    >
      <div className="p-2 text-xs space-y-1">
        <div className="font-medium">{entry.subject_name}</div>
        <div className="text-gray-600">{entry.teacher_name}</div>
        <div className="text-gray-500 text-xs">{entry.room_name}</div>
      </div>
    </div>
  );
}

function WeeklyGrid() {
  const { classId } = useParams<{ classId: string }>();
  const [academicYearId, setAcademicYearId] = useState<number | null>(null);
  const [academicYears, setAcademicYears] = useState<AcademicYearResponse[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<TimetableEntryResponse | null>(null);
  const [conflicts, setConflicts] = useState<TimetableCheckResult | null>(null);

  const { data: entries, loading: entriesLoading } = useTimetableEntries({
    class_id: parseInt(classId || '0'),
    academic_year_id: academicYearId || undefined,
  });

  const { data: timeSlots } = useTimeSlots();
  const { data: rooms } = useRooms();
  const { getConflictIcon, getConflictColor, formatConflictExplanation } = useConflictVisualization();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const currentPage = parseInt(searchParams.get('page') || '1');
  const [page, setPage] = useState(currentPage);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<{ day: number; slotId: number } | null>(null);

  useEffect(() => {
    listAcademicYears({ size: 50 }).then((r) => setAcademicYears(r.items));
  }, []);

  useEffect(() => {
    const pageParam = parseInt(searchParams.get('page') || '1');
    setPage(pageParam);
  }, [searchParams]);

  // Group entries by day and time slot
  const gridEntries = useMemo(() => {
    if (!entries || !timeSlots) return [];

    const entryMap = new Map<string, TimetableEntryResponse>();
    entries.forEach(e => entryMap.set(`${e.day_of_week}-${e.time_slot_id}`, e));

    const slotIndex = new Map<number, number>();
    timeSlots.forEach((s, i) => slotIndex.set(s.id, i));

    const rows: (TimetableEntryResponse | undefined)[][] = [];
    for (let i = 0; i < timeSlots.length; i++) {
      const row: (TimetableEntryResponse | undefined)[] = [];
      for (let day = 1; day <= 6; day++) {
        row.push(entryMap.get(`${day}-${timeSlots[i].id}`));
      }
      rows.push(row);
    }
    return rows;
  }, [entries, timeSlots]);

  const handleSlotClick = (day: number, slot: TimeSlot) => {
    setSelectedDay(day);
    setSelectedSlot({ day, slotId: slot.id });
    // Would open create modal
  };

  const handleEdit = (entry: TimetableEntryResponse) => {
    setSelectedEntry(entry);
    navigate(`/academic/timetable/${entry.id}/edit`);
  };

  const handleConflictCheck = useCallback(async (entryId: number) => {
    // Would call checkTimetableConflicts
  }, []);

  if (entriesLoading || !entries) {
    return <div className="p-6">Loading timetable...</div>;
  }

  return (
    <div className="flex-1 flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
          <h2 className="text-xl font-semibold">Timetable Studio</h2>
        </div>
        <div className="flex items-center gap-2">
          <Select
            placeholder="Academic Year"
            value={academicYearId?.toString()}
            onChange={(v) => setAcademicYearId(parseInt(v))}
          >
            {academicYears.map((y) => (
              <select.Option key={y.id} value={y.id.toString()}>
                {y.name}
              </select.Option>
            ))}
          </Select>
          <Button color="primary">
            <LayoutDashboard className="h-4 w-4 mr-2" />
            Add Entry
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="w-20 border p-2 font-medium text-left">{''}</th>
              {DAYS.map((d) => (
                <th key={d.value} className="border p-2 font-medium text-center bg-gray-100">
                  {d.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!timeSlots ? (
              <tr>
                <td colSpan={7} className="p-8 text-center">
                  Loading time slots...
                </td>
              </tr>
            ) : (
              gridEntries.map((row, i) => (
                <tr key={i}>
                  <td className="border p-2 font-medium text-gray-600">
                    {timeSlots[i]?.name || `Slot ${i + 1}`}
                  </td>
                  {row.map((entry, day) => (
                    <td key={day} className="border p-1">
                      <TimetableCell
                        entry={entry}
                        onEdit={handleEdit}
                        onConflictCheck={handleConflictCheck}
                      />
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      {selectedEntry && (
        <Modal open={!!selectedEntry} onClose={() => setSelectedEntry(null)} title="Edit Timetable Entry">
          <Form>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Subject</label>
                <Input value={selectedEntry.subject_name || ''} readOnly />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Teacher</label>
                <Input value={selectedEntry.teacher_name || ''} readOnly />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Room</label>
                <Input value={selectedEntry.room_name || ''} readOnly />
              </div>
            </div>
          </Form>
        </Modal>
      )}

      {/* Conflict Modal */}
      {conflicts?.has_conflicts && (
        <ConflictOverlay
          conflicts={conflicts.conflicts.map(c => ({
            type: c.type,
            entry_id: c.conflicting_entry_id,
            description: formatConflictExplanation(c),
          }))}
          onClose={() => setConflicts(null)}
        />
      )}
    </div>
  );
}

export default function TimetableStudioPage() {
  const { classId, entryId } = useParams();
  const [isCreateMode, setIsCreateMode] = useState(false);

  if (entryId) {
    // Would navigate to edit page for specific entry
    return <div>Edit Entry Page would go here</div>;
  }

  return <WeeklyGrid />;
}