import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  useToast,
} from '../../components/ui';
import type { Room, RoomCreate, RoomUpdate, RoomPage } from '../../api/academic_ops/types';
import { useRooms } from '../../hooks/academic-ops';

export function RoomsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [roomTypeFilter, setRoomTypeFilter] = useState('');
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [formData, setFormData] = useState<RoomCreate>({
    name: '',
    code: '',
    room_type: '',
    capacity: 30,
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    data: rooms,
    loading: listLoading,
    error: listError,
    refresh,
  } = useRooms(20);

  const { showToast } = useToast();
  const navigate = useNavigate();

  // Validate form
  const validateForm = useCallback((data: RoomCreate) => {
    const errors: Record<string, string> = {};

    if (!data.name.trim()) errors.name = 'Name is required';
    if (!data.code.trim()) errors.code = 'Code is required';
    if (!data.room_type.trim()) errors.room_type = 'Room type is required';
    if (!data.capacity || data.capacity <= 0) errors.capacity = 'Valid capacity is required';

    return errors;
  }, []);

  // Create room
  const handleCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validateForm(formData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setLoading(true);
    setApiError(null);
    try {
      await createRoom(formData);
      setFormData({
        name: '',
        code: '',
        room_type: '',
        capacity: 30,
      });
      setFormErrors({});
      setShowCreateModal(false);
      refresh();
      showToast({ title: 'Room created successfully', status: 'success' });
    } catch (err: any) {
      setApiError(
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Failed to create room'
      );
    } finally {
      setLoading(false);
    }
  }, [formData, refresh, showToast]);

  // Update room
  const handleUpdate = useCallback(async (e: React.FormEvent) => {
    if (!selectedRoom) return;
    e.preventDefault();
    const errors = validateForm(formData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setLoading(true);
    setApiError(null);
    try {
      await updateRoom(selectedRoom.id, formData);
      setShowEditModal(false);
      refresh();
      showToast({ title: 'Room updated successfully', status: 'success' });
    } catch (err: any) {
      setApiError(
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Failed to update room'
      );
    } finally {
      setLoading(false);
    }
  }, [selectedRoom, formData, refresh, showToast]);

  // Delete room
  const handleDelete = useCallback(async () => {
    if (!selectedRoom) return;
    if (!window.confirm(`Delete room "${selectedRoom.name}"?`)) return;

    try {
      await deleteRoom(selectedRoom.id);
      setSelectedRoom(null);
      refresh();
      showToast({ title: 'Room deleted successfully', status: 'success' });
    } catch (err: any) {
      showToast({
        title: 'Failed to delete room',
        description:
          err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          'Unknown error',
        status: 'error',
      });
    }
  }, [selectedRoom, refresh, showToast]);

  // Open create modal
  const openCreateModal = () => {
    setFormData({
      name: '',
      code: '',
      room_type: '',
      capacity: 30,
    });
    setFormErrors({});
    setShowCreateModal(true);
  };

  // Open edit modal
  const openEditModal = (room: Room) => {
    setSelectedRoom(room);
    setFormData({
      name: room.name,
      code: room.code,
      room_type: room.room_type,
      capacity: room.capacity,
    });
    setFormErrors({});
    setShowEditModal(true);
  };

  // Filter rooms
  const filteredRooms = rooms?.filter((room) => {
    const matchesSearch =
      !searchTerm ||
      room.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      room.code.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = !statusFilter || room.status === statusFilter;
    const matchesType = !roomTypeFilter || room.room_type === roomTypeFilter;

    return matchesSearch && matchesStatus && matchesType;
  }) ?? [];

  // Define table columns
  const columns = [
    {
      accessorKey: 'name',
      header: 'Name',
    },
    {
      accessorKey: 'code',
      header: 'Code',
    },
    {
      accessorKey: 'room_type',
      header: 'Type',
    },
    {
      accessorKey: 'capacity',
      header: 'Capacity',
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }: { row: { original: Room } }) => (
        <StatusBadge variant={row.original.status === 'active' ? 'success' : 'secondary'}>
          {row.original.status}
        </StatusBadge>
      ),
    },
    {
      header: 'Actions',
      cell: ({ row }: { row: { original: Room } }) => (
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => openEditModal(row.original)}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            color="destructive"
            onClick={() => {
              setSelectedRow(row.original);
            }}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  if (listLoading) {
    return <div className="p-8 text-center">Loading rooms...</div>;
  }

  if (listError) {
    return (
      <Alert variant="destructive">
        Failed to load rooms: {listError}
      </Alert>
    );
  }

  return (
    <div className="flex-1 p-6">
      <PageHeader>
        <PageHeader.Title>Rooms Management</PageHeader.Title>
        <PageHeader.Description>
          Manage classrooms, laboratories, and other learning spaces
        </PageHeader.Description>
        <PageHeader.Action>
          <Button color="primary" onClick={openCreateModal}>
            Add Room
          </Button>
        </PageHeader.Action>
      </PageHeader>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium mb-1">Search</label>
          <Input
            placeholder="Search by name or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Status</label>
          <Select
            value={statusFilter}
            onChange={(v) => setStatusFilter(v)}
          >
            <select.Option value="">All</select.Option>
            <select.Option value="active">Active</select.Option>
            <select.Option value="inactive">Inactive</select.Option>
            <select.Option value="maintenance">Maintenance</select.Option>
          </Select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Room Type</label>
          <Select
            value={roomTypeFilter}
            onChange={(v) => setRoomTypeFilter(v)}
          >
            <select.Option value="">All</select.Option>
            <select.Option value="classroom">Classroom</select.Option>
            <select.Option value="laboratory">Laboratory</select.Option>
            <select.Option value="auditorium">Auditorium</select.Option>
            <select.Option value="library">Library</select.Option>
            <select.Option value="office">Office</select.Option>
          </Select>
        </div>
      </div>

      {/* Tables */}
      <Card>
        <Card.Body>
          {filteredRooms.length > 0 ? (
            <DataTable<Room>
              data={filteredRooms}
              columns={columns}
              getRowId={(row) => row.id}
              filterable
              emptyMessage="No rooms found"
              urlSync
              viewKey="rooms-management"
            />
          ) : (
            <div className="p-8 text-center">
              <p className="text-muted-foreground">No rooms found matching your criteria</p>
            </div>
          )}
        </Card.Body>
      </Card>

      {/* Create Modal */}
      <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} title="Create New Room">
        <Form onSubmit={handleCreate}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <Input
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Enter room name"
                aria-invalid={!!formErrors.name}
              />
              {formErrors.name && (
                <p className="text-xs text-destructive mt-1">{formErrors.name}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Code</label>
              <Input
                value={formData.code}
                onChange={(e) =>
                  setFormData({ ...formData, code: e.target.value })
                }
                placeholder="Enter room code (e.g., A-101)"
                aria-invalid={!!formErrors.code}
              />
              {formErrors.code && (
                <p className="text-xs text-destructive mt-1">{formErrors.code}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <Select
                value={formData.room_type}
                onChange={(e) => setFormData({ ...formData, room_type: e.target.value })}
                placeholder="Select room type"
                aria-invalid={!!formErrors.room_type}
              >
                <select.Option value="classroom">Classroom</select.Option>
                <select.Option value="laboratory">Laboratory</select.Option>
                <select.Option value="auditorium">Auditorium</select.Option>
                <select.Option value="library">Library</select.Option>
                <select.Option value="office">Office</select.Option>
                <select.Option value="gymnasium">Gymnasium</select.Option>
              </Select>
              {formErrors.room_type && (
                <p className="text-xs text-destructive mt-1">{formErrors.room_type}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Capacity</label>
              <Input
                type="number"
                value={formData.capacity?.toString() || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    capacity: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                placeholder="Enter capacity"
                aria-invalid={!!formErrors.capacity}
              />
              {formErrors.capacity && (
                <p className="text-xs text-destructive mt-1">{formErrors.capacity}</p>
              )}
            </div>
          </div>

          <div className="flex justify-end pt-4 space-x-3">
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button color="primary" type="submit" isLoading={loading}>
              Create Room
            </Button>
          </div>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal open={showEditModal} onClose={() => setShowEditModal(false)} title="Edit Room">
        <Form onSubmit={handleUpdate}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <Input
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Enter room name"
                aria-invalid={!!formErrors.name}
              />
              {formErrors.name && (
                <p className="text-xs text-destructive mt-1">{formErrors.name}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Code</label>
              <Input
                value={formData.code}
                onChange={(e) =>
                  setFormData({ ...formData, code: e.target.value })
                }
                placeholder="Enter room code"
                aria-invalid={!!formErrors.code}
              />
              {formErrors.code && (
                <p className="text-xs text-destructive mt-1">{formErrors.code}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <Select
                value={formData.room_type}
                onChange={(e) => setFormData({ ...formData, room_type: e.target.value })}
                placeholder="Select room type"
                aria-invalid={!!formErrors.room_type}
              >
                <select.Option value="classroom">Classroom</select.Option>
                <select.Option value="laboratory">Laboratory</select.Option>
                <select.Option value="auditorium">Auditorium</select.Option>
                <select.Option value="library">Library</select.Option>
                <select.Option value="office">Office</select.Option>
                <select.Option value="gymnasium">Gymnasium</select.Option>
              </Select>
              {formErrors.room_type && (
                <p className="text-xs text-destructive mt-1">{formErrors.room_type}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Capacity</label>
              <Input
                type="number"
                value={formData.capacity?.toString() || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    capacity: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                placeholder="Enter capacity"
                aria-invalid={!!formErrors.capacity}
              />
              {formErrors.capacity && (
                <p className="text-xs text-destructive mt-1">{formErrors.capacity}</p>
              )}
            </div>
          </div>

          <div className="flex justify-end pt-4 space-x-3">
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              Cancel
            </Button>
            <Button color="primary" type="submit" isLoading={loading}>
              Update Room
            </Button>
          </div>
        </Form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={!!selectedRoom}
        onClose={() => setSelectedRoom(null)}
        title="Delete Room"
      >
        <Card.Body className="py-6">
          <p className="mb-4">
            Are you sure you want to delete the room <strong>{selectedRoom?.name}</strong>?
          </p>
          <p className="text-muted-foreground mb-6">
            This action cannot be undone.
          </p>

          <div className="flex justify-end pt-4 space-x-3">
            <Button variant="outline" onClick={() => setSelectedRoom(null)}>
              Cancel
            </Button>
            <Button color="destructive" onClick={handleDelete} isLoading={loading}>
              Delete Room
            </Button>
          </div>
        </Card.Body>
      </Modal>
    </div>
  );
}