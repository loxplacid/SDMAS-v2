/* Blocking theme initializer: applies the saved/preferred theme before
 * first paint to prevent a flash of the wrong theme.
 *
 * Kept as an EXTERNAL file (served from /theme-init.js) so the app can
 * ship a strict Content-Security-Policy with `script-src 'self'` — no
 * inline scripts required.
 */
(function () {
  var isDark = false;
  try {
    var stored = localStorage.getItem('sdmas-theme');
    if (stored === 'dark') {
      isDark = true;
    } else if (stored === 'light') {
      isDark = false;
    } else {
      isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
  } catch (e) {
    isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  if (isDark) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', isDark ? '#0b0f1e' : '#f8fafc');
  }
})();
