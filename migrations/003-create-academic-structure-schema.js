module.exports = {
  version: 3,
  name: 'create-academic-structure-schema',
  up(db) {
    db.query(`
      CREATE TABLE IF NOT EXISTS terms (
        id INT PRIMARY KEY AUTO_INCREMENT,
        academic_year_id INT NOT NULL,
        name VARCHAR(100) NOT NULL,
        start_date VARCHAR(10),
        end_date VARCHAR(10),
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS subjects (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        code VARCHAR(50) UNIQUE NOT NULL,
        description TEXT,
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS teachers (
        id INT PRIMARY KEY AUTO_INCREMENT,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        employee_number VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255),
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS teacher_assignments (
        id INT PRIMARY KEY AUTO_INCREMENT,
        teacher_id INT NOT NULL,
        class_id INT NOT NULL,
        subject_id INT,
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
  }
};
