const { IAttendanceRepository } = require('../interfaces');

class AttendanceRepository extends IAttendanceRepository {
  constructor(database) {
    super();
    this.database = database;
  }

  findById(id) {
    if (id === undefined || id === null) {
      throw new Error('Attendance record id is required');
    }
    const result = this.database.query('SELECT * FROM attendance_records WHERE id = ?', [id]);
    return result.rows[0];
  }

  save(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Attendance data must be a non-null object');
    }
    const sql = 'INSERT INTO attendance_records (student_id, academic_year_id, class_id, section_id, attendance_date, status, notes, recorded_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [
      data.student_id, data.academic_year_id, data.class_id, data.section_id,
      data.attendance_date, data.status, data.notes || null,
      data.recorded_at, data.updated_at
    ]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert attendance record');
    }
    return { id: result.insertId, ...data, notes: data.notes || null };
  }

  update(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Attendance record id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
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
    const sql = `UPDATE attendance_records SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Attendance record with id ${id} not found for update`);
    }
    return this.findById(id);
  }

  findByStudentAndDateRange(studentId, startDate, endDate) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    const result = this.database.query(
      'SELECT * FROM attendance_records WHERE student_id = ? AND attendance_date >= ? AND attendance_date <= ? ORDER BY attendance_date',
      [studentId, startDate, endDate]
    );
    return result.rows;
  }

  findBySectionAndDate(sectionId, date) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    if (!date) {
      throw new Error('Date is required');
    }
    const result = this.database.query(
      'SELECT * FROM attendance_records WHERE section_id = ? AND attendance_date = ?',
      [sectionId, date]
    );
    return result.rows;
  }

  findBySectionAndDateRange(sectionId, startDate, endDate) {
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    const result = this.database.query(
      'SELECT * FROM attendance_records WHERE section_id = ? AND attendance_date >= ? AND attendance_date <= ? ORDER BY attendance_date',
      [sectionId, startDate, endDate]
    );
    return result.rows;
  }

  findByStudentAndFilters(studentId, filters = {}) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    let sql = 'SELECT * FROM attendance_records WHERE student_id = ?';
    const params = [studentId];

    if (filters.academic_year_id) {
      sql += ' AND academic_year_id = ?';
      params.push(filters.academic_year_id);
    }
    if (filters.class_id) {
      sql += ' AND class_id = ?';
      params.push(filters.class_id);
    }
    if (filters.section_id) {
      sql += ' AND section_id = ?';
      params.push(filters.section_id);
    }
    if (filters.status) {
      sql += ' AND status = ?';
      params.push(filters.status);
    }
    if (filters.start_date) {
      sql += ' AND attendance_date >= ?';
      params.push(filters.start_date);
    }
    if (filters.end_date) {
      sql += ' AND attendance_date <= ?';
      params.push(filters.end_date);
    }

    sql += ' ORDER BY attendance_date';
    const result = this.database.query(sql, params);
    return result.rows;
  }

  findDuplicate(studentId, date, sectionId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    if (!date) {
      throw new Error('Date is required');
    }
    if (sectionId === undefined || sectionId === null) {
      throw new Error('Section id is required');
    }
    const result = this.database.query(
      'SELECT * FROM attendance_records WHERE student_id = ? AND attendance_date = ? AND section_id = ?',
      [studentId, date, sectionId]
    );
    return result.rows[0];
  }

  transaction(callback) {
    return this.database.transaction(callback);
  }
}

module.exports = AttendanceRepository;
