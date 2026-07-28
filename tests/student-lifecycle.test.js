const Database = require('../implementations/database');
const StudentRepository = require('../implementations/student-repository');
const StudentService = require('../implementations/student-service');

describe('Student Lifecycle Integration', () => {
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

  describe('complete student lifecycle (create → get → update → get → deactivate → reactivate → verify)', () => {
    test('should execute full student lifecycle end-to-end', () => {
      // 1. CREATE a student
      const created = studentService.createStudent({
        first_name: '  Alice  ',
        last_name: 'Johnson',
        student_number: 'STU100',
        email: 'alice@school.com',
        date_of_birth: '2000-06-15'
      });

      expect(created).toBeDefined();
      expect(created.id).toBe(1);
      expect(created.first_name).toBe('Alice');
      expect(created.last_name).toBe('Johnson');
      expect(created.student_number).toBe('STU100');
      expect(created.email).toBe('alice@school.com');
      expect(created.date_of_birth).toBe('2000-06-15');
      expect(created.status).toBe('active');
      expect(created.created_at).toBeDefined();
      expect(created.updated_at).toBeDefined();

      // 2. RETRIEVE by ID — verify the persisted data matches
      const retrieved = studentService.getStudent(created.id);
      expect(retrieved.id).toBe(created.id);
      expect(retrieved.first_name).toBe('Alice');
      expect(retrieved.last_name).toBe('Johnson');
      expect(retrieved.student_number).toBe('STU100');
      expect(retrieved.email).toBe('alice@school.com');
      expect(retrieved.date_of_birth).toBe('2000-06-15');
      expect(retrieved.status).toBe('active');

      // 3. UPDATE — change fields
      const updated = studentService.updateStudent(created.id, {
        first_name: 'Alicia',
        email: 'alicia@school.com'
      });

      expect(updated.first_name).toBe('Alicia');
      expect(updated.last_name).toBe('Johnson');
      expect(updated.email).toBe('alicia@school.com');
      expect(updated.student_number).toBe('STU100');
      expect(updated.status).toBe('active');

      // 4. RETRIEVE again — verify updates persisted
      const retrievedAgain = studentService.getStudent(created.id);
      expect(retrievedAgain.first_name).toBe('Alicia');
      expect(retrievedAgain.email).toBe('alicia@school.com');
      expect(retrievedAgain.last_name).toBe('Johnson');
      expect(retrievedAgain.student_number).toBe('STU100');

      // 5. DEACTIVATE student
      const deactivated = studentService.deactivateStudent(created.id);
      expect(deactivated.status).toBe('inactive');

      // 6. VERIFY inactive state
      const inactiveState = studentService.getStudent(created.id);
      expect(inactiveState.status).toBe('inactive');
      expect(inactiveState.updated_at).not.toBe(created.updated_at);

      // 7. REACTIVATE student
      const reactivated = studentService.reactivateStudent(created.id);
      expect(reactivated.status).toBe('active');

      // 8. VERIFY final active state
      const finalState = studentService.getStudent(created.id);
      expect(finalState.first_name).toBe('Alicia');
      expect(finalState.last_name).toBe('Johnson');
      expect(finalState.student_number).toBe('STU100');
      expect(finalState.email).toBe('alicia@school.com');
      expect(finalState.status).toBe('active');
    });
  });

  describe('lifecycle error cases', () => {
    test('should reject duplicate student number', () => {
      studentService.createStudent({
        first_name: 'First',
        last_name: 'User',
        student_number: 'STU001'
      });

      expect(() => studentService.createStudent({
        first_name: 'Second',
        last_name: 'User',
        student_number: 'STU001'
      })).toThrow('already exists');
    });

    test('should throw when retrieving non-existent student', () => {
      expect(() => studentService.getStudent(999))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when reactivating already active student', () => {
      const student = studentService.createStudent({
        first_name: 'Already', last_name: 'Active', student_number: 'STU003'
      });
      expect(() => studentService.reactivateStudent(student.id))
        .toThrow('is already active');
    });

    test('should throw when reactivating non-existent student', () => {
      expect(() => studentService.reactivateStudent(999))
        .toThrow('Student with id 999 not found');
    });

    test('should throw when reactivating with null id', () => {
      expect(() => studentService.reactivateStudent(null))
        .toThrow('Student id is required');
    });

    test('should allow deactivate → reactivate → deactivate cycle', () => {
      const student = studentService.createStudent({
        first_name: 'Cycle', last_name: 'Test', student_number: 'STU004'
      });

      studentService.deactivateStudent(student.id);
      expect(studentService.getStudent(student.id).status).toBe('inactive');

      studentService.reactivateStudent(student.id);
      expect(studentService.getStudent(student.id).status).toBe('active');

      studentService.deactivateStudent(student.id);
      expect(studentService.getStudent(student.id).status).toBe('inactive');
    });

    test('should throw when deactivating already inactive student', () => {
      const student = studentService.createStudent({
        first_name: 'Test',
        last_name: 'User',
        student_number: 'STU002'
      });

      studentService.deactivateStudent(student.id);
      expect(() => studentService.deactivateStudent(student.id))
        .toThrow('is already inactive');
    });

    test('should list active students after deactivation', () => {
      const s1 = studentService.createStudent({
        first_name: 'Active', last_name: 'One', student_number: 'STU010'
      });
      const s2 = studentService.createStudent({
        first_name: 'Active', last_name: 'Two', student_number: 'STU011'
      });

      studentService.deactivateStudent(s1.id);

      const activeStudents = studentService.listStudents({ status: 'active' });
      expect(activeStudents).toHaveLength(1);
      expect(activeStudents[0].student_number).toBe('STU011');

      const allStudents = studentService.listStudents();
      expect(allStudents).toHaveLength(2);
    });

    test('should search across multiple fields', () => {
      studentService.createStudent({
        first_name: 'Robert', last_name: 'Jones', student_number: 'STU020', email: 'rob@school.com'
      });
      studentService.createStudent({
        first_name: 'Roberta', last_name: 'Smith', student_number: 'STU021', email: 'roberta@school.com'
      });
      studentService.createStudent({
        first_name: 'Alice', last_name: 'Robertson', student_number: 'STU022'
      });

      const byFirstName = studentService.searchStudents('roberta');
      expect(byFirstName).toHaveLength(1);
      expect(byFirstName[0].student_number).toBe('STU021');

      const byLastName = studentService.searchStudents('jones');
      expect(byLastName).toHaveLength(1);
      expect(byLastName[0].student_number).toBe('STU020');

      const byStudentNumber = studentService.searchStudents('STU022');
      expect(byStudentNumber).toHaveLength(1);
      expect(byStudentNumber[0].first_name).toBe('Alice');
    });

    test('should reject invalid student data on creation', () => {
      expect(() => studentService.createStudent({
        first_name: '', last_name: 'Doe', student_number: 'STU030'
      })).toThrow('First name is required');

      expect(() => studentService.createStudent({
        first_name: 'John', last_name: '', student_number: 'STU030'
      })).toThrow('Last name is required');

      expect(() => studentService.createStudent({
        first_name: 'John', last_name: 'Doe', student_number: ''
      })).toThrow('Student number is required');

      expect(() => studentService.createStudent({
        first_name: 'John', last_name: 'Doe', student_number: 'STU030', email: 'bad-email'
      })).toThrow('Invalid email format');
    });
  });

  describe('cross-operation data consistency', () => {
    test('should maintain data integrity across multiple operations', () => {
      const student = studentService.createStudent({
        first_name: 'Consistency',
        last_name: 'Check',
        student_number: 'STU050',
        email: 'test@school.com'
      });

      studentService.updateStudent(student.id, { first_name: 'Verified' });
      studentService.updateStudent(student.id, { last_name: 'Confirmed' });
      studentService.updateStudent(student.id, { email: 'verified@school.com' });

      const final = studentService.getStudent(student.id);
      expect(final.first_name).toBe('Verified');
      expect(final.last_name).toBe('Confirmed');
      expect(final.email).toBe('verified@school.com');
      expect(final.student_number).toBe('STU050');
      expect(final.status).toBe('active');
    });

    test('should track updated_at changes through the lifecycle', () => {
      const student = studentService.createStudent({
        first_name: 'Time', last_name: 'Tracker', student_number: 'STU060'
      });

      const updated = studentService.updateStudent(student.id, { first_name: 'Time2' });
      expect(updated.updated_at).toBeDefined();
      expect(updated.updated_at).not.toBe(student.updated_at);

      const deactivated = studentService.deactivateStudent(student.id);
      expect(deactivated.updated_at).toBeDefined();
      expect(deactivated.updated_at).not.toBe(student.updated_at);
    });
  });
});
