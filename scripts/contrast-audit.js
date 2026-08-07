// Contrast audit for SDMAS token pairs (WCAG 2.1 relative luminance)
function lum(hex) {
  const c = hex.replace('#', '')
  const r = parseInt(c.slice(0, 2), 16) / 255
  const g = parseInt(c.slice(2, 4), 16) / 255
  const b = parseInt(c.slice(4, 6), 16) / 255
  const f = (v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
function ratio(a, b) {
  const l1 = lum(a)
  const l2 = lum(b)
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
}
const pairs = [
  // Light theme
  ['LIGHT secondary/on-surface', '#464b61', '#ffffff'],
  ['LIGHT tertiary/on-surface', '#868da6', '#ffffff'],
  ['LIGHT muted/on-surface', '#aeb4c9', '#ffffff'],
  ['LIGHT secondary/on-bg', '#464b61', '#f5f5f7'],
  ['LIGHT tertiary/on-bg', '#868da6', '#f5f5f7'],
  ['LIGHT muted/on-bg', '#aeb4c9', '#f5f5f7'],
  ['LIGHT border-on-surface', '#e3e4e9', '#ffffff'],
  ['LIGHT accent/on-white', '#4f7aff', '#ffffff'],
  ['LIGHT success-dark/on-success-light', '#06722d', '#e9f9ee'],
  ['LIGHT danger/on-white', '#dc2626', '#ffffff'],
  // Dark theme
  ['DARK secondary/on-surface', '#9ea3bf', '#11163a'],
  ['DARK tertiary/on-surface', '#636b90', '#11163a'],
  ['DARK muted/on-surface', '#434a6e', '#11163a'],
  ['DARK secondary/on-bg', '#9ea3bf', '#080c24'],
  ['DARK tertiary/on-bg', '#636b90', '#080c24'],
  ['DARK muted/on-bg', '#434a6e', '#080c24'],
  ['DARK border-on-surface', '#1e2456', '#11163a'],
  ['DARK accent/on-navy', '#4f7aff', '#11163a'],
  ['DARK primary-text/on-surface', '#e4e6ef', '#11163a'],
]
for (const [name, fg, bg] of pairs) {
  const r = ratio(fg, bg)
  const pass = r >= 4.5 ? 'AA' : r >= 3 ? 'AA-LARGE' : 'FAIL'
  console.log(`${pass.padEnd(9)} ${r.toFixed(2).padStart(5)}  ${name}`)
}
