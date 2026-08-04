#!/usr/bin/env node
const { startup } = require('./di-setup');

const USAGE = `
SDMAS-v2 Academic Structure Management CLI

Usage:
  node academic-cli.js <command> [options]

Commands:
  Academic Years:
    year-create <name> <start_date> <end_date> [status]
    year-get <id>
    year-list [status]
    year-update <id> <field=value> ...
    year-activate <id>
    year-deactivate <id>

  Classes:
    class-create <academic_year_id> <name>
    class-get <id>
    class-list <academic_year_id>
    class-update <id> <field=value> ...
    class-activate <id>
    class-deactivate <id>

  Sections:
    section-create <class_id> <name>
    section-get <id>
    section-list <class_id>
    section-update <id> <field=value> ...
    section-activate <id>
    section-deactivate <id>

  Subjects:
    subject-create <name> <code> [description]
    subject-get <id>
    subject-list
    subject-update <id> <field=value> ...
    subject-activate <id>
    subject-deactivate <id>

  Terms:
    term-create <academic_year_id> <name> <start_date> <end_date>
    term-get <id>
    term-list <academic_year_id>
    term-update <id> <field=value> ...

Examples:
  node academic-cli.js year-create 2026-2027 2026-01-01 2026-12-31
  node academic-cli.js year-list active
  node academic-cli.js class-create 1 "Grade 10"
  node academic-cli.js class-list 1
  node academic-cli.js section-create 1 "Section A"
  node academic-cli.js section-list 1
  node academic-cli.js subject-create Mathematics MATH101
  node academic-cli.js subject-list
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

function formatYear(y) {
  if (!y) return '(not found)';
  return `ID: ${y.id}  Name: ${y.name}  ${y.start_date} → ${y.end_date}  [${y.status}]`;
}

function formatClass(c) {
  if (!c) return '(not found)';
  return `ID: ${c.id}  Name: ${c.name}  Year: ${c.academic_year_id}  [${c.status}]`;
}

function formatSection(s) {
  if (!s) return '(not found)';
  return `ID: ${s.id}  Name: ${s.name}  Class: ${s.class_id}  [${s.status}]`;
}

function formatSubject(s) {
  if (!s) return '(not found)';
  return `ID: ${s.id}  Name: ${s.name}  Code: ${s.code}  [${s.status}]${s.description ? '  ' + s.description : ''}`;
}

function formatTerm(t) {
  if (!t) return '(not found)';
  return `ID: ${t.id}  Name: ${t.name}  ${t.start_date} → ${t.end_date}  Year: ${t.academic_year_id}  [${t.status}]`;
}

function main() {
  const container = startup();
  const service = container.resolve('academicStructureService');

  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === 'help') {
    console.log(USAGE);
    return;
  }

  try {
    switch (command) {
      // --- Academic Year commands ---
      case 'year-create': {
        const [name, start_date, end_date, status] = args.slice(1);
        if (!name || !start_date || !end_date) {
          throw new Error('Usage: year-create <name> <start_date> <end_date> [status]');
        }
        const year = service.createAcademicYear({ name, start_date, end_date, status: status || 'active' });
        console.log('Academic year created:');
        console.log(formatYear(year));
        break;
      }
      case 'year-get': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatYear(service.getAcademicYear(id)));
        break;
      }
      case 'year-list': {
        const filter = args[1] ? { status: args[1] } : {};
        const years = service.listAcademicYears(filter);
        if (years.length === 0) {
          console.log('No academic years found.');
        } else {
          console.log(`${years.length} academic year(s):`);
          years.forEach(y => console.log(formatYear(y)));
        }
        break;
      }
      case 'year-update': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        const data = parseKeyValueArgs(args.slice(2));
        const updated = service.updateAcademicYear(id, data);
        console.log('Updated:');
        console.log(formatYear(updated));
        break;
      }
      case 'year-activate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatYear(service.activateAcademicYear(id)));
        break;
      }
      case 'year-deactivate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatYear(service.deactivateAcademicYear(id)));
        break;
      }

      // --- Class commands ---
      case 'class-create': {
        const academicYearId = parseInt(args[1], 10);
        const name = args[2];
        if (isNaN(academicYearId) || !name) throw new Error('Usage: class-create <academic_year_id> <name>');
        const cls = service.createClass(academicYearId, { name });
        console.log('Class created:');
        console.log(formatClass(cls));
        break;
      }
      case 'class-get': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatClass(service.getClass(id)));
        break;
      }
      case 'class-list': {
        const academicYearId = parseInt(args[1], 10);
        if (isNaN(academicYearId)) throw new Error('Valid academic year ID is required');
        const classes = service.listClassesByAcademicYear(academicYearId);
        if (classes.length === 0) {
          console.log('No classes found.');
        } else {
          console.log(`${classes.length} class(es):`);
          classes.forEach(c => console.log(formatClass(c)));
        }
        break;
      }
      case 'class-update': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        const data = parseKeyValueArgs(args.slice(2));
        console.log(formatClass(service.updateClass(id, data)));
        break;
      }
      case 'class-activate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatClass(service.activateClass(id)));
        break;
      }
      case 'class-deactivate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatClass(service.deactivateClass(id)));
        break;
      }

      // --- Section commands ---
      case 'section-create': {
        const classId = parseInt(args[1], 10);
        const name = args[2];
        if (isNaN(classId) || !name) throw new Error('Usage: section-create <class_id> <name>');
        const section = service.createSection(classId, { name });
        console.log('Section created:');
        console.log(formatSection(section));
        break;
      }
      case 'section-get': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatSection(service.getSection(id)));
        break;
      }
      case 'section-list': {
        const classId = parseInt(args[1], 10);
        if (isNaN(classId)) throw new Error('Valid class ID is required');
        const sections = service.listSectionsByClass(classId);
        if (sections.length === 0) {
          console.log('No sections found.');
        } else {
          console.log(`${sections.length} section(s):`);
          sections.forEach(s => console.log(formatSection(s)));
        }
        break;
      }
      case 'section-update': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        const data = parseKeyValueArgs(args.slice(2));
        console.log(formatSection(service.updateSection(id, data)));
        break;
      }
      case 'section-activate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatSection(service.activateSection(id)));
        break;
      }
      case 'section-deactivate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatSection(service.deactivateSection(id)));
        break;
      }

      // --- Subject commands ---
      case 'subject-create': {
        const [name, code, ...descriptionParts] = args.slice(1);
        if (!name || !code) throw new Error('Usage: subject-create <name> <code> [description]');
        const subject = service.createSubject({ name, code, description: descriptionParts.join(' ') || null });
        console.log('Subject created:');
        console.log(formatSubject(subject));
        break;
      }
      case 'subject-get': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatSubject(service.getSubject(id)));
        break;
      }
      case 'subject-list': {
        const subjects = service.listSubjects();
        if (subjects.length === 0) {
          console.log('No subjects found.');
        } else {
          console.log(`${subjects.length} subject(s):`);
          subjects.forEach(s => console.log(formatSubject(s)));
        }
        break;
      }
      case 'subject-update': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        const data = parseKeyValueArgs(args.slice(2));
        console.log(formatSubject(service.updateSubject(id, data)));
        break;
      }
      case 'subject-activate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatSubject(service.activateSubject(id)));
        break;
      }
      case 'subject-deactivate': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatSubject(service.deactivateSubject(id)));
        break;
      }

      // --- Term commands ---
      case 'term-create': {
        const academicYearId = parseInt(args[1], 10);
        const name = args[2];
        const start_date = args[3];
        const end_date = args[4];
        if (isNaN(academicYearId) || !name || !start_date || !end_date) {
          throw new Error('Usage: term-create <academic_year_id> <name> <start_date> <end_date>');
        }
        const term = service.createTerm(academicYearId, { name, start_date, end_date });
        console.log('Term created:');
        console.log(formatTerm(term));
        break;
      }
      case 'term-get': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        console.log(formatTerm(service.getTerm(id)));
        break;
      }
      case 'term-list': {
        const academicYearId = parseInt(args[1], 10);
        if (isNaN(academicYearId)) throw new Error('Valid academic year ID is required');
        const terms = service.listTermsByAcademicYear(academicYearId);
        if (terms.length === 0) {
          console.log('No terms found.');
        } else {
          console.log(`${terms.length} term(s):`);
          terms.forEach(t => console.log(formatTerm(t)));
        }
        break;
      }
      case 'term-update': {
        const id = parseInt(args[1], 10);
        if (isNaN(id)) throw new Error('Valid ID is required');
        const data = parseKeyValueArgs(args.slice(2));
        console.log(formatTerm(service.updateTerm(id, data)));
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

module.exports = { main, formatYear, formatClass, formatSection, formatSubject, formatTerm };
