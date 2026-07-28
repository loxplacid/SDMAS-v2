const { IFeeService } = require('../interfaces');

const VALID_FEE_STATUSES = ['unpaid', 'partially_paid', 'paid'];
const VALID_FEE_TYPE_STATUSES = ['active', 'inactive'];

class FeeService extends IFeeService {
  constructor(feeRepository, studentRepository, academicStructureRepository) {
    super();
    this.feeRepository = feeRepository;
    this.studentRepository = studentRepository;
    this.academicStructureRepository = academicStructureRepository;
  }

  createFeeType(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Fee type data must be a non-null object');
    }
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
      throw new Error('Fee type name is required');
    }

    const trimmedName = data.name.trim();
    const existing = this.feeRepository.findFeeTypeByName(trimmedName);
    if (existing) {
      throw new Error(`Fee type "${trimmedName}" already exists`);
    }

    return this.feeRepository.saveFeeType({
      name: trimmedName,
      description: data.description || null,
      status: 'active'
    });
  }

  getFeeType(id) {
    if (id === undefined || id === null) {
      throw new Error('Fee type id is required');
    }
    const feeType = this.feeRepository.findFeeTypeById(id);
    if (!feeType) {
      throw new Error(`Fee type with id ${id} not found`);
    }
    return feeType;
  }

  updateFeeType(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Fee type id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getFeeType(id);

    const updateData = {};
    if (data.name !== undefined) {
      if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
        throw new Error('Fee type name cannot be empty');
      }
      const trimmedName = data.name.trim();
      if (trimmedName !== existing.name) {
        const duplicate = this.feeRepository.findFeeTypeByName(trimmedName);
        if (duplicate) {
          throw new Error(`Fee type "${trimmedName}" already exists`);
        }
      }
      updateData.name = trimmedName;
    }
    if (data.description !== undefined) {
      updateData.description = data.description;
    }
    if (data.status !== undefined) {
      if (!VALID_FEE_TYPE_STATUSES.includes(data.status)) {
        throw new Error('Invalid fee type status');
      }
      updateData.status = data.status;
    }

    if (Object.keys(updateData).length === 0) {
      throw new Error('No fields to update');
    }

    this.feeRepository.updateFeeType(id, updateData);
    return this.feeRepository.findFeeTypeById(id);
  }

  deactivateFeeType(id) {
    return this.updateFeeType(id, { status: 'inactive' });
  }

  listFeeTypes(filter = {}) {
    if (filter.status && !VALID_FEE_TYPE_STATUSES.includes(filter.status)) {
      throw new Error('Invalid status filter for fee types');
    }
    return this.feeRepository.findFeeTypes(filter);
  }

  createFeeStructure(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Fee structure data must be a non-null object');
    }

    if (!data.academic_year_id) {
      throw new Error('Academic year id is required');
    }
    if (!data.class_id) {
      throw new Error('Class id is required');
    }
    if (!data.fee_type_id) {
      throw new Error('Fee type id is required');
    }
    if (data.amount === undefined || data.amount === null || !Number.isInteger(data.amount) || data.amount <= 0) {
      throw new Error('Fee amount must be a positive integer');
    }

    const academicYear = this.academicStructureRepository.findAcademicYearById(data.academic_year_id);
    if (!academicYear) {
      throw new Error(`Academic year with id ${data.academic_year_id} not found`);
    }
    if (academicYear.status !== 'active') {
      throw new Error('Cannot create fee structure for an inactive academic year');
    }

    const classObj = this.academicStructureRepository.findClassById(data.class_id);
    if (!classObj) {
      throw new Error(`Class with id ${data.class_id} not found`);
    }
    if (classObj.status !== 'active') {
      throw new Error('Cannot create fee structure for an inactive class');
    }

    const feeType = this.feeRepository.findFeeTypeById(data.fee_type_id);
    if (!feeType) {
      throw new Error(`Fee type with id ${data.fee_type_id} not found`);
    }
    if (feeType.status !== 'active') {
      throw new Error('Cannot create fee structure for an inactive fee type');
    }

    const duplicate = this.feeRepository.findFeeStructureByYearClassAndType(
      data.academic_year_id, data.class_id, data.fee_type_id
    );
    if (duplicate) {
      throw new Error('Fee structure already exists for this academic year, class, and fee type');
    }

    return this.feeRepository.saveFeeStructure({
      academic_year_id: data.academic_year_id,
      class_id: data.class_id,
      fee_type_id: data.fee_type_id,
      amount: data.amount,
      frequency: data.frequency || 'annual',
      status: data.status || 'active'
    });
  }

  getFeeStructure(id) {
    if (id === undefined || id === null) {
      throw new Error('Fee structure id is required');
    }
    const structure = this.feeRepository.findFeeStructureById(id);
    if (!structure) {
      throw new Error(`Fee structure with id ${id} not found`);
    }
    return structure;
  }

  updateFeeStructure(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Fee structure id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getFeeStructure(id);

    const updateData = {};
    if (data.amount !== undefined) {
      if (!Number.isInteger(data.amount) || data.amount <= 0) {
        throw new Error('Fee amount must be a positive integer');
      }
      updateData.amount = data.amount;
    }
    if (data.frequency !== undefined) {
      updateData.frequency = data.frequency;
    }
    if (data.status !== undefined) {
      if (!['active', 'inactive'].includes(data.status)) {
        throw new Error('Invalid fee structure status');
      }
      updateData.status = data.status;
    }

    if (data.academic_year_id !== undefined) {
      const year = this.academicStructureRepository.findAcademicYearById(data.academic_year_id);
      if (!year) throw new Error(`Academic year with id ${data.academic_year_id} not found`);
      updateData.academic_year_id = data.academic_year_id;
    }
    if (data.class_id !== undefined) {
      const cls = this.academicStructureRepository.findClassById(data.class_id);
      if (!cls) throw new Error(`Class with id ${data.class_id} not found`);
      updateData.class_id = data.class_id;
    }
    if (data.fee_type_id !== undefined) {
      const ft = this.feeRepository.findFeeTypeById(data.fee_type_id);
      if (!ft) throw new Error(`Fee type with id ${data.fee_type_id} not found`);
      updateData.fee_type_id = data.fee_type_id;
    }

    if (Object.keys(updateData).length === 0) {
      throw new Error('No fields to update');
    }

    this.feeRepository.updateFeeStructure(id, updateData);
    return this.feeRepository.findFeeStructureById(id);
  }

  listFeeStructures(filters = {}) {
    if (filters.status && !['active', 'inactive'].includes(filters.status)) {
      throw new Error('Invalid status filter for fee structures');
    }
    return this.feeRepository.findFeeStructures(filters);
  }

  getStudentFees(studentId, academicYearId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }

    const student = this.studentRepository.findById(studentId);
    if (!student) {
      throw new Error(`Student with id ${studentId} not found`);
    }

    const academicYear = this.academicStructureRepository.findAcademicYearById(academicYearId);
    if (!academicYear) {
      throw new Error(`Academic year with id ${academicYearId} not found`);
    }

    const enrollment = this.studentRepository.findEnrollment(studentId, academicYearId);
    if (!enrollment) {
      throw new Error(`Student ${studentId} is not enrolled in academic year ${academicYearId}`);
    }

    const feeStructures = this.feeRepository.findFeeStructures({
      academic_year_id: academicYearId,
      class_id: enrollment.class_id,
      status: 'active'
    });

    return feeStructures.map(fs => {
      const feeType = this.feeRepository.findFeeTypeById(fs.fee_type_id);
      return {
        ...fs,
        fee_type_name: feeType ? feeType.name : 'Unknown'
      };
    });
  }

  createFeeDues(studentId, academicYearId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }

    const student = this.studentRepository.findById(studentId);
    if (!student) {
      throw new Error(`Student with id ${studentId} not found`);
    }

    const academicYear = this.academicStructureRepository.findAcademicYearById(academicYearId);
    if (!academicYear) {
      throw new Error(`Academic year with id ${academicYearId} not found`);
    }

    const enrollment = this.studentRepository.findEnrollment(studentId, academicYearId);
    if (!enrollment) {
      throw new Error(`Student ${studentId} is not enrolled in academic year ${academicYearId}`);
    }

    if (enrollment.status !== 'active') {
      throw new Error('Cannot create fee dues for an inactive enrollment');
    }

    const feeStructures = this.feeRepository.findFeeStructures({
      academic_year_id: academicYearId,
      class_id: enrollment.class_id,
      status: 'active'
    });

    if (feeStructures.length === 0) {
      throw new Error(`No active fee structures found for class ${enrollment.class_id} in academic year ${academicYearId}`);
    }

    const createdDues = [];
    this.feeRepository.transaction(() => {
      for (const fs of feeStructures) {
        const existing = this.feeRepository.findFeeDueByStudentAndStructure(studentId, fs.id);
        if (existing) {
          throw new Error(`Fee due already exists for student ${studentId} and fee structure ${fs.id}`);
        }

        const now = new Date().toISOString();
        const due = this.feeRepository.saveFeeDue({
          student_id: studentId,
          academic_year_id: academicYearId,
          fee_structure_id: fs.id,
          original_amount: fs.amount,
          amount_paid: 0,
          due_date: null,
          status: 'unpaid',
          created_at: now,
          updated_at: now
        });
        createdDues.push(due);
      }
    });

    return createdDues;
  }

  recordPayment(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Payment data must be a non-null object');
    }

    if (data.student_id === undefined || data.student_id === null) {
      throw new Error('Student id is required');
    }
    if (data.fee_due_id === undefined || data.fee_due_id === null) {
      throw new Error('Fee due id is required');
    }
    if (data.amount === undefined || data.amount === null || !Number.isInteger(data.amount) || data.amount <= 0) {
      throw new Error('Payment amount must be a positive integer');
    }

    const student = this.studentRepository.findById(data.student_id);
    if (!student) {
      throw new Error(`Student with id ${data.student_id} not found`);
    }

    const feeDue = this.feeRepository.findFeeDueById(data.fee_due_id);
    if (!feeDue) {
      throw new Error(`Fee due with id ${data.fee_due_id} not found`);
    }
    if (feeDue.student_id !== data.student_id) {
      throw new Error('Fee due does not belong to the specified student');
    }
    if (feeDue.status === 'paid') {
      throw new Error('Fee due is already fully paid');
    }

    if (data.receipt_number) {
      const existingReceipt = this.feeRepository.findPaymentByReceiptNumber(data.receipt_number);
      if (existingReceipt) {
        throw new Error(`Payment with receipt number ${data.receipt_number} already exists`);
      }
    }

    const newAmountPaid = feeDue.amount_paid + data.amount;
    if (newAmountPaid > feeDue.original_amount) {
      throw new Error('Payment would exceed outstanding balance');
    }

    const newStatus = newAmountPaid >= feeDue.original_amount ? 'paid' : 'partially_paid';
    const now = new Date().toISOString();

    let savedPayment;
    this.feeRepository.transaction(() => {
      savedPayment = this.feeRepository.savePayment({
        student_id: data.student_id,
        fee_due_id: data.fee_due_id,
        amount: data.amount,
        payment_date: data.payment_date || now.slice(0, 10),
        payment_method: data.payment_method || null,
        receipt_number: data.receipt_number || null,
        created_at: now
      });

      this.feeRepository.updateFeeDue(data.fee_due_id, {
        amount_paid: newAmountPaid,
        status: newStatus,
        updated_at: now
      });
    });

    return {
      payment: savedPayment,
      fee_due: {
        id: feeDue.id,
        original_amount: feeDue.original_amount,
        amount_paid: newAmountPaid,
        balance: feeDue.original_amount - newAmountPaid,
        status: newStatus
      }
    };
  }

  getPayment(id) {
    if (id === undefined || id === null) {
      throw new Error('Payment id is required');
    }
    const payment = this.feeRepository.findPaymentById(id);
    if (!payment) {
      throw new Error(`Payment with id ${id} not found`);
    }
    return payment;
  }

  getStudentPayments(studentId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    return this.feeRepository.findPaymentsByStudent(studentId);
  }

  getFeeDuePayments(feeDueId) {
    if (feeDueId === undefined || feeDueId === null) {
      throw new Error('Fee due id is required');
    }
    return this.feeRepository.findPaymentsByFeeDue(feeDueId);
  }

  getPaymentsByDateRange(startDate, endDate) {
    if (!startDate || !endDate) {
      throw new Error('Start date and end date are required');
    }
    return this.feeRepository.findPaymentsByDateRange(startDate, endDate);
  }

  getPaymentByReceiptNumber(receiptNumber) {
    if (!receiptNumber) {
      throw new Error('Receipt number is required');
    }
    const payment = this.feeRepository.findPaymentByReceiptNumber(receiptNumber);
    if (!payment) {
      throw new Error(`Payment with receipt number ${receiptNumber} not found`);
    }
    return payment;
  }

  getStudentFinancialSummary(studentId, academicYearId) {
    if (studentId === undefined || studentId === null) {
      throw new Error('Student id is required');
    }
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }

    const feeDues = this.feeRepository.findFeeDuesByStudent(studentId, { academic_year_id: academicYearId });

    const summary = {
      student_id: studentId,
      academic_year_id: academicYearId,
      total_fees_assigned: 0,
      total_paid: 0,
      total_outstanding: 0,
      unpaid_count: 0,
      partially_paid_count: 0,
      paid_count: 0
    };

    for (const due of feeDues) {
      summary.total_fees_assigned += due.original_amount;
      summary.total_paid += due.amount_paid;
      if (due.status === 'unpaid') summary.unpaid_count++;
      if (due.status === 'partially_paid') summary.partially_paid_count++;
      if (due.status === 'paid') summary.paid_count++;
    }

    summary.total_outstanding = summary.total_fees_assigned - summary.total_paid;

    return summary;
  }

  getClassFinancialSummary(classId, academicYearId) {
    if (classId === undefined || classId === null) {
      throw new Error('Class id is required');
    }
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }

    const classEnrollments = this.studentRepository.findEnrollmentsByAcademicYear(academicYearId)
      .filter(e => e.class_id === classId);
    const studentIds = classEnrollments.map(e => e.student_id);
    const allDues = this.feeRepository.findFeeDuesByAcademicYear(academicYearId);
    const classDues = allDues.filter(d => studentIds.includes(d.student_id));

    const summary = {
      class_id: classId,
      academic_year_id: academicYearId,
      total_students: studentIds.length,
      total_fees_assigned: 0,
      total_collected: 0,
      total_outstanding: 0,
      students_with_outstanding: new Set()
    };

    for (const due of classDues) {
      summary.total_fees_assigned += due.original_amount;
      summary.total_collected += due.amount_paid;
      if (due.amount_paid < due.original_amount) {
        summary.students_with_outstanding.add(due.student_id);
      }
    }

    summary.total_outstanding = summary.total_fees_assigned - summary.total_collected;
    summary.students_with_outstanding = summary.students_with_outstanding.size;

    return summary;
  }
}

module.exports = FeeService;
