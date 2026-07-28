module.exports = {
  version: 5,
  name: 'create-fee-schema',
  up(db) {
    db.query(`CREATE TABLE IF NOT EXISTS fee_types (
      id INT PRIMARY KEY AUTO_INCREMENT,
      name VARCHAR(100) NOT NULL,
      description TEXT,
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS fee_structures (
      id INT PRIMARY KEY AUTO_INCREMENT,
      academic_year_id INT NOT NULL,
      class_id INT NOT NULL,
      fee_type_id INT NOT NULL,
      amount INT NOT NULL,
      frequency VARCHAR(50) DEFAULT 'annual',
      status VARCHAR(20) DEFAULT 'active'
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS fee_dues (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      academic_year_id INT NOT NULL,
      fee_structure_id INT NOT NULL,
      original_amount INT NOT NULL,
      amount_paid INT NOT NULL DEFAULT 0,
      due_date VARCHAR(10),
      status VARCHAR(20) DEFAULT 'unpaid',
      created_at VARCHAR(50),
      updated_at VARCHAR(50)
    )`);
    db.query(`CREATE TABLE IF NOT EXISTS payments (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      fee_due_id INT NOT NULL,
      amount INT NOT NULL,
      payment_date VARCHAR(10),
      payment_method VARCHAR(50),
      receipt_number VARCHAR(100),
      created_at VARCHAR(50)
    )`);
  }
};
