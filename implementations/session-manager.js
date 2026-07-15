const { ISessionManager } = require('../interfaces');

class SessionManager extends ISessionManager {
  constructor() {
    super();
    this.sessions = new Map();
  }

  createSession(userId) {
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    this.sessions.set(sessionId, { userId, createdAt: Date.now() });
    return sessionId;
  }

  getSession(sessionId) {
    return this.sessions.get(sessionId);
  }

  destroySession(sessionId) {
    return this.sessions.delete(sessionId);
  }

  validateSession(sessionId) {
    const session = this.getSession(sessionId);
    if (!session) return false;
    
    // Session expires after 1 hour
    return (Date.now() - session.createdAt) < 3600000;
  }
}

module.exports = SessionManager;
