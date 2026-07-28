const Database = require('../implementations/database');
const StudentRepository = require('../implementations/student-repository');
const StudentService = require('../implementations/student-service');
const AcademicStructureRepository = require('../implementations/academic-structure-repository');
const AcademicStructureService = require('../implementations/academic-structure-service');

describe('Academic Structure + Student Integration', () => {
  let db;
  let academicRepo;
  let academicService;
  let studentRepo;
  let studentService;

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
    db.query(`CREATE TABLE IF NOT EXISTS subjects (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      code VARCHAR(50) UNIQUE NOT NULL,
      description TEXT,
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
  }

  beforeEach(() => {
    db = new Database();
    db.connect();
    createTables();
    academicRepo = new AcademicStructureRepository(db);
    academicService = new AcademicStructureService(academicRepo);
    studentRepo = new StudentRepository(db);
    studentService = new StudentService(studentRepo);
  });

  afterEach(() => {
    db.disconnect();
  });

  describe('end-to-end academic structure and student workflow', () => {
    test('should build complete academic structure and enroll student', () => {
      // 1. CREATE Academic Year
      const year = academicService.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });
      expect(year.id).toBe(1);
      expect(year.status).toBe('active');

      // 2. CREATE a Subject
      const math = academicService.createSubject({ name: 'Mathematics', code: 'MATH101' });
      expect(math.status).toBe('active');

      // 3. CREATE a Class under the academic year
      const grade10 = academicService.createClass(year.id, { name: 'Grade 10' });
      expect(grade10.academic_year_id).toBe(year.id);
      expect(grade10.status).toBe('active');

      // 4. CREATE a second class
      const grade11 = academicService.createClass(year.id, { name: 'Grade 11' });
      expect(grade11.id).toBe(2);

      // 5. CREATE Sections under Grade 10
      const sectionA = academicService.createSection(grade10.id, { name: 'Section A' });
      expect(sectionA.class_id).toBe(grade10.id);

      const sectionB = academicService.createSection(grade10.id, { name: 'Section B' });
      expect(sectionB.id).toBe(2);

      // 6. LIST classes by year
      const classes = academicService.listClassesByAcademicYear(year.id);
      expect(classes).toHaveLength(2);

      // 7. LIST sections by class
      const sections = academicService.listSectionsByClass(grade10.id);
      expect(sections).toHaveLength(2);

      // 8. CREATE a Student
      const student = studentService.createStudent({
        first_name: 'Alice',
        last_name: 'Johnson',
        student_number: 'STU001',
        email: 'alice@school.com'
      });
      expect(student.status).toBe('active');

      // 9. ENROLL student in the academic year with class and section
      const enrollment = studentService.enrollStudent(student.id, {
        academic_year_id: year.id,
        class_id: grade10.id,
        section_id: sectionA.id
      });
      expect(enrollment.student_id).toBe(student.id);
      expect(enrollment.academic_year_id).toBe(year.id);
      expect(enrollment.class_id).toBe(grade10.id);
      expect(enrollment.section_id).toBe(sectionA.id);
      expect(enrollment.status).toBe('active');

      // 10. VERIFY student's enrollment via repository
      const enrollments = studentRepo.findEnrollmentsByStudent(student.id);
      expect(enrollments).toHaveLength(1);
      expect(enrollments[0].academic_year_id).toBe(year.id);

      // 11. UPDATE the class name and section name
      const updatedClass = academicService.updateClass(grade10.id, { name: 'Grade 10 Honors' });
      expect(updatedClass.name).toBe('Grade 10 Honors');

      const updatedSection = academicService.updateSection(sectionA.id, { name: 'Section A1' });
      expect(updatedSection.name).toBe('Section A1');

      // 12. DEACTIVATE then REACTIVATE the class
      const deactivatedClass = academicService.deactivateClass(grade10.id);
      expect(deactivatedClass.status).toBe('inactive');

      const reactivatedClass = academicService.activateClass(grade10.id);
      expect(reactivatedClass.status).toBe('active');

      // 13. DEACTIVATE then REACTIVATE a subject
      const deactivatedSubject = academicService.deactivateSubject(math.id);
      expect(deactivatedSubject.status).toBe('inactive');

      const reactivatedSubject = academicService.activateSubject(math.id);
      expect(reactivatedSubject.status).toBe('active');

      // 14. UPDATE term — create and update a term
      const term = academicService.createTerm(year.id, {
        name: 'Term 1',
        start_date: '2026-02-01',
        end_date: '2026-06-30'
      });
      const updatedTerm = academicService.updateTerm(term.id, { name: 'First Semester' });
      expect(updatedTerm.name).toBe('First Semester');
    });
  });

  describe('relationship validation', () => {
    test('should reject section under non-existent class', () => {
      expect(() => academicService.createSection(999, { name: 'Section X' }))
        .toThrow('Class with id 999 not found');
    });

    test('should reject class under non-existent academic year', () => {
      expect(() => academicService.createClass(999, { name: 'Grade 10' }))
        .toThrow('Academic year with id 999 not found');
    });

    test('should reject duplicate class name in same academic year', () => {
      const year = academicService.createAcademicYear({
        name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31'
      });
      academicService.createClass(year.id, { name: 'Grade 10' });
      expect(() => academicService.createClass(year.id, { name: 'Grade 10' }))
        .toThrow('already exists in this academic year');
    });

    test('should reject duplicate section name in same class', () => {
      const year = academicService.createAcademicYear({
        name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31'
      });
      const cls = academicService.createClass(year.id, { name: 'Grade 10' });
      academicService.createSection(cls.id, { name: 'Section A' });
      expect(() => academicService.createSection(cls.id, { name: 'Section A' }))
        .toThrow('already exists in this class');
    });

    test('should reject duplicate subject name', () => {
      academicService.createSubject({ name: 'Mathematics', code: 'MATH101' });
      expect(() => academicService.createSubject({ name: 'Mathematics', code: 'MATH102' }))
        .toThrow('already exists');
    });

    test('should reject duplicate subject code', () => {
      academicService.createSubject({ name: 'Mathematics', code: 'MATH101' });
      expect(() => academicService.createSubject({ name: 'Physics', code: 'MATH101' }))
        .toThrow('already exists');
    });

    test('should reject enrolling student in non-existent academic year', () => {
      const student = studentService.createStudent({
        first_name: 'Test', last_name: 'User', student_number: 'STU100'
      });
      expect(() => studentService.enrollStudent(student.id, { academic_year_id: 999 }))
        .toThrow('Academic year with id 999 not found');
    });

    test('should reject enrolling student in non-existent class', () => {
      const year = academicService.createAcademicYear({
        name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31'
      });
      const student = studentService.createStudent({
        first_name: 'Test', last_name: 'User', student_number: 'STU100'
      });
      expect(() => studentService.enrollStudent(student.id, {
        academic_year_id: year.id, class_id: 999
      })).toThrow('Class with id 999 not found');
    });

    test('should reject duplicate enrollment', () => {
      const year = academicService.createAcademicYear({
        name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31'
      });
      const student = studentService.createStudent({
        first_name: 'Test', last_name: 'User', student_number: 'STU100'
      });
      studentService.enrollStudent(student.id, { academic_year_id: year.id });
      expect(() => studentService.enrollStudent(student.id, { academic_year_id: year.id }))
        .toThrow('already enrolled');
    });
  });

  describe('error propagation', () => {
    test('should propagate repository errors for updateClass', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      const brokenRepo = new AcademicStructureRepository(brokenDb);
      const brokenService = new AcademicStructureService(brokenRepo);

      jest.spyOn(brokenRepo, 'findClassById').mockImplementation(() => {
        throw new Error('Database connection lost');
      });

      expect(() => brokenService.updateClass(1, { name: 'New' }))
        .toThrow('Database connection lost');
      brokenDb.disconnect();
    });

    test('should propagate repository errors for updateSection', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      const brokenRepo = new AcademicStructureRepository(brokenDb);
      const brokenService = new AcademicStructureService(brokenRepo);

      jest.spyOn(brokenRepo, 'findSectionById').mockImplementation(() => {
        throw new Error('Database connection lost');
      });

      expect(() => brokenService.updateSection(1, { name: 'New' }))
        .toThrow('Database connection lost');
      brokenDb.disconnect();
    });

    test('should propagate repository errors for updateSubject', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      const brokenRepo = new AcademicStructureRepository(brokenDb);
      const brokenService = new AcademicStructureService(brokenRepo);

      jest.spyOn(brokenRepo, 'findSubjectById').mockImplementation(() => {
        throw new Error('Database connection lost');
      });

      expect(() => brokenService.updateSubject(1, { name: 'New' }))
        .toThrow('Database connection lost');
      brokenDb.disconnect();
    });
  });
});
