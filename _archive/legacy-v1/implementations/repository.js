const { IRepository } = require('../interfaces');

class Repository extends IRepository {
  constructor(database) {
    super();
    this.database = database;
  }

  findById(id) {
    if (id === undefined || id === null) {
      throw new Error('Id is required');
    }
    const result = this.database.query('SELECT * FROM items WHERE id = ?', [id]);
    return result.rows[0];
  }

  findAll() {
    const result = this.database.query('SELECT * FROM items');
    return result.rows;
  }

  save(entity) {
    if (!entity || typeof entity !== 'object' || Array.isArray(entity)) {
      throw new Error('Entity must be a non-null object');
    }
    const sql = 'INSERT INTO items (name, description) VALUES (?, ?)';
    const result = this.database.query(sql, [entity.name, entity.description]);
    if (result.affectedRows === 0) {
      throw new Error('Failed to insert entity');
    }
    return { id: result.insertId, ...entity };
  }

  update(id, entity) {
    if (id === undefined || id === null) {
      throw new Error('Id is required');
    }
    if (!entity || typeof entity !== 'object' || Array.isArray(entity)) {
      throw new Error('Entity must be a non-null object');
    }
    const sql = 'UPDATE items SET name = ?, description = ? WHERE id = ?';
    const result = this.database.query(sql, [entity.name, entity.description, id]);
    if (result.affectedRows === 0) {
      throw new Error(`Entity with id ${id} not found for update`);
    }
    return { id, ...entity };
  }

  delete(id) {
    if (id === undefined || id === null) {
      throw new Error('Id is required');
    }
    const sql = 'DELETE FROM items WHERE id = ?';
    const result = this.database.query(sql, [id]);
    if (result.affectedRows === 0) {
      throw new Error(`Entity with id ${id} not found for deletion`);
    }
    return true;
  }
}

module.exports = Repository;
