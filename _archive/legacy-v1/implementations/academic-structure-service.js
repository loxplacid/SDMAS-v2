const { IAcademicStructureService } = require('../interfaces');

class AcademicStructureService extends IAcademicStructureService {
  constructor(academicStructureRepository) {
    super();
    this.repository = academicStructureRepository;
  }

  // --- Academic Year operations ---

  createAcademicYear(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Academic year data must be a non-null object');
    }
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
      throw new Error('Academic year name is required');
    }
    if (!data.start_date || typeof data.start_date !== 'string') {
      throw new Error('Academic year start date is required');
    }
    if (!data.end_date || typeof data.end_date !== 'string') {
      throw new Error('Academic year end date is required');
    }

    const trimmedName = data.name.trim();
    if (data.end_date <= data.start_date) {
      throw new Error('Academic year end date must be after start date');
    }

    const existing = this.repository.findAcademicYearByName(trimmedName);
    if (existing) {
      throw new Error(`Academic year "${trimmedName}" already exists`);
    }

    return this.repository.saveAcademicYear({
      name: trimmedName,
      start_date: data.start_date,
      end_date: data.end_date,
      status: data.status || 'active'
    });
  }

  getAcademicYear(id) {
    if (id === undefined || id === null) {
      throw new Error('Academic year id is required');
    }
    const year = this.repository.findAcademicYearById(id);
    if (!year) {
      throw new Error(`Academic year with id ${id} not found`);
    }
    return year;
  }

  updateAcademicYear(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Academic year id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getAcademicYear(id);

    if (data.name !== undefined) {
      if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
        throw new Error('Academic year name cannot be empty');
      }
      data.name = data.name.trim();
      if (data.name !== existing.name) {
        const duplicate = this.repository.findAcademicYearByName(data.name);
        if (duplicate) {
          throw new Error(`Academic year "${data.name}" already exists`);
        }
      }
    }

    if (data.status !== undefined && !['active', 'inactive'].includes(data.status)) {
      throw new Error('Invalid academic year status');
    }

    const startDate = data.start_date !== undefined ? data.start_date : existing.start_date;
    const endDate = data.end_date !== undefined ? data.end_date : existing.end_date;
    if (endDate && startDate && endDate <= startDate) {
      throw new Error('Academic year end date must be after start date');
    }

    this.repository.updateAcademicYear(id, data);
    return this.repository.findAcademicYearById(id);
  }

  activateAcademicYear(id) {
    return this.updateAcademicYear(id, { status: 'active' });
  }

  deactivateAcademicYear(id) {
    return this.updateAcademicYear(id, { status: 'inactive' });
  }

  listAcademicYears(filter = {}) {
    const validStatuses = ['active', 'inactive'];
    if (filter.status && !validStatuses.includes(filter.status)) {
      throw new Error('Invalid status filter for academic years');
    }
    return this.repository.findAcademicYears(filter);
  }

  // --- Term operations ---

  createTerm(academicYearId, data) {
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Term data must be a non-null object');
    }
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
      throw new Error('Term name is required');
    }
    if (!data.start_date || typeof data.start_date !== 'string') {
      throw new Error('Term start date is required');
    }
    if (!data.end_date || typeof data.end_date !== 'string') {
      throw new Error('Term end date is required');
    }

    const academicYear = this.getAcademicYear(academicYearId);

    if (data.end_date <= data.start_date) {
      throw new Error('Term end date must be after start date');
    }

    if (data.start_date < academicYear.start_date || data.end_date > academicYear.end_date) {
      throw new Error('Term dates must fall within the academic year date range');
    }

    const overlapping = this.repository.findOverlappingTerm(academicYearId, data.start_date, data.end_date, null);
    if (overlapping) {
      throw new Error('Term dates overlap with an existing term in this academic year');
    }

    return this.repository.saveTerm({
      academic_year_id: academicYearId,
      name: data.name.trim(),
      start_date: data.start_date,
      end_date: data.end_date,
      status: data.status || 'active'
    });
  }

  getTerm(id) {
    if (id === undefined || id === null) {
      throw new Error('Term id is required');
    }
    const term = this.repository.findTermById(id);
    if (!term) {
      throw new Error(`Term with id ${id} not found`);
    }
    return term;
  }

  updateTerm(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Term id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getTerm(id);

    if (data.name !== undefined) {
      if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
        throw new Error('Term name cannot be empty');
      }
      data.name = data.name.trim();
    }

    if (data.status !== undefined && !['active', 'inactive'].includes(data.status)) {
      throw new Error('Invalid term status');
    }

    const startDate = data.start_date !== undefined ? data.start_date : existing.start_date;
    const endDate = data.end_date !== undefined ? data.end_date : existing.end_date;
    if (endDate && startDate && endDate <= startDate) {
      throw new Error('Term end date must be after start date');
    }

    const academicYear = this.repository.findAcademicYearById(existing.academic_year_id);
    if (academicYear && startDate && endDate) {
      if (startDate < academicYear.start_date || endDate > academicYear.end_date) {
        throw new Error('Term dates must fall within the academic year date range');
      }
    }

    const overlapping = this.repository.findOverlappingTerm(
      existing.academic_year_id, startDate, endDate, id
    );
    if (overlapping) {
      throw new Error('Term dates overlap with an existing term in this academic year');
    }

    this.repository.updateTerm(id, data);
    return this.repository.findTermById(id);
  }

  listTermsByAcademicYear(academicYearId) {
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }
    return this.repository.findTermsByAcademicYear(academicYearId);
  }

  // --- Class/Grade operations ---

  createClass(academicYearId, data) {
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Class data must be a non-null object');
    }
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
      throw new Error('Class name is required');
    }

    this.getAcademicYear(academicYearId);

    const trimmedName = data.name.trim();
    const duplicate = this.repository.findClassByNameAndYear(trimmedName, academicYearId);
    if (duplicate) {
      throw new Error(`Class "${trimmedName}" already exists in this academic year`);
    }

    return this.repository.saveClass({
      name: trimmedName,
      academic_year_id: academicYearId,
      status: data.status || 'active'
    });
  }

  getClass(id) {
    if (id === undefined || id === null) {
      throw new Error('Class id is required');
    }
    const classObj = this.repository.findClassById(id);
    if (!classObj) {
      throw new Error(`Class with id ${id} not found`);
    }
    return classObj;
  }

  updateClass(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Class id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getClass(id);

    if (data.name !== undefined) {
      if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
        throw new Error('Class name cannot be empty');
      }
      data.name = data.name.trim();
      if (data.name !== existing.name) {
        const duplicate = this.repository.findClassByNameAndYear(data.name, existing.academic_year_id);
        if (duplicate) {
          throw new Error(`Class "${data.name}" already exists in this academic year`);
        }
      }
    }

    if (data.academic_year_id !== undefined) {
      this.getAcademicYear(data.academic_year_id);
    }

    if (data.status !== undefined && !['active', 'inactive'].includes(data.status)) {
      throw new Error('Invalid class status');
    }

    this.repository.updateClass(id, data);
    return this.repository.findClassById(id);
  }

  activateClass(id) {
    return this.updateClass(id, { status: 'active' });
  }

  deactivateClass(id) {
    return this.updateClass(id, { status: 'inactive' });
  }

  listClassesByAcademicYear(academicYearId) {
    if (academicYearId === undefined || academicYearId === null) {
      throw new Error('Academic year id is required');
    }
    return this.repository.findClassesByAcademicYear(academicYearId);
  }

  // --- Section operations ---

  createSection(classId, data) {
    if (classId === undefined || classId === null) {
      throw new Error('Class id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Section data must be a non-null object');
    }
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
      throw new Error('Section name is required');
    }

    this.getClass(classId);

    const trimmedName = data.name.trim();
    const duplicate = this.repository.findSectionByNameAndClass(trimmedName, classId);
    if (duplicate) {
      throw new Error(`Section "${trimmedName}" already exists in this class`);
    }

    return this.repository.saveSection({
      name: trimmedName,
      class_id: classId,
      status: data.status || 'active'
    });
  }

  getSection(id) {
    if (id === undefined || id === null) {
      throw new Error('Section id is required');
    }
    const section = this.repository.findSectionById(id);
    if (!section) {
      throw new Error(`Section with id ${id} not found`);
    }
    return section;
  }

  updateSection(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Section id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getSection(id);

    if (data.name !== undefined) {
      if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
        throw new Error('Section name cannot be empty');
      }
      data.name = data.name.trim();
      if (data.name !== existing.name) {
        const classId = data.class_id !== undefined ? data.class_id : existing.class_id;
        const duplicate = this.repository.findSectionByNameAndClass(data.name, classId);
        if (duplicate) {
          throw new Error(`Section "${data.name}" already exists in this class`);
        }
      }
    }

    if (data.class_id !== undefined) {
      this.getClass(data.class_id);
    }

    if (data.status !== undefined && !['active', 'inactive'].includes(data.status)) {
      throw new Error('Invalid section status');
    }

    this.repository.updateSection(id, data);
    return this.repository.findSectionById(id);
  }

  activateSection(id) {
    return this.updateSection(id, { status: 'active' });
  }

  deactivateSection(id) {
    return this.updateSection(id, { status: 'inactive' });
  }

  listSectionsByClass(classId) {
    if (classId === undefined || classId === null) {
      throw new Error('Class id is required');
    }
    return this.repository.findSectionsByClass(classId);
  }

  // --- Subject operations ---

  createSubject(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Subject data must be a non-null object');
    }
    if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
      throw new Error('Subject name is required');
    }
    if (!data.code || typeof data.code !== 'string' || data.code.trim().length === 0) {
      throw new Error('Subject code is required');
    }

    const trimmedName = data.name.trim();
    const trimmedCode = data.code.trim().toUpperCase();

    const duplicateName = this.repository.findSubjectByName(trimmedName);
    if (duplicateName) {
      throw new Error(`Subject "${trimmedName}" already exists`);
    }

    const duplicateCode = this.repository.findSubjectByCode(trimmedCode);
    if (duplicateCode) {
      throw new Error(`Subject code "${trimmedCode}" already exists`);
    }

    return this.repository.saveSubject({
      name: trimmedName,
      code: trimmedCode,
      description: data.description || null,
      status: data.status || 'active'
    });
  }

  getSubject(id) {
    if (id === undefined || id === null) {
      throw new Error('Subject id is required');
    }
    const subject = this.repository.findSubjectById(id);
    if (!subject) {
      throw new Error(`Subject with id ${id} not found`);
    }
    return subject;
  }

  listSubjects() {
    return this.repository.findSubjects();
  }

  updateSubject(id, data) {
    if (id === undefined || id === null) {
      throw new Error('Subject id is required');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Update data must be a non-null object');
    }

    const existing = this.getSubject(id);

    if (data.name !== undefined) {
      if (!data.name || typeof data.name !== 'string' || data.name.trim().length === 0) {
        throw new Error('Subject name cannot be empty');
      }
      data.name = data.name.trim();
      if (data.name !== existing.name) {
        const duplicate = this.repository.findSubjectByName(data.name);
        if (duplicate) {
          throw new Error(`Subject "${data.name}" already exists`);
        }
      }
    }

    if (data.code !== undefined) {
      if (!data.code || typeof data.code !== 'string' || data.code.trim().length === 0) {
        throw new Error('Subject code cannot be empty');
      }
      data.code = data.code.trim().toUpperCase();
      if (data.code !== existing.code) {
        const duplicate = this.repository.findSubjectByCode(data.code);
        if (duplicate) {
          throw new Error(`Subject code "${data.code}" already exists`);
        }
      }
    }

    if (data.status !== undefined && !['active', 'inactive'].includes(data.status)) {
      throw new Error('Invalid subject status');
    }

    this.repository.updateSubject(id, data);
    return this.repository.findSubjectById(id);
  }

  activateSubject(id) {
    return this.updateSubject(id, { status: 'active' });
  }

  deactivateSubject(id) {
    return this.updateSubject(id, { status: 'inactive' });
  }

  // --- Teacher operations ---

  createTeacher(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Teacher data must be a non-null object');
    }
    if (!data.first_name || typeof data.first_name !== 'string' || data.first_name.trim().length === 0) {
      throw new Error('First name is required');
    }
    if (!data.last_name || typeof data.last_name !== 'string' || data.last_name.trim().length === 0) {
      throw new Error('Last name is required');
    }
    if (!data.employee_number || typeof data.employee_number !== 'string' || data.employee_number.trim().length === 0) {
      throw new Error('Employee number is required');
    }

    const trimmedNumber = data.employee_number.trim();
    const existing = this.repository.findTeacherByEmployeeNumber(trimmedNumber);
    if (existing) {
      throw new Error(`Teacher with employee number ${trimmedNumber} already exists`);
    }

    return this.repository.saveTeacher({
      first_name: data.first_name.trim(),
      last_name: data.last_name.trim(),
      employee_number: trimmedNumber,
      email: data.email || null,
      status: data.status || 'active'
    });
  }

  getTeacher(id) {
    if (id === undefined || id === null) {
      throw new Error('Teacher id is required');
    }
    const teacher = this.repository.findTeacherById(id);
    if (!teacher) {
      throw new Error(`Teacher with id ${id} not found`);
    }
    return teacher;
  }

  listTeachers() {
    return this.repository.findTeachers();
  }

  // --- Teacher Assignment operations ---

  assignTeacher(teacherId, classId, subjectId) {
    if (teacherId === undefined || teacherId === null) {
      throw new Error('Teacher id is required');
    }
    if (classId === undefined || classId === null) {
      throw new Error('Class id is required');
    }

    const teacher = this.getTeacher(teacherId);
    if (teacher.status !== 'active') {
      throw new Error('Cannot assign an inactive teacher');
    }

    const classObj = this.getClass(classId);
    if (classObj.status !== 'active') {
      throw new Error('Cannot assign a teacher to an inactive class');
    }

    if (subjectId !== undefined && subjectId !== null) {
      const subject = this.getSubject(subjectId);
      if (subject.status !== 'active') {
        throw new Error('Cannot assign a teacher to an inactive subject');
      }
    }

    if (subjectId !== undefined && subjectId !== null) {
      const existing = this.repository.findAssignmentByClassAndSubject(classId, subjectId);
      if (existing) {
        throw new Error('A teacher is already assigned to this subject in this class');
      }
    }

    return this.repository.saveTeacherAssignment({
      teacher_id: teacherId,
      class_id: classId,
      subject_id: subjectId || null,
      status: 'active'
    });
  }

  getAssignmentsByClass(classId) {
    if (classId === undefined || classId === null) {
      throw new Error('Class id is required');
    }
    return this.repository.findAssignmentsByClass(classId);
  }
}

module.exports = AcademicStructureService;
