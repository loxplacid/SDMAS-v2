const { IFeeRepository } = require('../interfaces');

class FeeRepository extends IFeeRepository {
  constructor(database) {
    super();
    this.database = database;
  }

  findFeeTypeById(id) {
    if (id === undefined || id === null) {
      throw new Error('Fee type id is required');
    }
    const result = this.database.query('SELECT * FROM fee_types WHERE id = ?', [id]);
    return result.rows[0];
  }

  findFeeTypes(filter = {}) {
    if (filter.status) {
      const result = this.database.query('SELECT * FROM fee_types WHERE status = ?', [filter.status]);
      return result.rows;
    }
    const result = this.database.query('SELECT * FROM fee_types ORDER BY name');
    return result.rows;
  }

  findFeeTypeByName(name) {
    if (!name) {
      throw new Error('Fee type name is required');
    }
    const result = this.database.query('SELECT * FROM fee_types WHERE name = ?', [name]);
    return result.rows[0];
  }

  saveFeeType(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Fee type data must be a non-null object');
    }
    const sql = 'INSERT INTO fee_types (name, description, status) VALUES (?, ?, ?)';
    const result = this.database.query(sql, [data.name, data.description || null, data.status || 'active']);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert fee type');
    }
    return { id: result.insertId, ...data, description: data.description || null };
  }

  updateFeeType(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Fee type id is required');
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
    const sql = `UPDATE fee_types SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Fee type with id ${id} not found for update`);
    }
    return this.findFeeTypeById(id);
  }

  findFeeStructureById(id) {
    if (id === undefined || id === null) {
      throw new Error('Fee structure id is required');
    }
    const result = this.database.query('SELECT * FROM fee_structures WHERE id = ?', [id]);
    return result.rows[0];
  }

  findFeeStructures(filters = {}) {
    const conditions = [];
    const params = [];
    if (filters.academic_year_id) {
      conditions.push('academic_year_id = ?');
      params.push(filters.academic_year_id);
    }
    if (filters.class_id) {
      conditions.push('class_id = ?');
      params.push(filters.class_id);
    }
    if (filters.fee_type_id) {
      conditions.push('fee_type_id = ?');
      params.push(filters.fee_type_id);
    }
    if (filters.status) {
      conditions.push('status = ?');
      params.push(filters.status);
    }
    let sql = 'SELECT * FROM fee_structures';
    if (conditions.length > 0) {
      sql += ' WHERE ' + conditions.join(' AND ');
    }
    sql += ' ORDER BY id';
    const result = this.database.query(sql, params);
    return result.rows;
  }

  findFeeStructureByYearClassAndType(academicYearId, classId, feeTypeId) {
    const result = this.database.query(
      'SELECT * FROM fee_structures WHERE academic_year_id = ? AND class_id = ? AND fee_type_id = ?',
      [academicYearId, classId, feeTypeId]
    );
    return result.rows[0];
  }

  saveFeeStructure(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Fee structure data must be a non-null object');
    }
    const sql = 'INSERT INTO fee_structures (academic_year_id, class_id, fee_type_id, amount, frequency, status) VALUES (?, ?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [
      data.academic_year_id, data.class_id, data.fee_type_id,
      data.amount, data.frequency || 'annual', data.status || 'active'
    ]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert fee structure');
    }
    return { id: result.insertId, ...data, frequency: data.frequency || 'annual' };
  }

  updateFeeStructure(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Fee structure id is required');
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
    const sql = `UPDATE fee_structures SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Fee structure with id ${id} not found for update`);
    }
    return this.findFeeStructureById(id);
  }

  findFeeDueById(id) {
    if (id === undefined || id === null) {
      throw new Error('Fee due id is required');
    }
    const result = this.database.query('SELECT * FROM fee_dues WHERE id = ?', [id]);
    return result.rows[0];
  }

  findFeeDuesByStudent(studentId, filters = {}) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    const conditions = ['student_id = ?'];
    const params = [studentId];
    if (filters.status) {
      conditions.push('status = ?');
      params.push(filters.status);
    }
    if (filters.academic_year_id) {
      conditions.push('academic_year_id = ?');
      params.push(filters.academic_year_id);
    }
    const sql = 'SELECT * FROM fee_dues WHERE ' + conditions.join(' AND ') + ' ORDER BY created_at';
    const result = this.database.query(sql, params);
    return result.rows;
  }

  findFeeDuesByAcademicYear(academicYearId) {
    const result = this.database.query('SELECT * FROM fee_dues WHERE academic_year_id = ?', [academicYearId]);
    return result.rows;
  }

  findFeeDueByStudentAndStructure(studentId, feeStructureId) {
    const result = this.database.query(
      'SELECT * FROM fee_dues WHERE student_id = ? AND fee_structure_id = ?',
      [studentId, feeStructureId]
    );
    return result.rows[0];
  }

  saveFeeDue(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Fee due data must be a non-null object');
    }
    const sql = 'INSERT INTO fee_dues (student_id, academic_year_id, fee_structure_id, original_amount, amount_paid, due_date, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [
      data.student_id, data.academic_year_id, data.fee_structure_id,
      data.original_amount, data.amount_paid || 0,
      data.due_date || null, data.status || 'unpaid',
      data.created_at, data.updated_at
    ]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert fee due');
    }
    return { id: result.insertId, ...data, amount_paid: data.amount_paid || 0 };
  }

  updateFeeDue(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Fee due id is required');
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
    const sql = `UPDATE fee_dues SET ${setClauses.join(', ')} WHERE id = ?`;
    const result = this.database.query(sql, values);
    if (result.affectedRows === 0) {
      throw new Error(`Fee due with id ${id} not found for update`);
    }
    return this.findFeeDueById(id);
  }

  findPaymentById(id) {
    if (id === undefined || id === null) {
      throw new Error('Payment id is required');
    }
    const result = this.database.query('SELECT * FROM payments WHERE id = ?', [id]);
    return result.rows[0];
  }

  findPaymentsByStudent(studentId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    const result = this.database.query('SELECT * FROM payments WHERE student_id = ? ORDER BY payment_date', [studentId]);
    return result.rows;
  }

  findPaymentsByFeeDue(feeDueId) {
    if (feeDueId === undefined || feeDueId === null) {
      throw new Error('Fee due id is required');
    }
    const result = this.database.query('SELECT * FROM payments WHERE fee_due_id = ? ORDER BY payment_date', [feeDueId]);
    return result.rows;
  }

  findPaymentsByDateRange(startDate, endDate) {
    const result = this.database.query(
      'SELECT * FROM payments WHERE payment_date >= ? AND payment_date <= ? ORDER BY payment_date',
      [startDate, endDate]
    );
    return result.rows;
  }

  findPaymentByReceiptNumber(receiptNumber) {
    if (!receiptNumber) {
      throw new Error('Receipt number is required');
    }
    const result = this.database.query('SELECT * FROM payments WHERE receipt_number = ?', [receiptNumber]);
    return result.rows[0];
  }

  savePayment(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Payment data must be a non-null object');
    }
    const sql = 'INSERT INTO payments (student_id, fee_due_id, amount, payment_date, payment_method, receipt_number, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)';
    const result = this.database.query(sql, [
      data.student_id, data.fee_due_id, data.amount,
      data.payment_date, data.payment_method || null,
      data.receipt_number || null, data.created_at
    ]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert payment');
    }
    return {
      id: result.insertId, ...data,
      payment_method: data.payment_method || null,
      receipt_number: data.receipt_number || null
    };
  }

  transaction(callback) {
    return this.database.transaction(callback);
  }
}

module.exports = FeeRepository;
