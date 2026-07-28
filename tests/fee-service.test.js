const Database = require('../implementations/database');
const StudentRepository = require('../implementations/student-repository');
const StudentService = require('../implementations/student-service');
const AcademicStructureRepository = require('../implementations/academic-structure-repository');
const AcademicStructureService = require('../implementations/academic-structure-service');
const FeeRepository = require('../implementations/fee-repository');
const FeeService = require('../implementations/fee-service');

describe('FeeService', () => {
  let db;
  let studentRepository;
  let studentService;
  let academicStructureRepository;
  let academicStructureService;
  let feeRepository;
  let feeService;

  let academicYear;
  let classObj;
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
    db.query(`CREATE TABLE IF NOT EXISTS fee_types (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      description TEXT,
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS fee_structures (
      id INT PRIMARY KEY AUTO_INCREMENT,
      academic_year_id INT NOT NULL,
      class_id INT NOT NULL,
      fee_type_id INT NOT NULL,
      amount INT NOT NULL,
      frequency VARCHAR(50) DEFAULT 'annual',
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS fee_dues (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      academic_year_id INT NOT NULL,
      fee_structure_id INT NOT NULL,
      original_amount INT NOT NULL,
      amount_paid INT NOT NULL DEFAULT 0,
      due_date VARCHAR(10),
      status VARCHAR(20) DEFAULT 'unpaid',
      created_at VARCHAR(50),
      updated_at VARCHAR(50)
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS payments (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      fee_due_id INT NOT NULL,
      amount INT NOT NULL,
      payment_date VARCHAR(10),
      payment_method VARCHAR(50),
      receipt_number VARCHAR(100),
      created_at VARCHAR(50)
    )`);
  }

  function seedData() {
    db.query('INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)',
      ['2026-2027', '2026-01-01', '2026-12-31', 'active']);
    academicYear = db.query('SELECT * FROM academic_years WHERE name = ?', ['2026-2027']).rows[0];

    db.query('INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)',
      ['Grade 10', academicYear.id, 'active']);
    classObj = db.query('SELECT * FROM classes WHERE name = ?', ['Grade 10']).rows[0];

    student1 = studentService.createStudent({
      first_name: 'John', last_name: 'Doe', student_number: 'STU001'
    });
    student2 = studentService.createStudent({
      first_name: 'Jane', last_name: 'Smith', student_number: 'STU002'
    });

    studentService.enrollStudent(student1.id, {
      academic_year_id: academicYear.id,
      class_id: classObj.id
    });
    studentService.enrollStudent(student2.id, {
      academic_year_id: academicYear.id,
      class_id: classObj.id
    });
  }

  function createFeeTypes() {
    feeService.createFeeType({ name: 'Tuition' });
    feeService.createFeeType({ name: 'Library' });
    feeService.createFeeType({ name: 'Sports' });
  }

  function createFeeStructures() {
    const feeTypes = feeService.listFeeTypes();
    feeService.createFeeStructure({
      academic_year_id: academicYear.id,
      class_id: classObj.id,
      fee_type_id: feeTypes[0].id,
      amount: 500000
    });
    feeService.createFeeStructure({
      academic_year_id: academicYear.id,
      class_id: classObj.id,
      fee_type_id: feeTypes[1].id,
      amount: 100000
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
    feeRepository = new FeeRepository(db);
    feeService = new FeeService(feeRepository, studentRepository, academicStructureRepository);
    seedData();
  });

  afterEach(() => {
    db.disconnect();
  });

  describe('createFeeType', () => {
    test('should create a fee type', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(feeType).toBeDefined();
      expect(feeType.id).toBe(1);
      expect(feeType.name).toBe('Tuition');
      expect(feeType.status).toBe('active');
    });

    test('should trim fee type name', () => {
      const feeType = feeService.createFeeType({ name: '  Tuition Fee  ' });
      expect(feeType.name).toBe('Tuition Fee');
    });

    test('should throw for duplicate name', () => {
      feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeType({ name: 'Tuition' }))
        .toThrow('Fee type "Tuition" already exists');
    });

    test('should throw for empty name', () => {
      expect(() => feeService.createFeeType({ name: '' }))
        .toThrow('Fee type name is required');
    });

    test('should throw for null name', () => {
      expect(() => feeService.createFeeType({ name: null }))
        .toThrow('Fee type name is required');
    });

    test('should throw for missing name', () => {
      expect(() => feeService.createFeeType({}))
        .toThrow('Fee type name is required');
    });

    test('should throw for non-object data', () => {
      expect(() => feeService.createFeeType('tuition'))
        .toThrow('Fee type data must be a non-null object');
    });

    test('should throw for null data', () => {
      expect(() => feeService.createFeeType(null))
        .toThrow('Fee type data must be a non-null object');
    });

    test('should set description when provided', () => {
      const feeType = feeService.createFeeType({
        name: 'Library',
        description: 'Library usage fee'
      });
      expect(feeType.description).toBe('Library usage fee');
    });

    test('should set description to null when not provided', () => {
      const feeType = feeService.createFeeType({ name: 'Library' });
      expect(feeType.description).toBeNull();
    });
  });

  describe('getFeeType', () => {
    test('should retrieve a fee type by id', () => {
      const created = feeService.createFeeType({ name: 'Tuition' });
      const found = feeService.getFeeType(created.id);
      expect(found.id).toBe(created.id);
      expect(found.name).toBe('Tuition');
    });

    test('should throw for non-existent id', () => {
      expect(() => feeService.getFeeType(999))
        .toThrow('Fee type with id 999 not found');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => feeService.getFeeType(null)).toThrow('Fee type id is required');
      expect(() => feeService.getFeeType(undefined)).toThrow('Fee type id is required');
    });
  });

  describe('updateFeeType', () => {
    test('should update fee type name', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      const updated = feeService.updateFeeType(feeType.id, { name: 'Tuition Fee' });
      expect(updated.name).toBe('Tuition Fee');
    });

    test('should update fee type description', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      const updated = feeService.updateFeeType(feeType.id, { description: 'Updated description' });
      expect(updated.description).toBe('Updated description');
    });

    test('should deactivate a fee type', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      const updated = feeService.updateFeeType(feeType.id, { status: 'inactive' });
      expect(updated.status).toBe('inactive');
    });

    test('should throw for duplicate name on rename', () => {
      feeService.createFeeType({ name: 'Tuition' });
      const library = feeService.createFeeType({ name: 'Library' });
      expect(() => feeService.updateFeeType(library.id, { name: 'Tuition' }))
        .toThrow('Fee type "Tuition" already exists');
    });

    test('should throw for invalid status', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.updateFeeType(feeType.id, { status: 'invalid' }))
        .toThrow('Invalid fee type status');
    });

    test('should throw for empty name', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.updateFeeType(feeType.id, { name: '' }))
        .toThrow('Fee type name cannot be empty');
    });

    test('should throw for no fields to update', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.updateFeeType(feeType.id, {}))
        .toThrow('No fields to update');
    });

    test('should throw for non-existent id', () => {
      expect(() => feeService.updateFeeType(999, { name: 'New Name' }))
        .toThrow('Fee type with id 999 not found');
    });
  });

  describe('deactivateFeeType', () => {
    test('should set status to inactive', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      const deactivated = feeService.deactivateFeeType(feeType.id);
      expect(deactivated.status).toBe('inactive');
    });
  });

  describe('listFeeTypes', () => {
    test('should list all fee types', () => {
      createFeeTypes();
      const feeTypes = feeService.listFeeTypes();
      expect(feeTypes).toHaveLength(3);
    });

    test('should filter by status', () => {
      createFeeTypes();
      const feeTypes = feeService.listFeeTypes();
      feeService.deactivateFeeType(feeTypes[0].id);
      const active = feeService.listFeeTypes({ status: 'active' });
      expect(active).toHaveLength(2);
      const inactive = feeService.listFeeTypes({ status: 'inactive' });
      expect(inactive).toHaveLength(1);
    });

    test('should throw for invalid status filter', () => {
      expect(() => feeService.listFeeTypes({ status: 'invalid' }))
        .toThrow('Invalid status filter for fee types');
    });

    test('should return empty array when no fee types exist', () => {
      const feeTypes = feeService.listFeeTypes();
      expect(feeTypes).toEqual([]);
    });
  });

  describe('createFeeStructure', () => {
    test('should create a fee structure', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      const structure = feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000
      });
      expect(structure).toBeDefined();
      expect(structure.id).toBe(1);
      expect(structure.amount).toBe(500000);
      expect(structure.frequency).toBe('annual');
      expect(structure.status).toBe('active');
    });

    test('should throw for missing academic_year_id', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000
      })).toThrow('Academic year id is required');
    });

    test('should throw for missing class_id', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        fee_type_id: feeType.id,
        amount: 500000
      })).toThrow('Class id is required');
    });

    test('should throw for missing fee_type_id', () => {
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        amount: 500000
      })).toThrow('Fee type id is required');
    });

    test('should throw for missing amount', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id
      })).toThrow('Fee amount must be a positive integer');
    });

    test('should throw for non-positive amount', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 0
      })).toThrow('Fee amount must be a positive integer');
    });

    test('should throw for non-integer amount', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500.50
      })).toThrow('Fee amount must be a positive integer');
    });

    test('should throw for non-existent academic year', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        academic_year_id: 999,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000
      })).toThrow('Academic year with id 999 not found');
    });

    test('should throw for inactive academic year', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      academicStructureService.deactivateAcademicYear(academicYear.id);
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000
      })).toThrow('Cannot create fee structure for an inactive academic year');
    });

    test('should throw for non-existent class', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: 999,
        fee_type_id: feeType.id,
        amount: 500000
      })).toThrow('Class with id 999 not found');
    });

    test('should throw for non-existent fee type', () => {
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: 999,
        amount: 500000
      })).toThrow('Fee type with id 999 not found');
    });

    test('should throw for inactive fee type', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      feeService.deactivateFeeType(feeType.id);
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000
      })).toThrow('Cannot create fee structure for an inactive fee type');
    });

    test('should throw for duplicate structure', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000
      });
      expect(() => feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 600000
      })).toThrow('Fee structure already exists for this academic year, class, and fee type');
    });

    test('should accept optional frequency', () => {
      const feeType = feeService.createFeeType({ name: 'Tuition' });
      const structure = feeService.createFeeStructure({
        academic_year_id: academicYear.id,
        class_id: classObj.id,
        fee_type_id: feeType.id,
        amount: 500000,
        frequency: 'termly'
      });
      expect(structure.frequency).toBe('termly');
    });
  });

  describe('getFeeStructure', () => {
    test('should retrieve a fee structure by id', () => {
      createFeeTypes();
      createFeeStructures();
      const structures = feeService.listFeeStructures();
      const found = feeService.getFeeStructure(structures[0].id);
      expect(found.id).toBe(structures[0].id);
      expect(found.amount).toBe(500000);
    });

    test('should throw for non-existent id', () => {
      expect(() => feeService.getFeeStructure(999))
        .toThrow('Fee structure with id 999 not found');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => feeService.getFeeStructure(null)).toThrow('Fee structure id is required');
      expect(() => feeService.getFeeStructure(undefined)).toThrow('Fee structure id is required');
    });
  });

  describe('updateFeeStructure', () => {
    test('should update amount', () => {
      createFeeTypes();
      createFeeStructures();
      const structures = feeService.listFeeStructures();
      const updated = feeService.updateFeeStructure(structures[0].id, { amount: 550000 });
      expect(updated.amount).toBe(550000);
    });

    test('should update status', () => {
      createFeeTypes();
      createFeeStructures();
      const structures = feeService.listFeeStructures();
      const updated = feeService.updateFeeStructure(structures[0].id, { status: 'inactive' });
      expect(updated.status).toBe('inactive');
    });

    test('should throw for no fields to update', () => {
      createFeeTypes();
      createFeeStructures();
      const structures = feeService.listFeeStructures();
      expect(() => feeService.updateFeeStructure(structures[0].id, {}))
        .toThrow('No fields to update');
    });

    test('should throw for non-existent id', () => {
      expect(() => feeService.updateFeeStructure(999, { amount: 100 }))
        .toThrow('Fee structure with id 999 not found');
    });
  });

  describe('listFeeStructures', () => {
    test('should list all fee structures', () => {
      createFeeTypes();
      createFeeStructures();
      const structures = feeService.listFeeStructures();
      expect(structures).toHaveLength(2);
    });

    test('should filter by academic_year_id', () => {
      createFeeTypes();
      createFeeStructures();
      const filtered = feeService.listFeeStructures({ academic_year_id: academicYear.id });
      expect(filtered).toHaveLength(2);
    });

    test('should return empty array when no structures exist', () => {
      const structures = feeService.listFeeStructures();
      expect(structures).toEqual([]);
    });
  });

  describe('getStudentFees', () => {
    test('should retrieve applicable fee structures for a student', () => {
      createFeeTypes();
      createFeeStructures();
      const fees = feeService.getStudentFees(student1.id, academicYear.id);
      expect(fees).toHaveLength(2);
      expect(fees[0].fee_type_name).toBeDefined();
    });

    test('should throw for non-existent student', () => {
      expect(() => feeService.getStudentFees(999, academicYear.id))
        .toThrow('Student with id 999 not found');
    });

    test('should throw for non-existent academic year', () => {
      expect(() => feeService.getStudentFees(student1.id, 999))
        .toThrow('Academic year with id 999 not found');
    });

    test('should throw for unenrolled student', () => {
      const student3 = studentService.createStudent({
        first_name: 'Bob', last_name: 'Brown', student_number: 'STU003'
      });
      expect(() => feeService.getStudentFees(student3.id, academicYear.id))
        .toThrow(`Student ${student3.id} is not enrolled in academic year ${academicYear.id}`);
    });

    test('should return empty array when no fee structures exist', () => {
      const fees = feeService.getStudentFees(student1.id, academicYear.id);
      expect(fees).toEqual([]);
    });
  });

  describe('createFeeDues', () => {
    test('should create fee dues from active structures', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);
      expect(dues).toHaveLength(2);
      expect(dues[0].status).toBe('unpaid');
      expect(dues[0].amount_paid).toBe(0);
      expect(dues[0].original_amount).toBe(500000);
    });

    test('should throw for non-existent student', () => {
      expect(() => feeService.createFeeDues(999, academicYear.id))
        .toThrow('Student with id 999 not found');
    });

    test('should throw for non-existent academic year', () => {
      expect(() => feeService.createFeeDues(student1.id, 999))
        .toThrow('Academic year with id 999 not found');
    });

    test('should throw for unenrolled student', () => {
      const student3 = studentService.createStudent({
        first_name: 'Bob', last_name: 'Brown', student_number: 'STU003'
      });
      expect(() => feeService.createFeeDues(student3.id, academicYear.id))
        .toThrow(`Student ${student3.id} is not enrolled in academic year ${academicYear.id}`);
    });

    test('should throw for inactive enrollment', () => {
      createFeeTypes();
      createFeeStructures();
      db.query('UPDATE enrollments SET status = ? WHERE student_id = ? AND academic_year_id = ?',
        ['inactive', student1.id, academicYear.id]);
      expect(() => feeService.createFeeDues(student1.id, academicYear.id))
        .toThrow('Cannot create fee dues for an inactive enrollment');
    });

    test('should throw when no active fee structures found', () => {
      expect(() => feeService.createFeeDues(student1.id, academicYear.id))
        .toThrow(`No active fee structures found for class ${classObj.id} in academic year ${academicYear.id}`);
    });

    test('should rollback on duplicate fee due in same transaction', () => {
      createFeeTypes();
      createFeeStructures();
      feeService.createFeeDues(student1.id, academicYear.id);
      expect(() => feeService.createFeeDues(student1.id, academicYear.id))
        .toThrow('Fee due already exists');
    });
  });

  describe('recordPayment', () => {
    function setupDues() {
      createFeeTypes();
      createFeeStructures();
      return feeService.createFeeDues(student1.id, academicYear.id);
    }

    test('should record a full payment and mark as paid', () => {
      const dues = setupDues();
      const result = feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 500000,
        payment_method: 'cash',
        receipt_number: 'RCP-001'
      });
      expect(result.payment).toBeDefined();
      expect(result.payment.amount).toBe(500000);
      expect(result.payment.receipt_number).toBe('RCP-001');
      expect(result.fee_due.status).toBe('paid');
      expect(result.fee_due.amount_paid).toBe(500000);
      expect(result.fee_due.balance).toBe(0);
    });

    test('should record a partial payment', () => {
      const dues = setupDues();
      const result = feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 200000,
        payment_method: 'cash'
      });
      expect(result.fee_due.status).toBe('partially_paid');
      expect(result.fee_due.amount_paid).toBe(200000);
      expect(result.fee_due.balance).toBe(300000);
    });

    test('should allow multiple partial payments leading to paid', () => {
      const dues = setupDues();
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 300000
      });
      const result = feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 200000
      });
      expect(result.fee_due.status).toBe('paid');
      expect(result.fee_due.amount_paid).toBe(500000);
      expect(result.fee_due.balance).toBe(0);
    });

    test('should throw for non-existent student', () => {
      expect(() => feeService.recordPayment({
        student_id: 999,
        fee_due_id: 1,
        amount: 100
      })).toThrow('Student with id 999 not found');
    });

    test('should throw for non-existent fee due', () => {
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: 999,
        amount: 100
      })).toThrow('Fee due with id 999 not found');
    });

    test('should throw for payment exceeding outstanding balance', () => {
      const dues = setupDues();
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 999999
      })).toThrow('Payment would exceed outstanding balance');
    });

    test('should throw when paying a different student\'s due', () => {
      const dues1 = setupDues();
      const dues2 = feeService.createFeeDues(student2.id, academicYear.id);
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues2[0].id,
        amount: 100
      })).toThrow('Fee due does not belong to the specified student');
    });

    test('should throw for already fully paid due', () => {
      const dues = setupDues();
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 500000
      });
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 100
      })).toThrow('Fee due is already fully paid');
    });

    test('should throw for duplicate receipt number', () => {
      const dues = setupDues();
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 100,
        receipt_number: 'RCP-001'
      });
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 100,
        receipt_number: 'RCP-001'
      })).toThrow('Payment with receipt number RCP-001 already exists');
    });

    test('should throw for non-integer amount', () => {
      const dues = setupDues();
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 100.50
      })).toThrow('Payment amount must be a positive integer');
    });

    test('should throw for zero amount', () => {
      const dues = setupDues();
      expect(() => feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 0
      })).toThrow('Payment amount must be a positive integer');
    });
  });

  describe('getPayment', () => {
    test('should retrieve a payment by id', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);
      const result = feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 500000
      });
      const found = feeService.getPayment(result.payment.id);
      expect(found.id).toBe(result.payment.id);
      expect(found.amount).toBe(500000);
    });

    test('should throw for non-existent id', () => {
      expect(() => feeService.getPayment(999))
        .toThrow('Payment with id 999 not found');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => feeService.getPayment(null)).toThrow('Payment id is required');
      expect(() => feeService.getPayment(undefined)).toThrow('Payment id is required');
    });
  });

  describe('getStudentPayments', () => {
    test('should retrieve all payments for a student', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 500000
      });
      const payments = feeService.getStudentPayments(student1.id);
      expect(payments).toHaveLength(1);
    });

    test('should return empty array for student with no payments', () => {
      const payments = feeService.getStudentPayments(student1.id);
      expect(payments).toEqual([]);
    });
  });

  describe('getFeeDuePayments', () => {
    test('should retrieve all payments for a specific fee due', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 300000
      });
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 200000
      });
      const payments = feeService.getFeeDuePayments(dues[0].id);
      expect(payments).toHaveLength(2);
    });
  });

  describe('getPaymentsByDateRange', () => {
    test('should retrieve payments within a date range', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 500000,
        payment_date: '2026-03-15'
      });
      const payments = feeService.getPaymentsByDateRange('2026-03-01', '2026-03-31');
      expect(payments).toHaveLength(1);
    });

    test('should return empty array for date range with no payments', () => {
      const payments = feeService.getPaymentsByDateRange('2025-01-01', '2025-12-31');
      expect(payments).toEqual([]);
    });

    test('should throw for missing dates', () => {
      expect(() => feeService.getPaymentsByDateRange(null, '2026-03-31'))
        .toThrow('Start date and end date are required');
    });
  });

  describe('getPaymentByReceiptNumber', () => {
    test('should retrieve a payment by receipt number', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);
      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 500000,
        receipt_number: 'RCP-001'
      });
      const found = feeService.getPaymentByReceiptNumber('RCP-001');
      expect(found).toBeDefined();
      expect(found.receipt_number).toBe('RCP-001');
    });

    test('should throw for non-existent receipt number', () => {
      expect(() => feeService.getPaymentByReceiptNumber('NONEXISTENT'))
        .toThrow('Payment with receipt number NONEXISTENT not found');
    });

    test('should throw for empty receipt number', () => {
      expect(() => feeService.getPaymentByReceiptNumber(''))
        .toThrow('Receipt number is required');
    });
  });

  describe('getStudentFinancialSummary', () => {
    test('should compute correct summary for a student', () => {
      createFeeTypes();
      createFeeStructures();
      const dues = feeService.createFeeDues(student1.id, academicYear.id);

      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues[0].id,
        amount: 300000
      });

      const summary = feeService.getStudentFinancialSummary(student1.id, academicYear.id);

      expect(summary.total_fees_assigned).toBe(600000);
      expect(summary.total_paid).toBe(300000);
      expect(summary.total_outstanding).toBe(300000);
      expect(summary.unpaid_count).toBe(1);
      expect(summary.partially_paid_count).toBe(1);
      expect(summary.paid_count).toBe(0);
    });

    test('should return zero summary when no dues exist', () => {
      const summary = feeService.getStudentFinancialSummary(student1.id, academicYear.id);
      expect(summary.total_fees_assigned).toBe(0);
      expect(summary.total_paid).toBe(0);
      expect(summary.total_outstanding).toBe(0);
    });
  });

  describe('getClassFinancialSummary', () => {
    test('should compute correct summary for a class', () => {
      createFeeTypes();
      createFeeStructures();
      const dues1 = feeService.createFeeDues(student1.id, academicYear.id);
      const dues2 = feeService.createFeeDues(student2.id, academicYear.id);

      feeService.recordPayment({
        student_id: student1.id,
        fee_due_id: dues1[0].id,
        amount: 500000
      });

      const summary = feeService.getClassFinancialSummary(classObj.id, academicYear.id);

      expect(summary.total_students).toBe(2);
      expect(summary.total_fees_assigned).toBe(1200000);
      expect(summary.total_collected).toBe(500000);
      expect(summary.total_outstanding).toBe(700000);
      expect(summary.students_with_outstanding).toBe(2);
    });

    test('should return zero summary when no enrollments', () => {
      const summary = feeService.getClassFinancialSummary(999, academicYear.id);
      expect(summary.total_students).toBe(0);
      expect(summary.total_fees_assigned).toBe(0);
      expect(summary.total_collected).toBe(0);
    });
  });

  describe('atomicity', () => {
    test('should rollback payment if fee due update fails', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      brokenDb.query(`CREATE TABLE IF NOT EXISTS students (
        id INT PRIMARY KEY AUTO_INCREMENT, first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL, student_number VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255), date_of_birth VARCHAR(10),
        status VARCHAR(20) DEFAULT 'active', created_at VARCHAR(50), updated_at VARCHAR(50)
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS academic_years (
        id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
        start_date VARCHAR(10), end_date VARCHAR(10), status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS classes (
        id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
        academic_year_id INT, status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS enrollments (
        id INT PRIMARY KEY AUTO_INCREMENT, student_id INT NOT NULL,
        academic_year_id INT NOT NULL, class_id INT, section_id INT,
        status VARCHAR(20) DEFAULT 'active', enrolled_at VARCHAR(50)
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS fee_types (
        id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
        description TEXT, status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS fee_structures (
        id INT PRIMARY KEY AUTO_INCREMENT, academic_year_id INT NOT NULL,
        class_id INT NOT NULL, fee_type_id INT NOT NULL,
        amount INT NOT NULL, frequency VARCHAR(50) DEFAULT 'annual',
        status VARCHAR(20) DEFAULT 'active'
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS fee_dues (
        id INT PRIMARY KEY AUTO_INCREMENT, student_id INT NOT NULL,
        academic_year_id INT NOT NULL, fee_structure_id INT NOT NULL,
        original_amount INT NOT NULL, amount_paid INT NOT NULL DEFAULT 0,
        due_date VARCHAR(10), status VARCHAR(20) DEFAULT 'unpaid',
        created_at VARCHAR(50), updated_at VARCHAR(50)
      )`);
      brokenDb.query(`CREATE TABLE IF NOT EXISTS payments (
        id INT PRIMARY KEY AUTO_INCREMENT, student_id INT NOT NULL,
        fee_due_id INT NOT NULL, amount INT NOT NULL,
        payment_date VARCHAR(10), payment_method VARCHAR(50),
        receipt_number VARCHAR(100), created_at VARCHAR(50)
      )`);

      brokenDb.query("INSERT INTO academic_years (name, status) VALUES (?, ?)", ['2026-2027', 'active']);
      brokenDb.query("INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)", ['Grade 10', 1, 'active']);
      brokenDb.query("INSERT INTO students (first_name, last_name, student_number, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ['John', 'Doe', 'STU001', 'active', new Date().toISOString(), new Date().toISOString()]);
      brokenDb.query("INSERT INTO enrollments (student_id, academic_year_id, class_id, status, enrolled_at) VALUES (?, ?, ?, ?, ?)",
        [1, 1, 1, 'active', new Date().toISOString()]);
      brokenDb.query("INSERT INTO fee_types (name, status) VALUES (?, ?)", ['Tuition', 'active']);
      brokenDb.query("INSERT INTO fee_structures (academic_year_id, class_id, fee_type_id, amount, status) VALUES (?, ?, ?, ?, ?)",
        [1, 1, 1, 500000, 'active']);
      brokenDb.query("INSERT INTO fee_dues (student_id, academic_year_id, fee_structure_id, original_amount, amount_paid, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [1, 1, 1, 500000, 0, 'unpaid', new Date().toISOString(), new Date().toISOString()]);

      const brokenFeeRepo = new FeeRepository(brokenDb);
      const brokenStudentRepo = new StudentRepository(brokenDb);
      const brokenAcademicRepo = new AcademicStructureRepository(brokenDb);
      const brokenService = new FeeService(brokenFeeRepo, brokenStudentRepo, brokenAcademicRepo);

      jest.spyOn(brokenFeeRepo, 'updateFeeDue').mockImplementation(() => {
        throw new Error('Database error');
      });

      expect(() => brokenService.recordPayment({
        student_id: 1,
        fee_due_id: 1,
        amount: 500000
      })).toThrow('Database error');

      const payments = brokenFeeRepo.findPaymentsByStudent(1);
      expect(payments).toHaveLength(0);

      const due = brokenFeeRepo.findFeeDueById(1);
      expect(due.amount_paid).toBe(0);
      expect(due.status).toBe('unpaid');

      brokenDb.disconnect();
    });
  });
});
