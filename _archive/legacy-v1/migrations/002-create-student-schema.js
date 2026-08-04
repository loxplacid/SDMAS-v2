module.exports = {
  version: 2,
  name: 'create-student-schema',
  up(db) {
    db.query(`
      CREATE TABLE IF NOT EXISTS students (
        id INT PRIMARY KEY AUTO_INCREMENT,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        student_number VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255),
        date_of_birth VARCHAR(10),
        status VARCHAR(20) DEFAULT 'active',
        created_at VARCHAR(50),
        updated_at VARCHAR(50)
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS academic_years (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        start_date VARCHAR(10),
        end_date VARCHAR(10),
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS classes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        academic_year_id INT,
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS sections (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        class_id INT,
        status VARCHAR(20) DEFAULT 'active'
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS enrollments (
        id INT PRIMARY KEY AUTO_INCREMENT,
        student_id INT NOT NULL,
        academic_year_id INT NOT NULL,
        class_id INT,
        section_id INT,
        status VARCHAR(20) DEFAULT 'active',
        enrolled_at VARCHAR(50)
      )
    `);
  }
};
