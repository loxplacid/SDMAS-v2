const Database = require('../implementations/database');
const StudentRepository = require('../implementations/student-repository');
const StudentService = require('../implementations/student-service');
const AcademicStructureRepository = require('../implementations/academic-structure-repository');
const AcademicStructureService = require('../implementations/academic-structure-service');
const AttendanceRepository = require('../implementations/attendance-repository');
const AttendanceService = require('../implementations/attendance-service');

describe('AttendanceService', () => {
  let db;
  let studentRepository;
  let studentService;
  let academicStructureRepository;
  let academicStructureService;
  let attendanceRepository;
  let attendanceService;

  let academicYear;
  let classObj;
  let section;
  let student1;
  let student2;

  function createTables() {
    db.query(`CREATE TABLE IF NOT EXISTS students (
      id INT PRIMARY KEY AUTO_INCREMENT,
      first_name VARCHAR(100) NOT NULL,
      last_name VARCHAR(100) NOT NULL,
      student_number VARCHAR(50) UNIQUE NOT NULL,
      email VARCHAR(255),
      date_of_birth VARCHAR(10),
      status VARCHAR(20) DEFAULT 'active',
      created_at VARCHAR(50),
      updated_at VARCHAR(50)
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS academic_years (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      start_date VARCHAR(10),
      end_date VARCHAR(10),
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS classes (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      academic_year_id INT,
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS sections (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      class_id INT,
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS enrollments (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      academic_year_id INT NOT NULL,
      class_id INT,
      section_id INT,
      status VARCHAR(20) DEFAULT 'active',
      enrolled_at VARCHAR(50)
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS attendance_records (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      academic_year_id INT NOT NULL,
      class_id INT NOT NULL,
      section_id INT NOT NULL,
      attendance_date VARCHAR(10) NOT NULL,
      status VARCHAR(20) NOT NULL,
      notes TEXT,
      recorded_at VARCHAR(50),
      updated_at VARCHAR(50)
    )`);
  }

  function seedData() {
    db.query('INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)',
      ['2026-2027', '2026-01-01', '2026-12-31', 'active']);
    academicYear = db.query('SELECT * FROM academic_years WHERE name = ?', ['2026-2027']).rows[0];

    db.query('INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)',
      ['Grade 10', academicYear.id, 'active']);
    classObj = db.query('SELECT * FROM classes WHERE name = ?', ['Grade 10']).rows[0];

    db.query('INSERT INTO sections (name, class_id, status) VALUES (?, ?, ?)',
      ['Section A', classObj.id, 'active']);
    section = db.query('SELECT * FROM sections WHERE name = ?', ['Section A']).rows[0];

    student1 = studentService.createStudent({
      first_name: 'John', last_name: 'Doe', student_number: 'STU001'
    });
    student2 = studentService.createStudent({
      first_name: 'Jane', last_name: 'Smith', student_number: 'STU002'
    });

    studentService.enrollStudent(student1.id, {
      academic_year_id: academicYear.id,
      class_id: classObj.id,
      section_id: section.id
    });
    studentService.enrollStudent(student2.id, {
      academic_year_id: academicYear.id,
      class_id: classObj.id,
      section_id: section.id
    });
  }

  beforeEach(() => {
    db = new Database();
    db.connect();
    createTables();
    studentRepository = new StudentRepository(db);
    studentService = new StudentService(studentRepository);
    academicStructureRepository = new AcademicStructureRepository(db);
    academicStructureService = new AcademicStructureService(academicStructureRepository);
    attendanceRepository = new AttendanceRepository(db);
    attendanceService = new AttendanceService(attendanceRepository, studentRepository, academicStructureRepository);
    seedData();
  });

  afterEach(() => {
    db.disconnect();
  });

  describe('recordAttendance', () => {
    test('should record Present attendance', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      expect(record).toBeDefined();
      expect(record.id).toBe(1);
      expect(record.student_id).toBe(student1.id);
      expect(record.status).toBe('present');
      expect(record.attendance_date).toBe('2026-03-15');
      expect(record.recorded_at).toBeDefined();
      expect(record.updated_at).toBeDefined();
    });

    test('should record Absent attendance', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      });

      expect(record.status).toBe('absent');
    });

    test('should record Late attendance', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'late'
      });

      expect(record.status).toBe('late');
    });

    test('should record Excused attendance', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'excused'
      });

      expect(record.status).toBe('excused');
    });

    test('should throw for invalid status', () => {
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'invalid'
      })).toThrow('Invalid attendance status');
    });

    test('should throw for non-existent student', () => {
      expect(() => attendanceService.recordAttendance({
        student_id: 999,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow('Student with id 999 not found');
    });

    test('should throw for inactive student', () => {
      studentService.deactivateStudent(student1.id);
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow('Cannot record attendance for an inactive student');
    });

    test('should throw for non-existent academic year', () => {
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: 999,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow('Academic year with id 999 not found');
    });

    test('should throw for non-existent class', () => {
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: 999,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow('Class with id 999 not found');
    });

    test('should throw for non-existent section', () => {
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: 999,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow('Section with id 999 not found');
    });

    test('should throw for student not enrolled in section', () => {
      const otherSection = db.query('INSERT INTO sections (name, class_id, status) VALUES (?, ?, ?)',
        ['Section B', classObj.id, 'active']);
      const otherSectionRow = db.query('SELECT * FROM sections WHERE name = ?', ['Section B']).rows[0];

      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: otherSectionRow.id,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow(`Student ${student1.id} is not enrolled in section ${otherSectionRow.id}`);
    });

    test('should throw for empty date', () => {
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '',
        status: 'present'
      })).toThrow('Attendance date is required');
    });

    test('should accept notes', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent',
        notes: 'Sick leave'
      });

      expect(record.notes).toBe('Sick leave');
    });

    test('should set notes to null when not provided', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      expect(record.notes).toBeNull();
    });
  });

  describe('duplicate protection', () => {
    test('should reject duplicate attendance for same student/date/section', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      })).toThrow('Attendance record already exists');
    });

    test('should allow attendance for same student on different dates', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      const record2 = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-16',
        status: 'absent'
      });

      expect(record2.status).toBe('absent');
      expect(record2.attendance_date).toBe('2026-03-16');
    });

    test('should allow attendance for different students on same date', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      const record2 = attendanceService.recordAttendance({
        student_id: student2.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      });

      expect(record2.status).toBe('absent');
    });

    test('should allow correction through update path', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      });

      const corrected = attendanceService.updateAttendance(record.id, { status: 'present' });
      expect(corrected.status).toBe('present');

      const duplicateAttempt = attendanceService.attendanceRepository.findDuplicate(
        student1.id, '2026-03-15', section.id
      );
      expect(duplicateAttempt).toBeDefined();
      expect(duplicateAttempt.id).toBe(record.id);
      expect(duplicateAttempt.status).toBe('present');
    });
  });

  describe('getAttendance', () => {
    test('should retrieve attendance record by id', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      const found = attendanceService.getAttendance(record.id);
      expect(found.id).toBe(record.id);
      expect(found.status).toBe('present');
    });

    test('should throw for non-existent record', () => {
      expect(() => attendanceService.getAttendance(999))
        .toThrow('Attendance record with id 999 not found');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => attendanceService.getAttendance(null)).toThrow('Attendance record id is required');
      expect(() => attendanceService.getAttendance(undefined)).toThrow('Attendance record id is required');
    });
  });

  describe('updateAttendance', () => {
    test('should correct status from absent to present', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      });

      const updated = attendanceService.updateAttendance(record.id, { status: 'present' });
      expect(updated.status).toBe('present');
    });

    test('should correct status from late to present', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'late'
      });

      const updated = attendanceService.updateAttendance(record.id, { status: 'present' });
      expect(updated.status).toBe('present');
    });

    test('should correct status from present to excused', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      const updated = attendanceService.updateAttendance(record.id, { status: 'excused' });
      expect(updated.status).toBe('excused');
    });

    test('should update notes during correction', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent',
        notes: 'Original note'
      });

      const updated = attendanceService.updateAttendance(record.id, {
        status: 'present',
        notes: 'Corrected - was present'
      });
      expect(updated.status).toBe('present');
      expect(updated.notes).toBe('Corrected - was present');
    });

    test('should throw for non-existent record', () => {
      expect(() => attendanceService.updateAttendance(999, { status: 'present' }))
        .toThrow('Attendance record with id 999 not found');
    });

    test('should throw for invalid status', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      expect(() => attendanceService.updateAttendance(record.id, { status: 'invalid' }))
        .toThrow('Invalid attendance status');
    });

    test('should track updated_at changes', () => {
      const record = attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      const updated = attendanceService.updateAttendance(record.id, { status: 'absent' });
      expect(updated.updated_at).toBeDefined();
      expect(new Date(updated.updated_at).getTime()).toBeGreaterThanOrEqual(new Date(record.updated_at).getTime());
    });
  });

  describe('getStudentAttendance', () => {
    test('should retrieve attendance for a student', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-16',
        status: 'absent'
      });

      const records = attendanceService.getStudentAttendance(student1.id);
      expect(records).toHaveLength(2);
    });

    test('should filter by status', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-16',
        status: 'absent'
      });

      const records = attendanceService.getStudentAttendance(student1.id, { status: 'present' });
      expect(records).toHaveLength(1);
      expect(records[0].status).toBe('present');
    });

    test('should filter by date range', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-14',
        status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      });
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-16',
        status: 'present'
      });

      const records = attendanceService.getStudentAttendance(student1.id, {
        start_date: '2026-03-15',
        end_date: '2026-03-16'
      });
      expect(records).toHaveLength(2);
    });

    test('should return empty array when no records exist', () => {
      const records = attendanceService.getStudentAttendance(student1.id);
      expect(records).toEqual([]);
    });

    test('should throw for invalid status filter', () => {
      expect(() => attendanceService.getStudentAttendance(student1.id, { status: 'invalid' }))
        .toThrow('Invalid attendance status filter');
    });
  });

  describe('getSectionAttendance', () => {
    test('should retrieve attendance for a section on a date', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student2.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      });

      const records = attendanceService.getSectionAttendance(section.id, '2026-03-15');
      expect(records).toHaveLength(2);
    });

    test('should return empty array for date with no records', () => {
      const records = attendanceService.getSectionAttendance(section.id, '2026-03-15');
      expect(records).toEqual([]);
    });
  });

  describe('recordDailyAttendance', () => {
    test('should atomically record attendance for multiple students', () => {
      const records = attendanceService.recordDailyAttendance(section.id, '2026-03-15', [
        { student_id: student1.id, status: 'present' },
        { student_id: student2.id, status: 'absent' }
      ]);

      expect(records).toHaveLength(2);
      expect(records[0].status).toBe('present');
      expect(records[1].status).toBe('absent');
      expect(records[0].attendance_date).toBe('2026-03-15');
      expect(records[1].attendance_date).toBe('2026-03-15');
    });

    test('should rollback on failure', () => {
      expect(() => attendanceService.recordDailyAttendance(section.id, '2026-03-15', [
        { student_id: student1.id, status: 'present' },
        { student_id: 999, status: 'absent' }
      ])).toThrow('Student with id 999 not found');

      const records = attendanceService.getSectionAttendance(section.id, '2026-03-15');
      expect(records).toHaveLength(0);
    });

    test('should rollback on duplicate', () => {
      attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'present'
      });

      expect(() => attendanceService.recordDailyAttendance(section.id, '2026-03-15', [
        { student_id: student1.id, status: 'present' },
        { student_id: student2.id, status: 'absent' }
      ])).toThrow('Attendance record already exists');

      const records = attendanceService.getSectionAttendance(section.id, '2026-03-15');
      expect(records).toHaveLength(1);
      expect(records[0].student_id).toBe(student1.id);
    });

    test('should throw for empty records array', () => {
      expect(() => attendanceService.recordDailyAttendance(section.id, '2026-03-15', []))
        .toThrow('Attendance records must be a non-empty array');
    });

    test('should throw for non-array records', () => {
      expect(() => attendanceService.recordDailyAttendance(section.id, '2026-03-15', 'not-an-array'))
        .toThrow('Attendance records must be a non-empty array');
    });
  });

  describe('getStudentSummary', () => {
    test('should calculate correct summary for known attendance history', () => {
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-16', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-17', status: 'absent'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-18', status: 'late'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-19', status: 'excused'
      });

      const summary = attendanceService.getStudentSummary(student1.id, '2026-03-15', '2026-03-19');

      expect(summary.total).toBe(5);
      expect(summary.present).toBe(2);
      expect(summary.absent).toBe(1);
      expect(summary.late).toBe(1);
      expect(summary.excused).toBe(1);
    });

    test('should calculate percentage as present/total*100', () => {
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-16', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-17', status: 'absent'
      });

      const summary = attendanceService.getStudentSummary(student1.id, '2026-03-15', '2026-03-17');
      expect(summary.total).toBe(3);
      expect(summary.present).toBe(2);
      expect(summary.percentage).toBe(66.67);
    });

    test('should return zero percentage when no records', () => {
      const summary = attendanceService.getStudentSummary(student1.id, '2026-03-15', '2026-03-17');
      expect(summary.total).toBe(0);
      expect(summary.present).toBe(0);
      expect(summary.percentage).toBe(0);
    });

    test('should respect date range boundaries', () => {
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-14', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-16', status: 'absent'
      });
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-17', status: 'present'
      });

      const summary = attendanceService.getStudentSummary(student1.id, '2026-03-15', '2026-03-16');
      expect(summary.total).toBe(2);
      expect(summary.present).toBe(1);
      expect(summary.absent).toBe(1);
    });
  });

  describe('getSectionSummary', () => {
    test('should calculate aggregate counts for section on a date', () => {
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student2.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'absent'
      });

      const summary = attendanceService.getSectionSummary(section.id, '2026-03-15');

      expect(summary.total_students).toBe(2);
      expect(summary.present).toBe(1);
      expect(summary.absent).toBe(1);
      expect(summary.late).toBe(0);
      expect(summary.excused).toBe(0);
      expect(summary.total_marked).toBe(2);
    });

    test('should return zeros when no attendance recorded', () => {
      const summary = attendanceService.getSectionSummary(section.id, '2026-03-15');

      expect(summary.total_students).toBe(2);
      expect(summary.present).toBe(0);
      expect(summary.absent).toBe(0);
      expect(summary.late).toBe(0);
      expect(summary.excused).toBe(0);
      expect(summary.total_marked).toBe(0);
      expect(summary.present_percentage).toBe(0);
    });

    test('should report present_percentage correctly', () => {
      attendanceService.recordAttendance({
        student_id: student1.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'present'
      });
      attendanceService.recordAttendance({
        student_id: student2.id, academic_year_id: academicYear.id,
        class_id: classObj.id, section_id: section.id,
        attendance_date: '2026-03-15', status: 'present'
      });

      const summary = attendanceService.getSectionSummary(section.id, '2026-03-15');
      expect(summary.present).toBe(2);
      expect(summary.present_percentage).toBe(100);
    });
  });

  describe('error propagation', () => {
    test('should propagate repository errors', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      brokenDb.query(`CREATE TABLE IF NOT EXISTS students (
        id INT PRIMARY KEY AUTO_INCREMENT,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        student_number VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255),
        date_of_birth VARCHAR(10),
        status VARCHAR(20) DEFAULT 'active',
        created_at VARCHAR(50),
        updated_at VARCHAR(50)
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS academic_years (
        id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
        start_date VARCHAR(10), end_date VARCHAR(10), status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS classes (
        id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
        academic_year_id INT, status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS sections (
        id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
        class_id INT, status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS enrollments (
        id INT PRIMARY KEY AUTO_INCREMENT, student_id INT NOT NULL,
        academic_year_id INT NOT NULL, class_id INT, section_id INT,
        status VARCHAR(20) DEFAULT 'active', enrolled_at VARCHAR(50)
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS attendance_records (
        id INT PRIMARY KEY AUTO_INCREMENT, student_id INT NOT NULL,
        academic_year_id INT NOT NULL, class_id INT NOT NULL, section_id INT NOT NULL,
        attendance_date VARCHAR(10) NOT NULL, status VARCHAR(20) NOT NULL,
        notes TEXT, recorded_at VARCHAR(50), updated_at VARCHAR(50)
      )`);

      brokenDb.query('INSERT INTO academic_years (name, status) VALUES (?, ?)', ['2026-2027', 'active']);
      brokenDb.query('INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)', ['Grade 10', 1, 'active']);
      brokenDb.query('INSERT INTO sections (name, class_id, status) VALUES (?, ?, ?)', ['Section A', 1, 'active']);
      brokenDb.query('INSERT INTO students (first_name, last_name, student_number, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        ['John', 'Doe', 'STU001', 'active', new Date().toISOString(), new Date().toISOString()]);
      brokenDb.query('INSERT INTO enrollments (student_id, academic_year_id, class_id, section_id, status, enrolled_at) VALUES (?, ?, ?, ?, ?, ?)',
        [1, 1, 1, 1, 'active', new Date().toISOString()]);

      const brokenRepo = new AttendanceRepository(brokenDb);
      const brokenStudentRepo = new StudentRepository(brokenDb);
      const brokenAcademicRepo = new AcademicStructureRepository(brokenDb);
      const brokenService = new AttendanceService(brokenRepo, brokenStudentRepo, brokenAcademicRepo);

      jest.spyOn(brokenRepo, 'save').mockImplementation(() => {
        throw new Error('Database connection lost');
      });

      expect(() => brokenService.recordAttendance({
        student_id: 1,
        academic_year_id: 1,
        class_id: 1,
        section_id: 1,
        attendance_date: '2026-03-15',
        status: 'present'
      })).toThrow('Database connection lost');
      brokenDb.disconnect();
    });
  });
});
