const path = require('path');
const fs = require('fs');
const DependencyInjectionContainer = require('./di-container');
const Configuration = require('./implementations/configuration');
const Logger = require('./implementations/logger');
const Database = require('./implementations/database');
const Repository = require('./implementations/repository');
const Service = require('./implementations/service');
const SessionManager = require('./implementations/session-manager');
const SecurityManager = require('./implementations/security-manager');
const ThemeManager = require('./implementations/theme-manager');
const AIManager = require('./implementations/ai-manager');
const EventBus = require('./implementations/event-bus');
const MigrationRunner = require('./implementations/migration-runner');
const StudentRepository = require('./implementations/student-repository');
const StudentService = require('./implementations/student-service');
const AcademicStructureRepository = require('./implementations/academic-structure-repository');
const AcademicStructureService = require('./implementations/academic-structure-service');
const AttendanceRepository = require('./implementations/attendance-repository');
const AttendanceService = require('./implementations/attendance-service');
const FeeRepository = require('./implementations/fee-repository');
const FeeService = require('./implementations/fee-service');

function setupDIContainer() {
  const container = new DependencyInjectionContainer();

  // Register services
  container.registerSingleton('configuration', () => new Configuration());
  container.registerSingleton('logger', () => new Logger());
  
  // Database service (singleton)
  container.registerSingleton('database', (config, logger) => {
    const db = new Database();
    db.connect();
    return db;
  }, ['configuration', 'logger']);
  
  // Repository service
  container.register('repository', (database) => {
    return new Repository(database);
  }, ['database']);
  
  // Migration runner
  container.registerSingleton('migrationRunner', (database) => {
    return new MigrationRunner(database);
  }, ['database']);
  
  // Student Repository
  container.register('studentRepository', (database) => {
    return new StudentRepository(database);
  }, ['database']);
  
  // Student Service
  container.register('studentService', (studentRepository) => {
    return new StudentService(studentRepository);
  }, ['studentRepository']);

  // Academic Structure Repository
  container.register('academicStructureRepository', (database) => {
    return new AcademicStructureRepository(database);
  }, ['database']);

  // Academic Structure Service
  container.register('academicStructureService', (academicStructureRepository) => {
    return new AcademicStructureService(academicStructureRepository);
  }, ['academicStructureRepository']);
  
  // Attendance Repository
  container.register('attendanceRepository', (database) => {
    return new AttendanceRepository(database);
  }, ['database']);

  // Attendance Service
  container.register('attendanceService', (attendanceRepository, studentRepository, academicStructureRepository) => {
    return new AttendanceService(attendanceRepository, studentRepository, academicStructureRepository);
  }, ['attendanceRepository', 'studentRepository', 'academicStructureRepository']);

  // Fee Repository
  container.register('feeRepository', (database) => {
    return new FeeRepository(database);
  }, ['database']);

  // Fee Service
  container.register('feeService', (feeRepository, studentRepository, academicStructureRepository) => {
    return new FeeService(feeRepository, studentRepository, academicStructureRepository);
  }, ['feeRepository', 'studentRepository', 'academicStructureRepository']);

  // Service
  container.registerSingleton('service', () => new Service());
  
  // Session Manager
  container.registerSingleton('sessionManager', () => new SessionManager());
  
  // Security Manager
  container.registerSingleton('securityManager', () => new SecurityManager());
  
  // Theme Manager
  container.registerSingleton('themeManager', () => new ThemeManager());
  
  // AI Manager
  container.registerSingleton('aiManager', () => new AIManager());
  
  // Event Bus
  container.registerSingleton('eventBus', () => new EventBus());

  return container;
}

function startup() {
  const container = setupDIContainer();

  const migrationsDir = path.join(__dirname, 'migrations');
  if (fs.existsSync(migrationsDir)) {
    const files = fs.readdirSync(migrationsDir)
      .filter(f => f.endsWith('.js'))
      .sort();

    if (files.length > 0) {
      const runner = container.resolve('migrationRunner');

      for (const file of files) {
        const migration = require(path.join(migrationsDir, file));
        runner.register(migration);
      }

      const results = runner.run();
      if (results.length > 0) {
        const logger = container.resolve('logger');
        logger.info(`Applied ${results.length} database migration(s)`);
      }
    }
  }

  return container;
}

module.exports = setupDIContainer;
module.exports.startup = startup;
module.exports.MigrationRunner = MigrationRunner;
