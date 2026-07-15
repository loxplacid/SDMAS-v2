const { IService } = require('../interfaces');

class Service extends IService {
  constructor() {
    super();
  }

  execute(...args) {
    console.log('Service executed with args:', args);
    return { success: true, data: args };
  }
}

module.exports = Service;
