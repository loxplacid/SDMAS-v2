const { IStudentService } = require('../interfaces');

class StudentService extends IStudentService {
  constructor(studentRepository) {
    super();
    this.studentRepository = studentRepository;
  }

  createStudent(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Student data must be a non-null object');
    }
    if (!data.first_name || typeof data.first_name !== 'string' || data.first_name.trim().length === 0) {
      throw new Error('First name is required');
    }
    if (!data.last_name || typeof data.last_name !== 'string' || data.last_name.trim().length === 0) {
      throw new Error('Last name is required');
    }
    if (!data.student_number || typeof data.student_number !== 'string' || data.student_number.trim().length === 0) {
      throw new Error('Student number is required');
    }
    if (data.email && typeof data.email === 'string' && data.email.length > 0) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(data.email)) {
        throw new Error('Invalid email format');
      }
    }

    const existing = this.studentRepository.findByStudentNumber(data.student_number);
    if (existing) {
      throw new Error(`Student with number ${data.student_number} already exists`);
    }

    const now = new Date().toISOString();
    const student = {
      first_name: data.first_name.trim(),
      last_name: data.last_name.trim(),
      student_number: data.student_number.trim(),
      email: data.email || null,
      date_of_birth: data.date_of_birth || null,
      status: 'active',
      created_at: now,
      updated_at: now
    };

    return this.studentRepository.save(student);
  }

  getStudent(id) {
    if (id === undefined || id === null) {
      throw new Error('Student id is required');
    }
    const student = this.studentRepository.findById(id);
    if (!student) {
      throw new Error(`Student with id ${id} not found`);
    }
    return student;
  }

  findByStudentNumber(studentNumber) {
    if (!studentNumber) {
      throw new Error('Student number is required');
    }
    const student = this.studentRepository.findByStudentNumber(studentNumber);
    if (!student) {
      throw new Error(`Student with number ${studentNumber} not found`);
    }
    return student;
  }

  updateStudent(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Student id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    this.getStudent(id);

    if (data.first_name !== undefined) {
      if (!data.first_name || typeof data.first_name !== 'string' || data.first_name.trim().length === 0) {
        throw new Error('First name cannot be empty');
      }
      data.first_name = data.first_name.trim();
    }
    if (data.last_name !== undefined) {
      if (!data.last_name || typeof data.last_name !== 'string' || data.last_name.trim().length === 0) {
        throw new Error('Last name cannot be empty');
      }
      data.last_name = data.last_name.trim();
    }
    if (data.email !== undefined && data.email !== null) {
      if (typeof data.email !== 'string' || data.email.trim().length === 0) {
        throw new Error('Email cannot be empty');
      }
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(data.email.trim())) {
        throw new Error('Invalid email format');
      }
      data.email = data.email.trim();
    }
    if (data.student_number !== undefined) {
      throw new Error('Student number cannot be changed');
    }
    if (data.status !== undefined && !['active', 'inactive', 'graduated'].includes(data.status)) {
      throw new Error('Invalid status value');
    }

    data.updated_at = new Date().toISOString();
    this.studentRepository.update(id, data);
    return this.getStudent(id);
  }

  deactivateStudent(id) {
    if (id === undefined || id === null) {
      throw new Error('Student id is required');
    }
    const student = this.getStudent(id);
    if (student.status === 'inactive') {
      throw new Error(`Student with id ${id} is already inactive`);
    }
    return this.studentRepository.update(id, {
      status: 'inactive',
      updated_at: new Date().toISOString()
    });
  }

  reactivateStudent(id) {
    if (id === undefined || id === null) {
      throw new Error('Student id is required');
    }
    const student = this.getStudent(id);
    if (student.status === 'active') {
      throw new Error(`Student with id ${id} is already active`);
    }
    return this.studentRepository.update(id, {
      status: 'active',
      updated_at: new Date().toISOString()
    });
  }

  listStudents(filter = {}) {
    const validStatuses = ['active', 'inactive', 'graduated'];
    if (filter.status && !validStatuses.includes(filter.status)) {
      throw new Error('Invalid status filter');
    }
    return this.studentRepository.findAll(filter);
  }

  searchStudents(query) {
    if (!query || typeof query !== 'string' || query.trim().length === 0) {
      throw new Error('Search query is required');
    }
    const term = query.trim().toLowerCase();
    const allStudents = this.studentRepository.findAll();
    return allStudents.filter(s =>
      (s.first_name && s.first_name.toLowerCase().includes(term)) ||
      (s.last_name && s.last_name.toLowerCase().includes(term)) ||
      (s.student_number && s.student_number.toLowerCase().includes(term)) ||
      (s.email && s.email.toLowerCase().includes(term))
    );
  }

  enrollStudent(studentId, enrollmentData) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    if (!enrollmentData || typeof enrollmentData !== 'object' || Array.isArray(enrollmentData)) {
      throw new Error('Enrollment data must be a non-null object');
    }

    const student = this.getStudent(studentId);
    if (student.status !== 'active') {
      throw new Error('Cannot enroll an inactive student');
    }

    if (!enrollmentData.academic_year_id) {
      throw new Error('Academic year id is required');
    }

    const academicYear = this.studentRepository.findAcademicYear(enrollmentData.academic_year_id);
    if (!academicYear) {
      throw new Error(`Academic year with id ${enrollmentData.academic_year_id} not found`);
    }
    if (academicYear.status !== 'active') {
      throw new Error('Cannot enroll in an inactive academic year');
    }

    if (enrollmentData.class_id) {
      const classObj = this.studentRepository.findClass(enrollmentData.class_id);
      if (!classObj) {
        throw new Error(`Class with id ${enrollmentData.class_id} not found`);
      }
      if (classObj.status !== 'active') {
        throw new Error('Cannot enroll in an inactive class');
      }
    }

    if (enrollmentData.section_id) {
      const section = this.studentRepository.findSection(enrollmentData.section_id);
      if (!section) {
        throw new Error(`Section with id ${enrollmentData.section_id} not found`);
      }
      if (section.status !== 'active') {
        throw new Error('Cannot enroll in an inactive section');
      }
    }

    const existingEnrollment = this.studentRepository.findEnrollment(studentId, enrollmentData.academic_year_id);
    if (existingEnrollment) {
      throw new Error(`Student is already enrolled in academic year ${enrollmentData.academic_year_id}`);
    }

    this.studentRepository.transaction(() => {
      this.studentRepository.createEnrollment({
        student_id: studentId,
        academic_year_id: enrollmentData.academic_year_id,
        class_id: enrollmentData.class_id || null,
        section_id: enrollmentData.section_id || null,
        enrolled_at: new Date().toISOString()
      });
    });

    return this.studentRepository.findEnrollment(studentId, enrollmentData.academic_year_id);
  }
}

module.exports = StudentService;
