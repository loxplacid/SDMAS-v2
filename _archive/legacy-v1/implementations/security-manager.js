const { ISecurityManager } = require('../interfaces');

class SecurityManager extends ISecurityManager {
  constructor() {
    super();
    this.users = new Map();
    this.tokens = new Map();
  }

  authenticate(username, password) {
    // Simulate authentication logic
    if (username === 'admin' && password === 'password') {
      return { userId: '1', username };
    }
    return null;
  }

  authorize(userId, permission) {
    // Simulate authorization logic
    return true;
  }

  generateToken(payload) {
    const token = `token_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    this.tokens.set(token, { payload, createdAt: Date.now() });
    return token;
  }

  verifyToken(token) {
    const tokenData = this.tokens.get(token);
    if (!tokenData) return false;
    
    // Token expires after 1 day
    return (Date.now() - tokenData.createdAt) < 86400000;
  }
}

module.exports = SecurityManager;
