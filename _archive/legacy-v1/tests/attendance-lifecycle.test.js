const Database = require('../implementations/database');
const StudentRepository = require('../implementations/student-repository');
const StudentService = require('../implementations/student-service');
const AcademicStructureRepository = require('../implementations/academic-structure-repository');
const AcademicStructureService = require('../implementations/academic-structure-service');
const AttendanceRepository = require('../implementations/attendance-repository');
const AttendanceService = require('../implementations/attendance-service');

describe('Attendance Lifecycle Integration', () => {
  let db;
  let studentRepository;
  let studentService;
  let academicStructureRepository;
  let academicStructureService;
  let attendanceRepository;
  let attendanceService;

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
  });

  afterEach(() => {
    db.disconnect();
  });

  describe('complete attendance workflow', () => {
    test('should execute full attendance lifecycle end-to-end', () => {
      // 1. CREATE Academic Year
      const year = academicStructureService.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });
      expect(year).toBeDefined();
      expect(year.status).toBe('active');

      // 2. CREATE Class/Grade
      const classObj = academicStructureService.createClass(year.id, {
        name: 'Grade 10'
      });
      expect(classObj).toBeDefined();
      expect(classObj.name).toBe('Grade 10');

      // 3. CREATE Section
      const section = academicStructureService.createSection(classObj.id, {
        name: 'Section A'
      });
      expect(section).toBeDefined();
      expect(section.name).toBe('Section A');

      // 4. CREATE Students
      const student1 = studentService.createStudent({
        first_name: 'Alice', last_name: 'Johnson', student_number: 'STU100'
      });
      const student2 = studentService.createStudent({
        first_name: 'Bob', last_name: 'Williams', student_number: 'STU101'
      });
      const student3 = studentService.createStudent({
        first_name: 'Carol', last_name: 'Brown', student_number: 'STU102'
      });
      expect(student1.status).toBe('active');
      expect(student2.status).toBe('active');
      expect(student3.status).toBe('active');

      // 5. ENROLL Students in section
      studentService.enrollStudent(student1.id, {
        academic_year_id: year.id,
        class_id: classObj.id,
        section_id: section.id
      });
      studentService.enrollStudent(student2.id, {
        academic_year_id: year.id,
        class_id: classObj.id,
        section_id: section.id
      });
      studentService.enrollStudent(student3.id, {
        academic_year_id: year.id,
        class_id: classObj.id,
        section_id: section.id
      });

      // Verify enrollments
      const enrollments = studentRepository.findEnrollmentsBySection(section.id);
      expect(enrollments).toHaveLength(3);

      // 6. RECORD daily attendance
      const dailyRecords = attendanceService.recordDailyAttendance(section.id, '2026-03-15', [
        { student_id: student1.id, status: 'present' },
        { student_id: student2.id, status: 'present' },
        { student_id: student3.id, status: 'absent' }
      ]);
      expect(dailyRecords).toHaveLength(3);

      // 7. RETRIEVE section attendance
      const sectionAttendance = attendanceService.getSectionAttendance(section.id, '2026-03-15');
      expect(sectionAttendance).toHaveLength(3);
      expect(sectionAttendance.find(r => r.student_id === student1.id).status).toBe('present');
      expect(sectionAttendance.find(r => r.student_id === student2.id).status).toBe('present');
      expect(sectionAttendance.find(r => r.student_id === student3.id).status).toBe('absent');

      // 8. CORRECT one student's attendance
      const student3Record = sectionAttendance.find(r => r.student_id === student3.id);
      const corrected = attendanceService.updateAttendance(student3Record.id, {
        status: 'present',
        notes: 'Was present, entered late but corrected'
      });
      expect(corrected.status).toBe('present');
      expect(corrected.notes).toBe('Was present, entered late but corrected');

      // 9. RECORD more attendance days
      attendanceService.recordDailyAttendance(section.id, '2026-03-16', [
        { student_id: student1.id, status: 'present' },
        { student_id: student2.id, status: 'absent' },
        { student_id: student3.id, status: 'present' }
      ]);
      attendanceService.recordDailyAttendance(section.id, '2026-03-17', [
        { student_id: student1.id, status: 'present' },
        { student_id: student2.id, status: 'late' },
        { student_id: student3.id, status: 'excused' }
      ]);
      attendanceService.recordDailyAttendance(section.id, '2026-03-18', [
        { student_id: student1.id, status: 'present' },
        { student_id: student2.id, status: 'present' },
        { student_id: student3.id, status: 'present' }
      ]);

      // 10. RETRIEVE student's attendance history
      const aliceAttendance = attendanceService.getStudentAttendance(student1.id);
      expect(aliceAttendance).toHaveLength(4);

      const bobAttendance = attendanceService.getStudentAttendance(student2.id);
      expect(bobAttendance).toHaveLength(4);

      const carolAttendance = attendanceService.getStudentAttendance(student3.id);
      expect(carolAttendance).toHaveLength(4);

      // 11. CALCULATE student attendance summary
      const aliceSummary = attendanceService.getStudentSummary(student1.id, '2026-03-15', '2026-03-18');
      expect(aliceSummary.total).toBe(4);
      expect(aliceSummary.present).toBe(4);
      expect(aliceSummary.absent).toBe(0);
      expect(aliceSummary.late).toBe(0);
      expect(aliceSummary.excused).toBe(0);
      expect(aliceSummary.percentage).toBe(100);

      const bobSummary = attendanceService.getStudentSummary(student2.id, '2026-03-15', '2026-03-18');
      expect(bobSummary.total).toBe(4);
      expect(bobSummary.present).toBe(2);
      expect(bobSummary.absent).toBe(1);
      expect(bobSummary.late).toBe(1);
      expect(bobSummary.excused).toBe(0);
      expect(bobSummary.percentage).toBe(50);

      const carolSummary = attendanceService.getStudentSummary(student3.id, '2026-03-15', '2026-03-18');
      expect(carolSummary.total).toBe(4);
      expect(carolSummary.present).toBe(3);
      expect(carolSummary.absent).toBe(0);
      expect(carolSummary.late).toBe(0);
      expect(carolSummary.excused).toBe(1);
      expect(carolSummary.percentage).toBe(75);

      // 12. CALCULATE section attendance summary for a date
      const sectionSummary = attendanceService.getSectionSummary(section.id, '2026-03-16');
      expect(sectionSummary.total_students).toBe(3);
      expect(sectionSummary.total_marked).toBe(3);
      expect(sectionSummary.present).toBe(2);
      expect(sectionSummary.absent).toBe(1);
      expect(sectionSummary.late).toBe(0);
      expect(sectionSummary.excused).toBe(0);

      // 13. VERIFY duplicate protection
      expect(() => attendanceService.recordAttendance({
        student_id: student1.id,
        academic_year_id: year.id,
        class_id: classObj.id,
        section_id: section.id,
        attendance_date: '2026-03-15',
        status: 'absent'
      })).toThrow('Attendance record already exists');

      // 14. VERIFY atomic rollback
      expect(() => attendanceService.recordDailyAttendance(section.id, '2026-03-19', [
        { student_id: student1.id, status: 'present' },
        { student_id: 999, status: 'absent' }
      ])).toThrow('Student with id 999 not found');

      const day19Records = attendanceService.getSectionAttendance(section.id, '2026-03-19');
      expect(day19Records).toHaveLength(0);

      // 15. VERIFY cross-domain integration
      const aliceEnrollments = studentRepository.findEnrollmentsByStudent(student1.id);
      expect(aliceEnrollments).toHaveLength(1);
      expect(aliceEnrollments[0].academic_year_id).toBe(year.id);
      expect(aliceEnrollments[0].section_id).toBe(section.id);

      const yearById = academicStructureService.getAcademicYear(year.id);
      expect(yearById.name).toBe('2026-2027');

      const sectionById = academicStructureService.getSection(section.id);
      expect(sectionById.name).toBe('Section A');
    });
  });
});
