const { IThemeManager } = require('../interfaces');

class ThemeManager extends IThemeManager {
  constructor() {
    super();
    this.currentTheme = 'default';
  }

  setTheme(themeName) {
    this.currentTheme = themeName;
    console.log(`Theme changed to: ${themeName}`);
  }

  getTheme() {
    return this.currentTheme;
  }

  applyTheme(element) {
    element.classList.add(this.currentTheme);
    console.log(`Applied theme "${this.currentTheme}" to element`);
  }
}

module.exports = ThemeManager;
