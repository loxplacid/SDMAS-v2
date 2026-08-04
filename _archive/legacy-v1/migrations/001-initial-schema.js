module.exports = {
  version: 1,
  name: 'initial-schema',
  up(db) {
    db.query(`
      CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY,
        name VARCHAR(255),
        email VARCHAR(255)
      )
    `);
    db.query(`
      CREATE TABLE IF NOT EXISTS items (
        id INT PRIMARY KEY,
        name VARCHAR(255),
        description TEXT
      )
    `);
  }
};
