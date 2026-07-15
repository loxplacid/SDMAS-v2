const { IRepository } = require('../interfaces');

class Repository extends IRepository {
  constructor(database) {
    super();
    this.database = database;
  }

  findById(id) {
    const result = this.database.query('SELECT * FROM items WHERE id = ?', [id]);
    return result.rows[0];
  }

  findAll() {
    const result = this.database.query('SELECT * FROM items');
    return result.rows;
  }

  save(entity) {
    const sql = 'INSERT INTO items (name, description) VALUES (?, ?)';
    const result = this.database.query(sql, [entity.name, entity.description]);
    return { id: result.insertId, ...entity };
  }

  update(id, entity) {
    const sql = 'UPDATE items SET name = ?, description = ? WHERE id = ?';
    this.database.query(sql, [entity.name, entity.description, id]);
    return { id, ...entity };
  }

  delete(id) {
    const sql = 'DELETE FROM items WHERE id = ?';
    this.database.query(sql, [id]);
    return true;
  }
}

module.exports = Repository;
