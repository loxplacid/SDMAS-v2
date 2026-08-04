const Database = require('../implementations/database');
const AcademicStructureRepository = require('../implementations/academic-structure-repository');
const AcademicStructureService = require('../implementations/academic-structure-service');

describe('AcademicStructureService', () => {
  let db;
  let repository;
  let service;

  function createTables() {
    db.query(`CREATE TABLE IF NOT EXISTS academic_years (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      start_date VARCHAR(10),
      end_date VARCHAR(10),
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS terms (
      id INT PRIMARY KEY AUTO_INCREMENT,
      academic_year_id INT NOT NULL,
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
    db.query(`CREATE TABLE IF NOT EXISTS teachers (
      id INT PRIMARY KEY AUTO_INCREMENT,
      first_name VARCHAR(100) NOT NULL,
      last_name VARCHAR(100) NOT NULL,
      employee_number VARCHAR(50) UNIQUE NOT NULL,
      email VARCHAR(255),
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS teacher_assignments (
      id INT PRIMARY KEY AUTO_INCREMENT,
      teacher_id INT NOT NULL,
      class_id INT NOT NULL,
      subject_id INT,
      status VARCHAR(20) DEFAULT 'active'
    )`);
  }

  beforeEach(() => {
    db = new Database();
    db.connect();
    createTables();
    repository = new AcademicStructureRepository(db);
    service = new AcademicStructureService(repository);
  });

  afterEach(() => {
    db.disconnect();
  });

  // --- Academic Year tests ---

  describe('createAcademicYear', () => {
    test('should create an academic year with valid data', () => {
      const year = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      expect(year).toBeDefined();
      expect(year.id).toBe(1);
      expect(year.name).toBe('2026-2027');
      expect(year.start_date).toBe('2026-01-01');
      expect(year.end_date).toBe('2026-12-31');
      expect(year.status).toBe('active');
    });

    test('should throw when data is null or undefined', () => {
      expect(() => service.createAcademicYear(null)).toThrow('Academic year data must be a non-null object');
      expect(() => service.createAcademicYear(undefined)).toThrow('Academic year data must be a non-null object');
    });

    test('should throw when data is an array', () => {
      expect(() => service.createAcademicYear(['a'])).toThrow('Academic year data must be a non-null object');
    });

    test('should throw when name is missing', () => {
      expect(() => service.createAcademicYear({
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      })).toThrow('Academic year name is required');
    });

    test('should throw when name is empty', () => {
      expect(() => service.createAcademicYear({
        name: '',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      })).toThrow('Academic year name is required');
    });

    test('should throw when start_date is missing', () => {
      expect(() => service.createAcademicYear({
        name: '2026-2027',
        end_date: '2026-12-31'
      })).toThrow('Academic year start date is required');
    });

    test('should throw when end_date is missing', () => {
      expect(() => service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01'
      })).toThrow('Academic year end date is required');
    });

    test('should throw when end date is before start date', () => {
      expect(() => service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-12-31',
        end_date: '2026-01-01'
      })).toThrow('Academic year end date must be after start date');
    });

    test('should throw when end date equals start date', () => {
      expect(() => service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-01-01'
      })).toThrow('Academic year end date must be after start date');
    });

    test('should throw when academic year name already exists', () => {
      service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      expect(() => service.createAcademicYear({
        name: '2026-2027',
        start_date: '2027-01-01',
        end_date: '2027-12-31'
      })).toThrow('Academic year "2026-2027" already exists');
    });

    test('should accept custom status', () => {
      const year = service.createAcademicYear({
        name: 'Test Year',
        start_date: '2026-01-01',
        end_date: '2026-12-31',
        status: 'inactive'
      });

      expect(year.status).toBe('inactive');
    });
  });

  describe('getAcademicYear', () => {
    test('should return an academic year by id', () => {
      const created = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      const found = service.getAcademicYear(created.id);
      expect(found.id).toBe(created.id);
      expect(found.name).toBe('2026-2027');
    });

    test('should throw when id is null or undefined', () => {
      expect(() => service.getAcademicYear(null)).toThrow('Academic year id is required');
      expect(() => service.getAcademicYear(undefined)).toThrow('Academic year id is required');
    });

    test('should throw when academic year not found', () => {
      expect(() => service.getAcademicYear(999)).toThrow('Academic year with id 999 not found');
    });
  });

  describe('updateAcademicYear', () => {
    test('should update academic year name', () => {
      const created = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      const updated = service.updateAcademicYear(created.id, { name: '2026-2027 Updated' });
      expect(updated.name).toBe('2026-2027 Updated');
    });

    test('should throw when id is null', () => {
      expect(() => service.updateAcademicYear(null, { name: 'New' })).toThrow('Academic year id is required');
    });

    test('should throw when data is null', () => {
      expect(() => service.updateAcademicYear(1, null)).toThrow('Update data must be a non-null object');
    });

    test('should throw when setting name to empty', () => {
      const created = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      expect(() => service.updateAcademicYear(created.id, { name: '' })).toThrow('Academic year name cannot be empty');
    });

    test('should throw on duplicate name after rename', () => {
      service.createAcademicYear({
        name: 'First',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });
      const second = service.createAcademicYear({
        name: 'Second',
        start_date: '2027-01-01',
        end_date: '2027-12-31'
      });

      expect(() => service.updateAcademicYear(second.id, { name: 'First' }))
        .toThrow('Academic year "First" already exists');
    });

    test('should reject invalid status', () => {
      const created = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      expect(() => service.updateAcademicYear(created.id, { status: 'bogus' }))
        .toThrow('Invalid academic year status');
    });

    test('should reject end date before start date', () => {
      const created = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      expect(() => service.updateAcademicYear(created.id, { start_date: '2027-01-01' }))
        .toThrow('Academic year end date must be after start date');
    });
  });

  describe('activateAcademicYear / deactivateAcademicYear', () => {
    test('should activate an academic year', () => {
      const created = service.createAcademicYear({
        name: 'Test',
        start_date: '2026-01-01',
        end_date: '2026-12-31',
        status: 'inactive'
      });

      const activated = service.activateAcademicYear(created.id);
      expect(activated.status).toBe('active');
    });

    test('should deactivate an academic year', () => {
      const created = service.createAcademicYear({
        name: 'Test',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });

      const deactivated = service.deactivateAcademicYear(created.id);
      expect(deactivated.status).toBe('inactive');
    });
  });

  describe('listAcademicYears', () => {
    test('should list all academic years', () => {
      service.createAcademicYear({ name: '2025-2026', start_date: '2025-01-01', end_date: '2025-12-31' });
      service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });

      const years = service.listAcademicYears();
      expect(years).toHaveLength(2);
    });

    test('should filter academic years by status', () => {
      service.createAcademicYear({ name: 'Active Year', start_date: '2026-01-01', end_date: '2026-12-31' });
      service.createAcademicYear({ name: 'Inactive Year', start_date: '2025-01-01', end_date: '2025-12-31', status: 'inactive' });

      const activeYears = service.listAcademicYears({ status: 'active' });
      expect(activeYears).toHaveLength(1);
      expect(activeYears[0].name).toBe('Active Year');

      const inactiveYears = service.listAcademicYears({ status: 'inactive' });
      expect(inactiveYears).toHaveLength(1);
      expect(inactiveYears[0].name).toBe('Inactive Year');
    });

    test('should throw for invalid status filter', () => {
      expect(() => service.listAcademicYears({ status: 'bogus' }))
        .toThrow('Invalid status filter for academic years');
    });
  });

  // --- Term tests ---

  describe('createTerm', () => {
    let academicYear;

    beforeEach(() => {
      academicYear = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });
    });

    test('should create a term within an academic year', () => {
      const term = service.createTerm(academicYear.id, {
        name: 'Term 1',
        start_date: '2026-02-01',
        end_date: '2026-06-30'
      });

      expect(term).toBeDefined();
      expect(term.id).toBe(1);
      expect(term.name).toBe('Term 1');
      expect(term.academic_year_id).toBe(academicYear.id);
      expect(term.status).toBe('active');
    });

    test('should throw when academic year does not exist', () => {
      expect(() => service.createTerm(999, {
        name: 'Term 1',
        start_date: '2026-02-01',
        end_date: '2026-06-30'
      })).toThrow('Academic year with id 999 not found');
    });

    test('should throw when academic year id is null', () => {
      expect(() => service.createTerm(null, { name: 'T1', start_date: '2026-02-01', end_date: '2026-06-30' }))
        .toThrow('Academic year id is required');
    });

    test('should throw when term data is invalid', () => {
      expect(() => service.createTerm(academicYear.id, null)).toThrow('Term data must be a non-null object');
    });

    test('should throw when term name is missing', () => {
      expect(() => service.createTerm(academicYear.id, {
        start_date: '2026-02-01',
        end_date: '2026-06-30'
      })).toThrow('Term name is required');
    });

    test('should throw when term end date is before start date', () => {
      expect(() => service.createTerm(academicYear.id, {
        name: 'Bad Term',
        start_date: '2026-06-30',
        end_date: '2026-02-01'
      })).toThrow('Term end date must be after start date');
    });

    test('should throw when term dates are outside academic year', () => {
      expect(() => service.createTerm(academicYear.id, {
        name: 'Outside Term',
        start_date: '2025-06-01',
        end_date: '2026-06-30'
      })).toThrow('Term dates must fall within the academic year date range');
    });

    test('should throw when term starts before academic year', () => {
      expect(() => service.createTerm(academicYear.id, {
        name: 'Early Term',
        start_date: '2025-06-01',
        end_date: '2026-02-01'
      })).toThrow('Term dates must fall within the academic year date range');
    });

    test('should throw when term ends after academic year', () => {
      expect(() => service.createTerm(academicYear.id, {
        name: 'Late Term',
        start_date: '2026-06-01',
        end_date: '2027-02-01'
      })).toThrow('Term dates must fall within the academic year date range');
    });

    test('should throw on overlapping terms', () => {
      service.createTerm(academicYear.id, {
        name: 'Term 1',
        start_date: '2026-02-01',
        end_date: '2026-06-30'
      });

      expect(() => service.createTerm(academicYear.id, {
        name: 'Term 2',
        start_date: '2026-03-01',
        end_date: '2026-07-31'
      })).toThrow('Term dates overlap with an existing term in this academic year');
    });

    test('should allow adjacent non-overlapping terms', () => {
      const t1 = service.createTerm(academicYear.id, {
        name: 'Term 1',
        start_date: '2026-02-01',
        end_date: '2026-06-30'
      });

      const t2 = service.createTerm(academicYear.id, {
        name: 'Term 2',
        start_date: '2026-07-01',
        end_date: '2026-12-31'
      });

      expect(t1.id).toBe(1);
      expect(t2.id).toBe(2);
    });
  });

  describe('getTerm', () => {
    test('should return a term by id', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      const created = service.createTerm(year.id, { name: 'Term 1', start_date: '2026-02-01', end_date: '2026-06-30' });

      const found = service.getTerm(created.id);
      expect(found.name).toBe('Term 1');
    });

    test('should throw when term not found', () => {
      expect(() => service.getTerm(999)).toThrow('Term with id 999 not found');
    });
  });

  describe('updateTerm', () => {
    let year;
    let term;

    beforeEach(() => {
      year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      term = service.createTerm(year.id, { name: 'Term 1', start_date: '2026-02-01', end_date: '2026-06-30' });
    });

    test('should update term name', () => {
      const updated = service.updateTerm(term.id, { name: 'First Term' });
      expect(updated.name).toBe('First Term');
    });

    test('should throw when id is null', () => {
      expect(() => service.updateTerm(null, { name: 'New' })).toThrow('Term id is required');
    });

    test('should throw when data is null', () => {
      expect(() => service.updateTerm(term.id, null)).toThrow('Update data must be a non-null object');
    });

    test('should throw when name is empty', () => {
      expect(() => service.updateTerm(term.id, { name: '' })).toThrow('Term name cannot be empty');
    });

    test('should reject invalid status', () => {
      expect(() => service.updateTerm(term.id, { status: 'bogus' }))
        .toThrow('Invalid term status');
    });

    test('should reject end date before start date', () => {
      expect(() => service.updateTerm(term.id, { start_date: '2026-07-01' }))
        .toThrow('Term end date must be after start date');
    });

    test('should reject dates outside academic year', () => {
      expect(() => service.updateTerm(term.id, { start_date: '2025-01-01' }))
        .toThrow('Term dates must fall within the academic year date range');
    });

    test('should reject overlapping dates', () => {
      service.createTerm(year.id, { name: 'Term 2', start_date: '2026-07-01', end_date: '2026-12-31' });
      expect(() => service.updateTerm(term.id, { end_date: '2026-08-01' }))
        .toThrow('Term dates overlap with an existing term in this academic year');
    });
  });

  describe('listTermsByAcademicYear', () => {
    test('should list terms for an academic year', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      service.createTerm(year.id, { name: 'Term 1', start_date: '2026-02-01', end_date: '2026-06-30' });
      service.createTerm(year.id, { name: 'Term 2', start_date: '2026-07-01', end_date: '2026-12-31' });

      const terms = service.listTermsByAcademicYear(year.id);
      expect(terms).toHaveLength(2);
    });

    test('should throw when academic year id is null', () => {
      expect(() => service.listTermsByAcademicYear(null)).toThrow('Academic year id is required');
    });
  });

  // --- Class tests ---

  describe('createClass', () => {
    let academicYear;

    beforeEach(() => {
      academicYear = service.createAcademicYear({
        name: '2026-2027',
        start_date: '2026-01-01',
        end_date: '2026-12-31'
      });
    });

    test('should create a class under an academic year', () => {
      const classObj = service.createClass(academicYear.id, { name: 'Grade 10' });

      expect(classObj).toBeDefined();
      expect(classObj.id).toBe(1);
      expect(classObj.name).toBe('Grade 10');
      expect(classObj.academic_year_id).toBe(academicYear.id);
      expect(classObj.status).toBe('active');
    });

    test('should throw when academic year does not exist', () => {
      expect(() => service.createClass(999, { name: 'Grade 10' }))
        .toThrow('Academic year with id 999 not found');
    });

    test('should throw when academic year id is null', () => {
      expect(() => service.createClass(null, { name: 'Grade 10' })).toThrow('Academic year id is required');
    });

    test('should throw when class name is missing', () => {
      expect(() => service.createClass(academicYear.id, {})).toThrow('Class name is required');
    });

    test('should throw when class name already exists in same academic year', () => {
      service.createClass(academicYear.id, { name: 'Grade 10' });

      expect(() => service.createClass(academicYear.id, { name: 'Grade 10' }))
        .toThrow('Class "Grade 10" already exists in this academic year');
    });

    test('should allow same class name in different academic years', () => {
      const year2 = service.createAcademicYear({
        name: '2027-2028',
        start_date: '2027-01-01',
        end_date: '2027-12-31'
      });

      service.createClass(academicYear.id, { name: 'Grade 10' });
      const class2 = service.createClass(year2.id, { name: 'Grade 10' });
      expect(class2.id).toBe(2);
    });
  });

  describe('updateClass', () => {
    let year;
    let classObj;

    beforeEach(() => {
      year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      classObj = service.createClass(year.id, { name: 'Grade 10' });
    });

    test('should update class name', () => {
      const updated = service.updateClass(classObj.id, { name: 'Grade 10 Updated' });
      expect(updated.name).toBe('Grade 10 Updated');
    });

    test('should throw when id is null', () => {
      expect(() => service.updateClass(null, { name: 'New' })).toThrow('Class id is required');
    });

    test('should throw when data is null', () => {
      expect(() => service.updateClass(classObj.id, null)).toThrow('Update data must be a non-null object');
    });

    test('should throw when name is empty', () => {
      expect(() => service.updateClass(classObj.id, { name: '' })).toThrow('Class name cannot be empty');
    });

    test('should throw on duplicate name within same year', () => {
      service.createClass(year.id, { name: 'Grade 11' });
      expect(() => service.updateClass(classObj.id, { name: 'Grade 11' }))
        .toThrow('already exists in this academic year');
    });

    test('should reject invalid status', () => {
      expect(() => service.updateClass(classObj.id, { status: 'bogus' }))
        .toThrow('Invalid class status');
    });

    test('should activate and deactivate class', () => {
      const deactivated = service.deactivateClass(classObj.id);
      expect(deactivated.status).toBe('inactive');

      const activated = service.activateClass(classObj.id);
      expect(activated.status).toBe('active');
    });
  });

  describe('getClass', () => {
    test('should return a class by id', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      const created = service.createClass(year.id, { name: 'Grade 10' });

      const found = service.getClass(created.id);
      expect(found.name).toBe('Grade 10');
    });

    test('should throw when class not found', () => {
      expect(() => service.getClass(999)).toThrow('Class with id 999 not found');
    });

    test('should throw when id is null', () => {
      expect(() => service.getClass(null)).toThrow('Class id is required');
    });
  });

  describe('listClassesByAcademicYear', () => {
    test('should list classes for an academic year', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      service.createClass(year.id, { name: 'Grade 10' });
      service.createClass(year.id, { name: 'Grade 11' });

      const classes = service.listClassesByAcademicYear(year.id);
      expect(classes).toHaveLength(2);
    });

    test('should throw when academic year id is null', () => {
      expect(() => service.listClassesByAcademicYear(null)).toThrow('Academic year id is required');
    });
  });

  // --- Section tests ---

  describe('createSection', () => {
    let year;
    let classObj;

    beforeEach(() => {
      year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      classObj = service.createClass(year.id, { name: 'Grade 10' });
    });

    test('should create a section under a class', () => {
      const section = service.createSection(classObj.id, { name: 'Section A' });

      expect(section).toBeDefined();
      expect(section.id).toBe(1);
      expect(section.name).toBe('Section A');
      expect(section.class_id).toBe(classObj.id);
      expect(section.status).toBe('active');
    });

    test('should throw when class does not exist', () => {
      expect(() => service.createSection(999, { name: 'Section A' }))
        .toThrow('Class with id 999 not found');
    });

    test('should throw when class id is null', () => {
      expect(() => service.createSection(null, { name: 'Section A' })).toThrow('Class id is required');
    });

    test('should throw when section name is missing', () => {
      expect(() => service.createSection(classObj.id, {})).toThrow('Section name is required');
    });

    test('should throw when section name already exists in same class', () => {
      service.createSection(classObj.id, { name: 'Section A' });

      expect(() => service.createSection(classObj.id, { name: 'Section A' }))
        .toThrow('Section "Section A" already exists in this class');
    });

    test('should allow same section name in different classes', () => {
      const class2 = service.createClass(year.id, { name: 'Grade 11' });
      service.createSection(classObj.id, { name: 'Section A' });
      const section2 = service.createSection(class2.id, { name: 'Section A' });
      expect(section2.id).toBe(2);
    });
  });

  describe('getSection', () => {
    test('should return a section by id', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      const cls = service.createClass(year.id, { name: 'Grade 10' });
      const created = service.createSection(cls.id, { name: 'Section A' });

      const found = service.getSection(created.id);
      expect(found.name).toBe('Section A');
    });

    test('should throw when section not found', () => {
      expect(() => service.getSection(999)).toThrow('Section with id 999 not found');
    });
  });

  describe('updateSection', () => {
    let year;
    let cls;
    let section;

    beforeEach(() => {
      year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      cls = service.createClass(year.id, { name: 'Grade 10' });
      section = service.createSection(cls.id, { name: 'Section A' });
    });

    test('should update section name', () => {
      const updated = service.updateSection(section.id, { name: 'Section B' });
      expect(updated.name).toBe('Section B');
    });

    test('should throw when id is null', () => {
      expect(() => service.updateSection(null, { name: 'New' })).toThrow('Section id is required');
    });

    test('should throw when data is null', () => {
      expect(() => service.updateSection(section.id, null)).toThrow('Update data must be a non-null object');
    });

    test('should throw when name is empty', () => {
      expect(() => service.updateSection(section.id, { name: '' })).toThrow('Section name cannot be empty');
    });

    test('should throw on duplicate name within same class', () => {
      service.createSection(cls.id, { name: 'Section B' });
      expect(() => service.updateSection(section.id, { name: 'Section B' }))
        .toThrow('already exists in this class');
    });

    test('should reject invalid status', () => {
      expect(() => service.updateSection(section.id, { status: 'bogus' }))
        .toThrow('Invalid section status');
    });

    test('should activate and deactivate section', () => {
      const deactivated = service.deactivateSection(section.id);
      expect(deactivated.status).toBe('inactive');

      const activated = service.activateSection(section.id);
      expect(activated.status).toBe('active');
    });
  });

  describe('listSectionsByClass', () => {
    test('should list sections for a class', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      const cls = service.createClass(year.id, { name: 'Grade 10' });
      service.createSection(cls.id, { name: 'Section A' });
      service.createSection(cls.id, { name: 'Section B' });

      const sections = service.listSectionsByClass(cls.id);
      expect(sections).toHaveLength(2);
    });

    test('should throw when class id is null', () => {
      expect(() => service.listSectionsByClass(null)).toThrow('Class id is required');
    });
  });

  // --- Subject tests ---

  describe('createSubject', () => {
    test('should create a subject with valid data', () => {
      const subject = service.createSubject({
        name: 'Mathematics',
        code: 'MATH101'
      });

      expect(subject).toBeDefined();
      expect(subject.id).toBe(1);
      expect(subject.name).toBe('Mathematics');
      expect(subject.code).toBe('MATH101');
      expect(subject.status).toBe('active');
    });

    test('should throw when data is null', () => {
      expect(() => service.createSubject(null)).toThrow('Subject data must be a non-null object');
    });

    test('should throw when name is missing', () => {
      expect(() => service.createSubject({ code: 'MATH101' })).toThrow('Subject name is required');
    });

    test('should throw when code is missing', () => {
      expect(() => service.createSubject({ name: 'Math' })).toThrow('Subject code is required');
    });

    test('should throw when name already exists', () => {
      service.createSubject({ name: 'Mathematics', code: 'MATH101' });

      expect(() => service.createSubject({ name: 'Mathematics', code: 'MATH102' }))
        .toThrow('Subject "Mathematics" already exists');
    });

    test('should throw when code already exists', () => {
      service.createSubject({ name: 'Mathematics', code: 'MATH101' });

      expect(() => service.createSubject({ name: 'Physics', code: 'MATH101' }))
        .toThrow('Subject code "MATH101" already exists');
    });

    test('should uppercase the subject code', () => {
      const subject = service.createSubject({ name: 'English', code: 'eng101' });
      expect(subject.code).toBe('ENG101');
    });

    test('should accept description', () => {
      const subject = service.createSubject({
        name: 'Science',
        code: 'SCI101',
        description: 'General science'
      });
      expect(subject.description).toBe('General science');
    });
  });

  describe('getSubject', () => {
    test('should return a subject by id', () => {
      const created = service.createSubject({ name: 'Math', code: 'MATH101' });
      const found = service.getSubject(created.id);
      expect(found.name).toBe('Math');
    });

    test('should throw when subject not found', () => {
      expect(() => service.getSubject(999)).toThrow('Subject with id 999 not found');
    });
  });

  describe('updateSubject', () => {
    let subject;

    beforeEach(() => {
      subject = service.createSubject({ name: 'Mathematics', code: 'MATH101' });
    });

    test('should update subject name', () => {
      const updated = service.updateSubject(subject.id, { name: 'Advanced Math' });
      expect(updated.name).toBe('Advanced Math');
    });

    test('should update subject code with uppercase', () => {
      const updated = service.updateSubject(subject.id, { code: 'adv101' });
      expect(updated.code).toBe('ADV101');
    });

    test('should throw when id is null', () => {
      expect(() => service.updateSubject(null, { name: 'New' })).toThrow('Subject id is required');
    });

    test('should throw when data is null', () => {
      expect(() => service.updateSubject(subject.id, null)).toThrow('Update data must be a non-null object');
    });

    test('should throw when name is empty', () => {
      expect(() => service.updateSubject(subject.id, { name: '' })).toThrow('Subject name cannot be empty');
    });

    test('should throw on duplicate name', () => {
      service.createSubject({ name: 'Physics', code: 'PHY101' });
      expect(() => service.updateSubject(subject.id, { name: 'Physics' }))
        .toThrow('Subject "Physics" already exists');
    });

    test('should throw on duplicate code', () => {
      service.createSubject({ name: 'Physics', code: 'PHY101' });
      expect(() => service.updateSubject(subject.id, { code: 'phy101' }))
        .toThrow('Subject code "PHY101" already exists');
    });

    test('should reject invalid status', () => {
      expect(() => service.updateSubject(subject.id, { status: 'bogus' }))
        .toThrow('Invalid subject status');
    });

    test('should activate and deactivate subject', () => {
      const deactivated = service.deactivateSubject(subject.id);
      expect(deactivated.status).toBe('inactive');

      const activated = service.activateSubject(subject.id);
      expect(activated.status).toBe('active');
    });
  });

  describe('listSubjects', () => {
    test('should list all subjects', () => {
      service.createSubject({ name: 'Math', code: 'MATH101' });
      service.createSubject({ name: 'English', code: 'ENG101' });

      const subjects = service.listSubjects();
      expect(subjects).toHaveLength(2);
    });
  });

  // --- Teacher tests ---

  describe('createTeacher', () => {
    test('should create a teacher with valid data', () => {
      const teacher = service.createTeacher({
        first_name: 'John',
        last_name: 'Smith',
        employee_number: 'TCH001',
        email: 'john@school.com'
      });

      expect(teacher).toBeDefined();
      expect(teacher.id).toBe(1);
      expect(teacher.first_name).toBe('John');
      expect(teacher.last_name).toBe('Smith');
      expect(teacher.employee_number).toBe('TCH001');
      expect(teacher.email).toBe('john@school.com');
      expect(teacher.status).toBe('active');
    });

    test('should throw when data is null', () => {
      expect(() => service.createTeacher(null)).toThrow('Teacher data must be a non-null object');
    });

    test('should throw when first_name is missing', () => {
      expect(() => service.createTeacher({ last_name: 'Smith', employee_number: 'TCH001' }))
        .toThrow('First name is required');
    });

    test('should throw when last_name is missing', () => {
      expect(() => service.createTeacher({ first_name: 'John', employee_number: 'TCH001' }))
        .toThrow('Last name is required');
    });

    test('should throw when employee_number is missing', () => {
      expect(() => service.createTeacher({ first_name: 'John', last_name: 'Smith' }))
        .toThrow('Employee number is required');
    });

    test('should throw when employee_number already exists', () => {
      service.createTeacher({ first_name: 'John', last_name: 'Smith', employee_number: 'TCH001' });

      expect(() => service.createTeacher({ first_name: 'Jane', last_name: 'Doe', employee_number: 'TCH001' }))
        .toThrow('Teacher with employee number TCH001 already exists');
    });
  });

  describe('getTeacher', () => {
    test('should return a teacher by id', () => {
      const created = service.createTeacher({ first_name: 'John', last_name: 'Smith', employee_number: 'TCH001' });
      const found = service.getTeacher(created.id);
      expect(found.first_name).toBe('John');
    });

    test('should throw when teacher not found', () => {
      expect(() => service.getTeacher(999)).toThrow('Teacher with id 999 not found');
    });

    test('should throw when id is null', () => {
      expect(() => service.getTeacher(null)).toThrow('Teacher id is required');
    });
  });

  describe('listTeachers', () => {
    test('should list all teachers', () => {
      service.createTeacher({ first_name: 'John', last_name: 'Smith', employee_number: 'TCH001' });
      service.createTeacher({ first_name: 'Jane', last_name: 'Doe', employee_number: 'TCH002' });

      const teachers = service.listTeachers();
      expect(teachers).toHaveLength(2);
    });
  });

  // --- Teacher Assignment tests ---

  describe('assignTeacher', () => {
    let teacher;
    let activeTeacher;
    let classObj;
    let subject;

    beforeEach(() => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      classObj = service.createClass(year.id, { name: 'Grade 10' });
      subject = service.createSubject({ name: 'Mathematics', code: 'MATH101' });
      activeTeacher = service.createTeacher({ first_name: 'John', last_name: 'Smith', employee_number: 'TCH001' });
    });

    test('should assign a teacher to a class', () => {
      const assignment = service.assignTeacher(activeTeacher.id, classObj.id, subject.id);

      expect(assignment).toBeDefined();
      expect(assignment.teacher_id).toBe(activeTeacher.id);
      expect(assignment.class_id).toBe(classObj.id);
      expect(assignment.subject_id).toBe(subject.id);
      expect(assignment.status).toBe('active');
    });

    test('should throw when teacher id is null', () => {
      expect(() => service.assignTeacher(null, classObj.id, subject.id)).toThrow('Teacher id is required');
    });

    test('should throw when class id is null', () => {
      expect(() => service.assignTeacher(activeTeacher.id, null, subject.id)).toThrow('Class id is required');
    });

    test('should throw when teacher does not exist', () => {
      expect(() => service.assignTeacher(999, classObj.id, subject.id))
        .toThrow('Teacher with id 999 not found');
    });

    test('should throw when assigning an inactive teacher', () => {
      const inactiveTeacher = service.createTeacher({
        first_name: 'Inactive',
        last_name: 'Teacher',
        employee_number: 'TCH099',
        status: 'inactive'
      });

      expect(() => service.assignTeacher(inactiveTeacher.id, classObj.id, subject.id))
        .toThrow('Cannot assign an inactive teacher');
    });

    test('should throw when class does not exist', () => {
      expect(() => service.assignTeacher(activeTeacher.id, 999, subject.id))
        .toThrow('Class with id 999 not found');
    });

    test('should throw when subject does not exist', () => {
      expect(() => service.assignTeacher(activeTeacher.id, classObj.id, 999))
        .toThrow('Subject with id 999 not found');
    });

    test('should throw when assigning to inactive class', () => {
      const inactiveYear = service.createAcademicYear({ name: 'Old Year', start_date: '2025-01-01', end_date: '2025-12-31' });
      const inactiveClass = service.createClass(inactiveYear.id, { name: 'Old Class', status: 'inactive' });

      expect(() => service.assignTeacher(activeTeacher.id, inactiveClass.id, subject.id))
        .toThrow('Cannot assign a teacher to an inactive class');
    });

    test('should throw on duplicate assignment for same class and subject', () => {
      service.assignTeacher(activeTeacher.id, classObj.id, subject.id);

      const teacher2 = service.createTeacher({ first_name: 'Jane', last_name: 'Doe', employee_number: 'TCH002' });
      expect(() => service.assignTeacher(teacher2.id, classObj.id, subject.id))
        .toThrow('A teacher is already assigned to this subject in this class');
    });

    test('should allow same teacher in different classes', () => {
      const class2 = service.createClass(
        service.createAcademicYear({ name: '2027-2028', start_date: '2027-01-01', end_date: '2027-12-31' }).id,
        { name: 'Grade 11' }
      );

      const a1 = service.assignTeacher(activeTeacher.id, classObj.id, subject.id);
      const a2 = service.assignTeacher(activeTeacher.id, class2.id, subject.id);

      expect(a1.id).toBe(1);
      expect(a2.id).toBe(2);
    });
  });

  describe('getAssignmentsByClass', () => {
    test('should return assignments for a class', () => {
      const year = service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      const cls = service.createClass(year.id, { name: 'Grade 10' });
      const teacher = service.createTeacher({ first_name: 'John', last_name: 'Smith', employee_number: 'TCH001' });
      const subj = service.createSubject({ name: 'Math', code: 'MATH101' });

      service.assignTeacher(teacher.id, cls.id, subj.id);

      const assignments = service.getAssignmentsByClass(cls.id);
      expect(assignments).toHaveLength(1);
      expect(assignments[0].teacher_id).toBe(teacher.id);
    });

    test('should throw when class id is null', () => {
      expect(() => service.getAssignmentsByClass(null)).toThrow('Class id is required');
    });
  });

  // --- Error propagation ---

  describe('error propagation', () => {
    test('should propagate repository errors for getAcademicYear', () => {
      const brokenDb = new Database();
      brokenDb.connect();
      const brokenRepo = new AcademicStructureRepository(brokenDb);
      const brokenService = new AcademicStructureService(brokenRepo);

      jest.spyOn(brokenRepo, 'findAcademicYearById').mockImplementation(() => {
        throw new Error('Database connection lost');
      });

      expect(() => brokenService.getAcademicYear(1)).toThrow('Database connection lost');
      brokenDb.disconnect();
    });

    test('should rollback when a multi-step operation fails in a transaction', () => {
      service.createAcademicYear({ name: '2026-2027', start_date: '2026-01-01', end_date: '2026-12-31' });
      const yearsBefore = service.listAcademicYears();
      expect(yearsBefore).toHaveLength(1);

      const spy = jest.spyOn(repository, 'saveAcademicYear').mockImplementation(() => {
        throw new Error('Transaction failure');
      });

      expect(() => service.createAcademicYear({
        name: '2027-2028',
        start_date: '2027-01-01',
        end_date: '2027-12-31'
      })).toThrow('Transaction failure');

      spy.mockRestore();
    });
  });
});
