module.exports = {
  version: 4,
  name: 'create-attendance-schema',
  up(db) {
    db.query(`CREATE TABLE IF NOT EXISTS attendance_records (
      id INT PRIMARY KEY AUTO_INCREMENT,
      student_id INT NOT NULL,
      academic_year_id INT NOT NULL,
      class_id INT NOT NULL,
      section_id INT NOT NULL,
      attendance_date VARCHAR(10) NOT NULL,
      status VARCHAR(20) NOT NULL,
      notes TEXT,
      recorded_at VARCHAR(50),
      updated_at VARCHAR(50)
    )`);
  }
};
