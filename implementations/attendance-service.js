const { IAttendanceService } = require('../interfaces');

const VALID_STATUSES = ['present', 'absent', 'late', 'excused'];

class AttendanceService extends IAttendanceService {
  constructor(attendanceRepository, studentRepository, academicStructureRepository) {
    super();
    this.attendanceRepository = attendanceRepository;
    this.studentRepository = studentRepository;
    this.academicStructureRepository = academicStructureRepository;
  }

  recordAttendance(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Attendance data must be a non-null object');
    }

    const student = this._validateStudent(data.student_id);
    const academicYear = this._validateAcademicYear(data.academic_year_id);
    const classObj = this._validateClass(data.class_id);
    const section = this._validateSection(data.section_id);

    if (!data.attendance_date || typeof data.attendance_date !== 'string' || data.attendance_date.trim().length === 0) {
      throw new Error('Attendance date is required');
    }

    if (!data.status || !VALID_STATUSES.includes(data.status)) {
      throw new Error(`Invalid attendance status. Must be one of: ${VALID_STATUSES.join(', ')}`);
    }

    this._validateStudentEnrolledInSection(student.id, section.id);

    const duplicate = this.attendanceRepository.findDuplicate(student.id, data.attendance_date, section.id);
    if (duplicate) {
      throw new Error(`Attendance record already exists for student ${student.id} on ${data.attendance_date} in section ${section.id}`);
    }

    const now = new Date().toISOString();
    return this.attendanceRepository.save({
      student_id: student.id,
      academic_year_id: academicYear.id,
      class_id: classObj.id,
      section_id: section.id,
      attendance_date: data.attendance_date,
      status: data.status,
      notes: data.notes || null,
      recorded_at: now,
      updated_at: now
    });
  }

  recordDailyAttendance(sectionId, date, records) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    if (!date || typeof date !== 'string' || date.trim().length === 0) {
      throw new Error('Date is required');
    }
    if (!Array.isArray(records) || records.length === 0) {
      throw new Error('Attendance records must be a non-empty array');
    }

    const section = this._validateSection(sectionId);
    const classObj = this.academicStructureRepository.findClassById(section.class_id);
    if (!classObj) {
      throw new Error(`Class with id ${section.class_id} not found`);
    }
    const academicYear = this._validateAcademicYear(classObj.academic_year_id);

    const savedRecords = [];
    this.attendanceRepository.transaction(() => {
      for (const record of records) {
        if (!record.student_id) {
          throw new Error('Student id is required for each attendance record');
        }
        if (!record.status || !VALID_STATUSES.includes(record.status)) {
          throw new Error(`Invalid attendance status for student ${record.student_id}. Must be one of: ${VALID_STATUSES.join(', ')}`);
        }

        const student = this._validateStudent(record.student_id);
        this._validateStudentEnrolledInSection(student.id, sectionId);

        const duplicate = this.attendanceRepository.findDuplicate(student.id, date, sectionId);
        if (duplicate) {
          throw new Error(`Attendance record already exists for student ${student.id} on ${date} in section ${sectionId}`);
        }

        const now = new Date().toISOString();
        const saved = this.attendanceRepository.save({
          student_id: student.id,
          academic_year_id: academicYear.id,
          class_id: classObj.id,
          section_id: sectionId,
          attendance_date: date,
          status: record.status,
          notes: record.notes || null,
          recorded_at: now,
          updated_at: now
        });
        savedRecords.push(saved);
      }
    });

    return savedRecords;
  }

  getAttendance(id) {
    if (id === undefined || id === null) {
      throw new Error('Attendance record id is required');
    }
    const record = this.attendanceRepository.findById(id);
    if (!record) {
      throw new Error(`Attendance record with id ${id} not found`);
    }
    return record;
  }

  updateAttendance(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Attendance record id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getAttendance(id);

    const updateData = {};
    if (data.status !== undefined) {
      if (!VALID_STATUSES.includes(data.status)) {
        throw new Error(`Invalid attendance status. Must be one of: ${VALID_STATUSES.join(', ')}`);
      }
      updateData.status = data.status;
    }
    if (data.notes !== undefined) {
      updateData.notes = data.notes;
    }

    if (Object.keys(updateData).length === 0) {
      throw new Error('No fields to update');
    }

    updateData.updated_at = new Date().toISOString();
    this.attendanceRepository.update(id, updateData);
    return this.attendanceRepository.findById(id);
  }

  getStudentAttendance(studentId, filters = {}) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }

    if (filters.academic_year_id) {
      this._validateAcademicYear(filters.academic_year_id);
    }
    if (filters.class_id) {
      this._validateClass(filters.class_id);
    }
    if (filters.section_id) {
      this._validateSection(filters.section_id);
    }
    if (filters.status && !VALID_STATUSES.includes(filters.status)) {
      throw new Error(`Invalid attendance status filter. Must be one of: ${VALID_STATUSES.join(', ')}`);
    }

    return this.attendanceRepository.findByStudentAndFilters(studentId, filters);
  }

  getSectionAttendance(sectionId, date) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    if (!date || typeof date !== 'string' || date.trim().length === 0) {
      throw new Error('Date is required');
    }

    return this.attendanceRepository.findBySectionAndDate(sectionId, date);
  }

  getStudentSummary(studentId, startDate, endDate) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    if (!startDate || !endDate) {
      throw new Error('Start date and end date are required');
    }

    const records = this.attendanceRepository.findByStudentAndDateRange(studentId, startDate, endDate);

    const summary = {
      student_id: studentId,
      start_date: startDate,
      end_date: endDate,
      total: records.length,
      present: 0,
      absent: 0,
      late: 0,
      excused: 0
    };

    for (const record of records) {
      if (VALID_STATUSES.includes(record.status)) {
        summary[record.status]++;
      }
    }

    summary.percentage = summary.total > 0
      ? Math.round((summary.present / summary.total) * 10000) / 100
      : 0;

    return summary;
  }

  getSectionSummary(sectionId, date) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    if (!date || typeof date !== 'string' || date.trim().length === 0) {
      throw new Error('Date is required');
    }

    const enrollments = this.studentRepository.findEnrollmentsBySection(sectionId);
    const records = this.attendanceRepository.findBySectionAndDate(sectionId, date);

    const summary = {
      section_id: sectionId,
      attendance_date: date,
      total_students: enrollments.length,
      present: 0,
      absent: 0,
      late: 0,
      excused: 0
    };

    for (const record of records) {
      if (VALID_STATUSES.includes(record.status)) {
        summary[record.status]++;
      }
    }

    summary.total_marked = records.length;
    summary.present_percentage = summary.total_marked > 0
      ? Math.round((summary.present / summary.total_marked) * 10000) / 100
      : 0;

    return summary;
  }

  _validateStudent(studentId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    const student = this.studentRepository.findById(studentId);
    if (!student) {
      throw new Error(`Student with id ${studentId} not found`);
    }
    if (student.status !== 'active') {
      throw new Error('Cannot record attendance for an inactive student');
    }
    return student;
  }

  _validateAcademicYear(academicYearId) {
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }
    const academicYear = this.academicStructureRepository.findAcademicYearById(academicYearId);
    if (!academicYear) {
      throw new Error(`Academic year with id ${academicYearId} not found`);
    }
    if (academicYear.status !== 'active') {
      throw new Error('Cannot record attendance for an inactive academic year');
    }
    return academicYear;
  }

  _validateClass(classId) {
    if (classId === undefined || classId === null) {
      throw new Error('Class id is required');
    }
    const classObj = this.academicStructureRepository.findClassById(classId);
    if (!classObj) {
      throw new Error(`Class with id ${classId} not found`);
    }
    if (classObj.status !== 'active') {
      throw new Error('Cannot record attendance for an inactive class');
    }
    return classObj;
  }

  _validateSection(sectionId) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    const section = this.academicStructureRepository.findSectionById(sectionId);
    if (!section) {
      throw new Error(`Section with id ${sectionId} not found`);
    }
    if (section.status !== 'active') {
      throw new Error('Cannot record attendance for an inactive section');
    }
    return section;
  }

  _validateStudentEnrolledInSection(studentId, sectionId) {
    const enrollments = this.studentRepository.findEnrollmentsBySection(sectionId);
    const enrolled = enrollments.some(e => e.student_id === studentId);
    if (!enrolled) {
      throw new Error(`Student ${studentId} is not enrolled in section ${sectionId}`);
    }
  }
}

module.exports = AttendanceService;
