const { IAcademicStructureRepository } = require('../interfaces');

class AcademicStructureRepository extends IAcademicStructureRepository {
  constructor(database) {
    super();
    this.database = database;
  }

  // Academic years

  findAcademicYearById(id) {
    if (id === undefined || id === null) {
      throw new Error('Academic year id is required');
    }
    const result = this.database.query('SELECT * FROM academic_years WHERE id = ?', [id]);
    return result.rows[0];
  }

  findAcademicYears(filter = {}) {
    if (filter.status) {
      const result = this.database.query('SELECT * FROM academic_years WHERE status = ?', [filter.status]);
      return result.rows;
    }
    const result = this.database.query('SELECT * FROM academic_years ORDER BY start_date');
    return result.rows;
  }

  findAcademicYearByName(name) {
    const result = this.database.query('SELECT * FROM academic_years WHERE name = ?', [name]);
    return result.rows[0];
  }

  saveAcademicYear(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Academic year data must be a non-null object');
    }
    const sql = 'INSERT INTO academic_years (name, start_date, end_date, status) VALUES (?, ?, ?, ?)';
    const result = this.database.query(sql, [data.name, data.start_date, data.end_date, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert academic year');
    }
    return { id: result.insertId, ...data };
  }

  updateAcademicYear(id, data) {
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
    const sql = `UPDATE academic_years SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Academic year with id ${id} not found for update`);
    }
    return this.findAcademicYearById(id);
  }

  // Terms

  findTermById(id) {
    const result = this.database.query('SELECT * FROM terms WHERE id = ?', [id]);
    return result.rows[0];
  }

  findTermsByAcademicYear(academicYearId) {
    const result = this.database.query('SELECT * FROM terms WHERE academic_year_id = ? ORDER BY start_date', [academicYearId]);
    return result.rows;
  }

  findOverlappingTerm(academicYearId, startDate, endDate, excludeId) {
    let sql = 'SELECT * FROM terms WHERE academic_year_id = ? AND start_date < ? AND end_date > ?';
    const params = [academicYearId, endDate, startDate];
    if (excludeId !== undefined && excludeId !== null) {
      sql += ' AND id != ?';
      params.push(excludeId);
    }
    const result = this.database.query(sql, params);
    return result.rows[0];
  }

  saveTerm(data) {
    const sql = 'INSERT INTO terms (academic_year_id, name, start_date, end_date, status) VALUES (?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [data.academic_year_id, data.name, data.start_date, data.end_date, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert term');
    }
    return { id: result.insertId, ...data };
  }

  updateTerm(id, data) {
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
    const sql = `UPDATE terms SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Term with id ${id} not found for update`);
    }
    return this.findTermById(id);
  }

  // Classes

  findClassById(id) {
    const result = this.database.query('SELECT * FROM classes WHERE id = ?', [id]);
    return result.rows[0];
  }

  findClassesByAcademicYear(academicYearId) {
    const result = this.database.query('SELECT * FROM classes WHERE academic_year_id = ?', [academicYearId]);
    return result.rows;
  }

  findClassByNameAndYear(name, academicYearId) {
    const result = this.database.query('SELECT * FROM classes WHERE name = ? AND academic_year_id = ?', [name, academicYearId]);
    return result.rows[0];
  }

  saveClass(data) {
    const sql = 'INSERT INTO classes (name, academic_year_id, status) VALUES (?, ?, ?)';
    const result = this.database.query(sql, [data.name, data.academic_year_id, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert class');
    }
    return { id: result.insertId, ...data };
  }

  updateClass(id, data) {
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
    const sql = `UPDATE classes SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Class with id ${id} not found for update`);
    }
    return this.findClassById(id);
  }

  // Sections

  findSectionById(id) {
    const result = this.database.query('SELECT * FROM sections WHERE id = ?', [id]);
    return result.rows[0];
  }

  findSectionsByClass(classId) {
    const result = this.database.query('SELECT * FROM sections WHERE class_id = ?', [classId]);
    return result.rows;
  }

  findSectionByNameAndClass(name, classId) {
    const result = this.database.query('SELECT * FROM sections WHERE name = ? AND class_id = ?', [name, classId]);
    return result.rows[0];
  }

  saveSection(data) {
    const sql = 'INSERT INTO sections (name, class_id, status) VALUES (?, ?, ?)';
    const result = this.database.query(sql, [data.name, data.class_id, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert section');
    }
    return { id: result.insertId, ...data };
  }

  updateSection(id, data) {
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
    const sql = `UPDATE sections SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Section with id ${id} not found for update`);
    }
    return this.findSectionById(id);
  }

  // Subjects

  findSubjectById(id) {
    const result = this.database.query('SELECT * FROM subjects WHERE id = ?', [id]);
    return result.rows[0];
  }

  findSubjects() {
    const result = this.database.query('SELECT * FROM subjects ORDER BY name');
    return result.rows;
  }

  findSubjectByName(name) {
    const result = this.database.query('SELECT * FROM subjects WHERE name = ?', [name]);
    return result.rows[0];
  }

  findSubjectByCode(code) {
    const result = this.database.query('SELECT * FROM subjects WHERE code = ?', [code]);
    return result.rows[0];
  }

  saveSubject(data) {
    const sql = 'INSERT INTO subjects (name, code, description, status) VALUES (?, ?, ?, ?)';
    const result = this.database.query(sql, [data.name, data.code, data.description || null, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert subject');
    }
    return { id: result.insertId, ...data };
  }

  updateSubject(id, data) {
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
    const sql = `UPDATE subjects SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Subject with id ${id} not found for update`);
    }
    return this.findSubjectById(id);
  }

  // Teachers

  findTeacherById(id) {
    const result = this.database.query('SELECT * FROM teachers WHERE id = ?', [id]);
    return result.rows[0];
  }

  findTeachers() {
    const result = this.database.query('SELECT * FROM teachers ORDER BY last_name, first_name');
    return result.rows;
  }

  findTeacherByEmployeeNumber(employeeNumber) {
    const result = this.database.query('SELECT * FROM teachers WHERE employee_number = ?', [employeeNumber]);
    return result.rows[0];
  }

  saveTeacher(data) {
    const sql = 'INSERT INTO teachers (first_name, last_name, employee_number, email, status) VALUES (?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [data.first_name, data.last_name, data.employee_number, data.email || null, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert teacher');
    }
    return { id: result.insertId, ...data };
  }

  updateTeacher(id, data) {
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
    const sql = `UPDATE teachers SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Teacher with id ${id} not found for update`);
    }
    return this.findTeacherById(id);
  }

  // Teacher assignments

  findTeacherAssignmentById(id) {
    const result = this.database.query('SELECT * FROM teacher_assignments WHERE id = ?', [id]);
    return result.rows[0];
  }

  findAssignmentsByClass(classId) {
    const result = this.database.query('SELECT * FROM teacher_assignments WHERE class_id = ?', [classId]);
    return result.rows;
  }

  findAssignmentsByTeacher(teacherId) {
    const result = this.database.query('SELECT * FROM teacher_assignments WHERE teacher_id = ?', [teacherId]);
    return result.rows;
  }

  findAssignmentByClassAndSubject(classId, subjectId) {
    const result = this.database.query('SELECT * FROM teacher_assignments WHERE class_id = ? AND subject_id = ?', [classId, subjectId]);
    return result.rows[0];
  }

  saveTeacherAssignment(data) {
    const sql = 'INSERT INTO teacher_assignments (teacher_id, class_id, subject_id, status) VALUES (?, ?, ?, ?)';
    const result = this.database.query(sql, [data.teacher_id, data.class_id, data.subject_id || null, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to create teacher assignment');
    }
    return { id: result.insertId, ...data };
  }

  removeTeacherAssignment(id) {
    const result = this.database.query('DELETE FROM teacher_assignments WHERE id = ?', [id]);
    if (result.affectedRows === 0) {
      throw new Error(`Teacher assignment with id ${id} not found`);
    }
    return true;
  }

  transaction(callback) {
    return this.database.transaction(callback);
  }
}

module.exports = AcademicStructureRepository;
