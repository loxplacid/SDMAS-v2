const { IStudentRepository } = require('../interfaces');

class StudentRepository extends IStudentRepository {
  constructor(database) {
    super();
    this.database = database;
  }

  findById(id) {
    if (id === undefined || id === null) {
      throw new Error('Id is required');
    }
    const result = this.database.query('SELECT * FROM students WHERE id = ?', [id]);
    return result.rows[0];
  }

  findByStudentNumber(studentNumber) {
    if (!studentNumber) {
      throw new Error('Student number is required');
    }
    const result = this.database.query('SELECT * FROM students WHERE student_number = ?', [studentNumber]);
    return result.rows[0];
  }

  findAll(filter = {}) {
    if (filter.status) {
      const result = this.database.query('SELECT * FROM students WHERE status = ?', [filter.status]);
      return result.rows;
    }
    const result = this.database.query('SELECT * FROM students');
    return result.rows;
  }

  save(student) {
    if (!student || typeof student !== 'object' || Array.isArray(student)) {
      throw new Error('Student must be a non-null object');
    }
    const sql = 'INSERT INTO students (first_name, last_name, student_number, email, date_of_birth, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [
      student.first_name, student.last_name, student.student_number,
      student.email || null, student.date_of_birth || null,
      student.status || 'active', student.created_at, student.updated_at
    ]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert student');
    }
    return {
      id: result.insertId,
      ...student,
      email: student.email || null,
      date_of_birth: student.date_of_birth || null,
      status: student.status || 'active'
    };
  }

  update(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Data must be a non-null object');
    }
    const setClauses = [];
    const values = [];
    for (const [key, value] of Object.entries(data)) {
      if (key === 'id') continue;
      setClauses.push(`${key} = ?`);
      values.push(value);
    }
    if (setClauses.length === 0) {
      throw new Error('No fields to update');
    }
    values.push(id);
    const sql = `UPDATE students SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Student with id ${id} not found for update`);
    }
    return this.findById(id);
  }

  createEnrollment(enrollment) {
    if (!enrollment || typeof enrollment !== 'object') {
      throw new Error('Enrollment must be a non-null object');
    }
    const sql = 'INSERT INTO enrollments (student_id, academic_year_id, class_id, section_id, status, enrolled_at) VALUES (?, ?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [
      enrollment.student_id, enrollment.academic_year_id,
      enrollment.class_id || null, enrollment.section_id || null,
      enrollment.status || 'active', enrollment.enrolled_at
    ]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to create enrollment');
    }
    return { id: result.insertId, ...enrollment };
  }

  findEnrollment(studentId, academicYearId) {
    const result = this.database.query(
      'SELECT * FROM enrollments WHERE student_id = ? AND academic_year_id = ?',
      [studentId, academicYearId]
    );
    return result.rows[0];
  }

  findEnrollmentsByStudent(studentId) {
    const result = this.database.query('SELECT * FROM enrollments WHERE student_id = ?', [studentId]);
    return result.rows;
  }

  findEnrollmentsByAcademicYear(academicYearId) {
    const result = this.database.query('SELECT * FROM enrollments WHERE academic_year_id = ?', [academicYearId]);
    return result.rows;
  }

  findEnrollmentsBySection(sectionId) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    const result = this.database.query('SELECT * FROM enrollments WHERE section_id = ?', [sectionId]);
    return result.rows;
  }

  findAcademicYear(id) {
    const result = this.database.query('SELECT * FROM academic_years WHERE id = ?', [id]);
    return result.rows[0];
  }

  findAcademicYears(filter = {}) {
    if (filter.status) {
      const result = this.database.query('SELECT * FROM academic_years WHERE status = ?', [filter.status]);
      return result.rows;
    }
    const result = this.database.query('SELECT * FROM academic_years');
    return result.rows;
  }

  findClass(id) {
    const result = this.database.query('SELECT * FROM classes WHERE id = ?', [id]);
    return result.rows[0];
  }

  findSection(id) {
    const result = this.database.query('SELECT * FROM sections WHERE id = ?', [id]);
    return result.rows[0];
  }

  transaction(callback) {
    return this.database.transaction(callback);
  }
}

module.exports = StudentRepository;
