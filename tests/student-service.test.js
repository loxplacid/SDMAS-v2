const Database = require('../implementations/database');
const StudentRepository = require('../implementations/student-repository');
const StudentService = require('../implementations/student-service');

describe('StudentService', () => {
  let db;
  let studentRepository;
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

  function seedAcademicYear(name, status) {
    db.query('INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)',
      [name, '2026-01-01', '2026-12-31', status || 'active']);
    const rows = db.query('SELECT * FROM academic_years WHERE name = ?', [name]).rows;
    return rows[0];
  }

  function seedClass(name, academicYearId, status) {
    db.query('INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)',
      [name, academicYearId, status || 'active']);
    const rows = db.query('SELECT * FROM classes WHERE name = ?', [name]).rows;
    return rows[0];
  }

  function seedSection(name, classId, status) {
    db.query('INSERT INTO sections (name, class_id, status) VALUES (?, ?, ?)',
      [name, classId, status || 'active']);
    const rows = db.query('SELECT * FROM sections WHERE name = ?', [name]).rows;
    return rows[0];
  }

  beforeEach(() => {
    db = new Database();
    db.connect();
    createTables();
    studentRepository = new StudentRepository(db);
    studentService = new StudentService(studentRepository);
  });

  afterEach(() => {
    db.disconnect();
  });

  describe('createStudent', () => {
    test('should create a student with valid data', () => {
      const student = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001',
        email: 'john@school.com'
      });

      expect(student).toBeDefined();
      expect(student.id).toBe(1);
      expect(student.first_name).toBe('John');
      expect(student.last_name).toBe('Doe');
      expect(student.student_number).toBe('STU001');
      expect(student.email).toBe('john@school.com');
      expect(student.status).toBe('active');
      expect(student.created_at).toBeDefined();
      expect(student.updated_at).toBeDefined();
    });

    test('should set default status to active', () => {
      const student = studentService.createStudent({
        first_name: 'Jane',
        last_name: 'Smith',
        student_number: 'STU002'
      });

      expect(student.status).toBe('active');
    });

    test('should throw when data is null or undefined', () => {
      expect(() => studentService.createStudent(null)).toThrow('Student data must be a non-null object');
      expect(() => studentService.createStudent(undefined)).toThrow('Student data must be a non-null object');
    });

    test('should throw when data is an array', () => {
      expect(() => studentService.createStudent(['a', 'b'])).toThrow('Student data must be a non-null object');
    });

    test('should throw when first_name is missing', () => {
      expect(() => studentService.createStudent({
        last_name: 'Doe',
        student_number: 'STU003'
      })).toThrow('First name is required');
    });

    test('should throw when first_name is empty', () => {
      expect(() => studentService.createStudent({
        first_name: '',
        last_name: 'Doe',
        student_number: 'STU003'
      })).toThrow('First name is required');
    });

    test('should throw when last_name is missing', () => {
      expect(() => studentService.createStudent({
        first_name: 'John',
        student_number: 'STU004'
      })).toThrow('Last name is required');
    });

    test('should throw when student_number is missing', () => {
      expect(() => studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe'
      })).toThrow('Student number is required');
    });

    test('should throw when email format is invalid', () => {
      expect(() => studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU005',
        email: 'not-an-email'
      })).toThrow('Invalid email format');
    });

    test('should accept null email', () => {
      const student = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU006',
        email: null
      });
      expect(student.email).toBeNull();
    });

    test('should throw when student_number already exists', () => {
      studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      expect(() => studentService.createStudent({
        first_name: 'Jane',
        last_name: 'Smith',
        student_number: 'STU001'
      })).toThrow('Student with number STU001 already exists');
    });
  });

  describe('getStudent', () => {
    test('should return a student by id', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      const found = studentService.getStudent(created.id);
      expect(found.id).toBe(created.id);
      expect(found.first_name).toBe('John');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => studentService.getStudent(null)).toThrow('Student id is required');
      expect(() => studentService.getStudent(undefined)).toThrow('Student id is required');
    });

    test('should throw when student is not found', () => {
      expect(() => studentService.getStudent(999)).toThrow('Student with id 999 not found');
    });
  });

  describe('findByStudentNumber', () => {
    test('should find a student by student number', () => {
      studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      const found = studentService.findByStudentNumber('STU001');
      expect(found.first_name).toBe('John');
      expect(found.student_number).toBe('STU001');
    });

    test('should throw when student number is not provided', () => {
      expect(() => studentService.findByStudentNumber()).toThrow('Student number is required');
      expect(() => studentService.findByStudentNumber('')).toThrow('Student number is required');
    });

    test('should throw when student is not found by number', () => {
      expect(() => studentService.findByStudentNumber('NONEXISTENT'))
        .toThrow('Student with number NONEXISTENT not found');
    });
  });

  describe('updateStudent', () => {
    test('should update student information', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001',
        email: 'john@old.com'
      });

      const updated = studentService.updateStudent(created.id, {
        first_name: 'Jonathan',
        email: 'jonathan@school.com'
      });

      expect(updated.first_name).toBe('Jonathan');
      expect(updated.last_name).toBe('Doe');
      expect(updated.email).toBe('jonathan@school.com');
      expect(updated.student_number).toBe('STU001');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => studentService.updateStudent(null, { first_name: 'John' }))
        .toThrow('Student id is required');
    });

    test('should throw when data is null or undefined', () => {
      expect(() => studentService.updateStudent(1, null))
        .toThrow('Update data must be a non-null object');
    });

    test('should throw when student is not found', () => {
      expect(() => studentService.updateStudent(999, { first_name: 'Ghost' }))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when updating student_number', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      expect(() => studentService.updateStudent(created.id, { student_number: 'NEWNUM' }))
        .toThrow('Student number cannot be changed');
    });

    test('should throw when first_name is set to empty', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      expect(() => studentService.updateStudent(created.id, { first_name: '' }))
        .toThrow('First name cannot be empty');
    });

    test('should validate email format on update', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      expect(() => studentService.updateStudent(created.id, { email: 'bad' }))
        .toThrow('Invalid email format');
    });

    test('should reject invalid status value', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      expect(() => studentService.updateStudent(created.id, { status: 'invalid' }))
        .toThrow('Invalid status value');
    });
  });

  describe('deactivateStudent', () => {
    test('should deactivate an active student', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      const deactivated = studentService.deactivateStudent(created.id);
      expect(deactivated.status).toBe('inactive');
    });

    test('should throw when student is already inactive', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      studentService.deactivateStudent(created.id);
      expect(() => studentService.deactivateStudent(created.id))
        .toThrow('is already inactive');
    });

    test('should throw for non-existent student', () => {
      expect(() => studentService.deactivateStudent(999))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => studentService.deactivateStudent(null)).toThrow('Student id is required');
      expect(() => studentService.deactivateStudent(undefined)).toThrow('Student id is required');
    });
  });

  describe('reactivateStudent', () => {
    test('should reactivate an inactive student', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      studentService.deactivateStudent(created.id);
      const reactivated = studentService.reactivateStudent(created.id);
      expect(reactivated.status).toBe('active');
    });

    test('should throw when reactivating an already active student', () => {
      const created = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });

      expect(() => studentService.reactivateStudent(created.id))
        .toThrow('is already active');
    });

    test('should throw for non-existent student', () => {
      expect(() => studentService.reactivateStudent(999))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => studentService.reactivateStudent(null)).toThrow('Student id is required');
      expect(() => studentService.reactivateStudent(undefined)).toThrow('Student id is required');
    });

    test('should allow deactivate → reactivate → deactivate cycle', () => {
      const created = studentService.createStudent({
        first_name: 'Cycle',
        last_name: 'Test',
        student_number: 'STU002'
      });

      studentService.deactivateStudent(created.id);
      expect(studentService.getStudent(created.id).status).toBe('inactive');

      studentService.reactivateStudent(created.id);
      expect(studentService.getStudent(created.id).status).toBe('active');

      studentService.deactivateStudent(created.id);
      expect(studentService.getStudent(created.id).status).toBe('inactive');
    });
  });

  describe('listStudents', () => {
    test('should list all students', () => {
      studentService.createStudent({ first_name: 'John', last_name: 'Doe', student_number: 'STU001' });
      studentService.createStudent({ first_name: 'Jane', last_name: 'Smith', student_number: 'STU002' });

      const students = studentService.listStudents();
      expect(students).toHaveLength(2);
    });

    test('should filter students by status', () => {
      const s1 = studentService.createStudent({ first_name: 'John', last_name: 'Doe', student_number: 'STU001' });
      const s2 = studentService.createStudent({ first_name: 'Jane', last_name: 'Smith', student_number: 'STU002' });
      expect(s1.id).toBe(1);
      expect(s2.id).toBe(2);

      const allRows = db.query('SELECT * FROM students').rows;
      expect(allRows).toHaveLength(2);
      expect(allRows[0].id).toBe(1);
      expect(allRows[1].id).toBe(2);

      studentService.deactivateStudent(s1.id);

      const inactiveResult = db.query('SELECT * FROM students WHERE id = ?', [s1.id]).rows;
      expect(inactiveResult).toHaveLength(1);
      expect(inactiveResult[0].status).toBe('inactive');

      const activeStudents = studentService.listStudents({ status: 'active' });
      expect(activeStudents).toHaveLength(1);
      expect(activeStudents[0].first_name).toBe('Jane');

      const inactiveStudents = studentService.listStudents({ status: 'inactive' });
      expect(inactiveStudents).toHaveLength(1);
      expect(inactiveStudents[0].first_name).toBe('John');
    });

    test('should throw for invalid status filter', () => {
      expect(() => studentService.listStudents({ status: 'bogus' }))
        .toThrow('Invalid status filter');
    });

    test('should return empty array when no students exist', () => {
      const students = studentService.listStudents();
      expect(students).toEqual([]);
    });
  });

  describe('searchStudents', () => {
    test('should search students by name', () => {
      studentService.createStudent({ first_name: 'John', last_name: 'Doe', student_number: 'STU001' });
      studentService.createStudent({ first_name: 'Jane', last_name: 'Smith', student_number: 'STU002' });
      studentService.createStudent({ first_name: 'Alice', last_name: 'Jones', student_number: 'STU003' });

      const results = studentService.searchStudents('john');
      expect(results).toHaveLength(1);
      expect(results[0].first_name).toBe('John');
    });

    test('should search by student number', () => {
      studentService.createStudent({ first_name: 'John', last_name: 'Doe', student_number: 'STU001' });
      studentService.createStudent({ first_name: 'Jane', last_name: 'Smith', student_number: 'STU002' });

      const results = studentService.searchStudents('STU002');
      expect(results).toHaveLength(1);
      expect(results[0].student_number).toBe('STU002');
    });

    test('should search by email', () => {
      studentService.createStudent({ first_name: 'John', last_name: 'Doe', student_number: 'STU001', email: 'john@school.com' });
      studentService.createStudent({ first_name: 'Jane', last_name: 'Smith', student_number: 'STU002', email: 'jane@school.com' });

      const results = studentService.searchStudents('jane@school.com');
      expect(results).toHaveLength(1);
      expect(results[0].email).toBe('jane@school.com');
    });

    test('should throw when query is empty', () => {
      expect(() => studentService.searchStudents('')).toThrow('Search query is required');
      expect(() => studentService.searchStudents('   ')).toThrow('Search query is required');
    });

    test('should return empty array for no matches', () => {
      studentService.createStudent({ first_name: 'John', last_name: 'Doe', student_number: 'STU001' });

      const results = studentService.searchStudents('zzzzz');
      expect(results).toEqual([]);
    });
  });

  describe('enrollStudent', () => {
    let student;
    let academicYear;
    let classObj;
    let section;

    beforeEach(() => {
      student = studentService.createStudent({
        first_name: 'John',
        last_name: 'Doe',
        student_number: 'STU001'
      });
      academicYear = seedAcademicYear('2026-2027', 'active');
      classObj = seedClass('Grade 10', academicYear.id, 'active');
      section = seedSection('Section A', classObj.id, 'active');
    });

    test('should enroll a student in an academic year', () => {
      const enrollment = studentService.enrollStudent(student.id, {
        academic_year_id: academicYear.id
      });

      expect(enrollment).toBeDefined();
      expect(enrollment.student_id).toBe(student.id);
      expect(enrollment.academic_year_id).toBe(academicYear.id);
      expect(enrollment.status).toBe('active');
      expect(enrollment.enrolled_at).toBeDefined();
    });

    test('should enroll a student in an academic year with class and section', () => {
      const enrollment = studentService.enrollStudent(student.id, {
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        section_id: section.id
      });

      expect(enrollment.class_id).toBe(classObj.id);
      expect(enrollment.section_id).toBe(section.id);
    });

    test('should throw when student id is null or undefined', () => {
      expect(() => studentService.enrollStudent(null, { academic_year_id: 1 }))
        .toThrow('Student id is required');
    });

    test('should throw when student does not exist', () => {
      expect(() => studentService.enrollStudent(999, { academic_year_id: 1 }))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when enrolling an inactive student', () => {
      studentService.deactivateStudent(student.id);

      expect(() => studentService.enrollStudent(student.id, { academic_year_id: academicYear.id }))
        .toThrow('Cannot enroll an inactive student');
    });

    test('should throw when academic year id is missing', () => {
      expect(() => studentService.enrollStudent(student.id, {}))
        .toThrow('Academic year id is required');
    });

    test('should throw when academic year does not exist', () => {
      expect(() => studentService.enrollStudent(student.id, { academic_year_id: 999 }))
        .toThrow('Academic year with id 999 not found');
    });

    test('should throw when enrolling in an inactive academic year', () => {
      db.query('INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)',
        ['2025-2026', '2026-01-01', '2026-12-31', 'inactive']);
      const inactiveYear = db.query('SELECT * FROM academic_years WHERE name = ?', ['2025-2026']).rows[0];

      expect(() => studentService.enrollStudent(student.id, { academic_year_id: inactiveYear.id }))
        .toThrow('Cannot enroll in an inactive academic year');
    });

    test('should throw when class does not exist', () => {
      expect(() => studentService.enrollStudent(student.id, {
        academic_year_id: academicYear.id,
        class_id: 999
      })).toThrow('Class with id 999 not found');
    });

    test('should throw when class is inactive', () => {
      db.query('INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)',
        ['Old Class', academicYear.id, 'inactive']);
      const inactiveClass = db.query('SELECT * FROM classes WHERE name = ?', ['Old Class']).rows[0];

      expect(() => studentService.enrollStudent(student.id, {
        academic_year_id: academicYear.id,
        class_id: inactiveClass.id
      })).toThrow('Cannot enroll in an inactive class');
    });

    test('should throw when section does not exist', () => {
      expect(() => studentService.enrollStudent(student.id, {
        academic_year_id: academicYear.id,
        section_id: 999
      })).toThrow('Section with id 999 not found');
    });

    test('should throw when section is inactive', () => {
      db.query('INSERT INTO sections (name, class_id, status) VALUES (?, ?, ?)',
        ['Old Section', classObj.id, 'inactive']);
      const inactiveSection = db.query('SELECT * FROM sections WHERE name = ?', ['Old Section']).rows[0];

      expect(() => studentService.enrollStudent(student.id, {
        academic_year_id: academicYear.id,
        section_id: inactiveSection.id
      })).toThrow('Cannot enroll in an inactive section');
    });

    test('should throw on duplicate enrollment', () => {
      studentService.enrollStudent(student.id, { academic_year_id: academicYear.id });

      expect(() => studentService.enrollStudent(student.id, { academic_year_id: academicYear.id }))
        .toThrow('is already enrolled');
    });

    test('should allow enrollment in different academic years', () => {
      db.query('INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)',
        ['2027-2028', '2026-01-01', '2026-12-31', 'active']);
      const year2 = db.query('SELECT * FROM academic_years WHERE name = ?', ['2027-2028']).rows[0];

      studentService.enrollStudent(student.id, { academic_year_id: academicYear.id });
      const enrollment2 = studentService.enrollStudent(student.id, { academic_year_id: year2.id });

      expect(enrollment2.academic_year_id).toBe(year2.id);
    });
  });

  describe('lifecycle error cases', () => {
    test('should throw when updating a missing student', () => {
      expect(() => studentService.updateStudent(999, { first_name: 'Ghost' }))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when deactivating a missing student', () => {
      expect(() => studentService.deactivateStudent(999))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when reactivating a missing student', () => {
      expect(() => studentService.reactivateStudent(999))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when searching with empty query', () => {
      expect(() => studentService.searchStudents('')).toThrow('Search query is required');
      expect(() => studentService.searchStudents('   ')).toThrow('Search query is required');
    });

    test('should return empty list for search with no matches', () => {
      studentService.createStudent({
        first_name: 'John', last_name: 'Doe', student_number: 'STU001'
      });

      const results = studentService.searchStudents('zzzzz');
      expect(results).toEqual([]);
    });

    test('should throw when listing with invalid status filter', () => {
      expect(() => studentService.listStudents({ status: 'bogus' }))
        .toThrow('Invalid status filter');
    });
  });

  describe('error propagation', () => {
    test('should propagate repository errors for getStudent', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      const brokenRepo = new StudentRepository(brokenDb);
      const brokenService = new StudentService(brokenRepo);

      jest.spyOn(brokenRepo, 'findById').mockImplementation(() => {
        throw new Error('Database connection lost');
      });

      expect(() => brokenService.getStudent(1)).toThrow('Database connection lost');
      brokenDb.disconnect();
    });

    test('should rollback enrollment when a multi-step operation fails', () => {
      studentService.createStudent({ first_name: 'Test', last_name: 'User', student_number: 'STU100' });
      const rollbackStudent = studentRepository.findByStudentNumber('STU100');
      const enrollmentsBefore = studentRepository.findEnrollmentsByStudent(rollbackStudent.id);
      expect(enrollmentsBefore).toHaveLength(0);

      db.query('INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)',
        ['Bad Year', '2026-01-01', '2026-12-31', 'active']);
      const badYear = db.query('SELECT * FROM academic_years WHERE name = ?', ['Bad Year']).rows[0];
      db.query('INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)',
        ['Bad Class', badYear.id, 'inactive']);
      const badClass = db.query('SELECT * FROM classes WHERE name = ?', ['Bad Class']).rows[0];

      expect(() => studentService.enrollStudent(rollbackStudent.id, {
        academic_year_id: badYear.id,
        class_id: badClass.id
      })).toThrow('Cannot enroll in an inactive class');

      const enrollmentsAfter = studentRepository.findEnrollmentsByStudent(rollbackStudent.id);
      expect(enrollmentsAfter).toHaveLength(0);
    });
  });
});
