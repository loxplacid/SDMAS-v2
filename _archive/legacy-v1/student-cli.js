#!/usr/bin/env node
const { startup } = require('./di-setup');

const USAGE = `
SDMAS-v2 Student Management CLI

Usage:
  node student-cli.js <command> [options]

Commands:
  create <first_name> <last_name> <student_number> [email] [date_of_birth]
      Create a new student

  get <id>
      Retrieve a student by ID

  find-by-number <student_number>
      Find a student by student number

  list [status]
      List students (optionally filter by status: active, inactive, graduated)

  search <query>
      Search students by name, student number, or email

  update <id> <field1=value1> [field2=value2] ...
      Update student fields (first_name, last_name, email, date_of_birth, status)

  deactivate <id>
      Deactivate a student

  reactivate <id>
      Reactivate a student (set status back to active)

Examples:
  node student-cli.js create John Doe STU001 john@school.com 2000-01-15
  node student-cli.js get 1
  node student-cli.js list active
  node student-cli.js search john
  node student-cli.js update 1 email=new@school.com
  node student-cli.js deactivate 1
  node student-cli.js reactivate 1
`.trim();

function parseKeyValueArgs(args) {
  const data = {};
  for (const arg of args) {
    const eqIdx = arg.indexOf('=');
    if (eqIdx === -1) {
      throw new Error(`Invalid argument format "${arg}". Use field=value syntax.`);
    }
    const key = arg.slice(0, eqIdx);
    const value = arg.slice(eqIdx + 1);
    data[key] = value === 'null' ? null : value;
  }
  return data;
}

function formatStudent(s) {
  if (!s) return '(not found)';
  return [
    `ID:           ${s.id}`,
    `Name:         ${s.first_name} ${s.last_name}`,
    `Student #:    ${s.student_number}`,
    `Email:        ${s.email || '(none)'}`,
    `Date of Birth: ${s.date_of_birth || '(none)'}`,
    `Status:       ${s.status}`,
    `Created:      ${s.created_at || '(unknown)'}`,
    `Updated:      ${s.updated_at || '(unknown)'}`
  ].join('\n');
}

function formatStudentCompact(s) {
  return `#${s.id}  ${s.first_name} ${s.last_name}  (${s.student_number})  [${s.status}]${s.email ? '  ' + s.email : ''}`;
}

function main() {
  const container = startup();
  const studentService = container.resolve('studentService');

  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === 'help') {
    console.log(USAGE);
    return;
  }

  try {
    switch (command) {
      case 'create': {
        const [first_name, last_name, student_number, email, date_of_birth] = args.slice(1);
        if (!first_name || !last_name || !student_number) {
          throw new Error('Usage: node student-cli.js create <first_name> <last_name> <student_number> [email] [date_of_birth]');
        }
        const student = studentService.createStudent({
          first_name, last_name, student_number, email: email || null, date_of_birth: date_of_birth || null
        });
        console.log('Student created successfully:\n');
        console.log(formatStudent(student));
        break;
      }

      case 'get': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid student ID is required');
        const student = studentService.getStudent(id);
        console.log(formatStudent(student));
        break;
      }

      case 'find-by-number': {
        const studentNumber = args[1];
        if (!studentNumber) throw new Error('Student number is required');
        const student = studentService.findByStudentNumber(studentNumber);
        console.log(formatStudent(student));
        break;
      }

      case 'list': {
        const statusFilter = args[1];
        const filter = statusFilter ? { status: statusFilter } : {};
        const students = studentService.listStudents(filter);
        if (students.length === 0) {
          console.log('No students found.');
        } else {
          console.log(`${students.length} student(s) found:\n`);
          for (const s of students) {
            console.log(formatStudentCompact(s));
          }
        }
        break;
      }

      case 'search': {
        const query = args.slice(1).join(' ');
        if (!query) throw new Error('Search query is required');
        const results = studentService.searchStudents(query);
        if (results.length === 0) {
          console.log('No matching students found.');
        } else {
          console.log(`${results.length} matching student(s):\n`);
          for (const s of results) {
            console.log(formatStudentCompact(s));
          }
        }
        break;
      }

      case 'update': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid student ID is required');
        const data = parseKeyValueArgs(args.slice(2));
        if (Object.keys(data).length === 0) throw new Error('At least one field to update is required');
        const student = studentService.updateStudent(id, data);
        console.log('Student updated successfully:\n');
        console.log(formatStudent(student));
        break;
      }

      case 'deactivate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid student ID is required');
        const student = studentService.deactivateStudent(id);
        console.log('Student deactivated.\n');
        console.log(formatStudent(student));
        break;
      }

      case 'reactivate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid student ID is required');
        const student = studentService.reactivateStudent(id);
        console.log('Student reactivated.\n');
        console.log(formatStudent(student));
        break;
      }

      default:
        console.log(`Unknown command: ${command}`);
        console.log(USAGE);
        process.exit(1);
    }
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { main, formatStudent, formatStudentCompact };
