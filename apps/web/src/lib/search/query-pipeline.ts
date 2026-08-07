/**
 * Universal search — query pipeline (pure, framework-free).
 *
 * Turns a raw user query into a ranked FTS5 MATCH expression with:
 *  - tokenization (unicode-aware, quoted phrases preserved)
 *  - synonym expansion (teacher == faculty == instructor ...)
 *  - typo tolerance (Levenshtein against the index vocabulary)
 *  - partial matching (prefix + LIKE fallbacks)
 *
 * Everything here is a pure function so it can be unit-tested without a
 * worker or a browser.
 */

// ---------------------------------------------------------------------------
// Synonyms — the domain thesaurus. Each canonical term maps to all the words
// a user might type for it. Expands in BOTH directions at query time.
// ---------------------------------------------------------------------------

const SYNONYM_GROUPS: string[][] = [
  ['teacher', 'faculty', 'instructor', 'staff', 'lecturer'],
  ['student', 'pupil', 'learner'],
  ['fees', 'payments', 'fee', 'payment', 'dues', 'receipts', 'invoices'],
  ['attendance', 'present', 'absent', 'late', 'excused'],
  ['certificate', 'certificates', 'credential'],
  ['library', 'books', 'book'],
  ['discipline', 'disciplinary', 'conduct', 'behavior'],
  ['exam', 'exams', 'examination', 'examinations', 'test', 'assessment'],
  ['class', 'classes', 'course', 'courses'],
  ['parent', 'guardian'],
  ['enrollment', 'enrolment', 'admission', 'admissions', 'application'],
]

const SYNONYM_MAP: Map<string, string[]> = new Map()
for (const group of SYNONYM_GROUPS) {
  for (const term of group) {
    const others = group.filter((t) => t !== term)
    SYNONYM_MAP.set(term, others)
  }
}

/** Expand a single token to its synonym family (including itself). */
export function expandSynonyms(token: string): string[] {
  const canonical = token.toLowerCase().trim()
  const hits = SYNONYM_MAP.get(canonical)
  if (!hits) return [token]
  return [token, ...hits]
}

// ---------------------------------------------------------------------------
// Tokenization
// ---------------------------------------------------------------------------

export interface QueryToken {
  /** The raw text of the token. */
  text: string
  /** True when the user wrapped it in quotes (exact phrase). */
  quoted: boolean
}

/**
 * Split a query into tokens, preserving quoted phrases as single units.
 * `student:"Amina Kante"` → [{text:'student',...}, {text:'Amina Kante',quoted:true}]
 *
 * Implemented as a manual scan: regex alternation cannot backtrack into a
 * quoted phrase once the unquoted token has consumed it.
 */
// Straight and curly quotes (mobile keyboards emit smart quotes).
// The curly characters are U+201C/U+2018 (open) and U+201D/U+2019 (close).
const OPEN_QUOTES = ['"', '“', '‘']
const CLOSE_QUOTES = ['"', '”', '’']

function isOpenQuote(ch: string): boolean {
  return OPEN_QUOTES.includes(ch)
}

function isCloseQuote(ch: string): boolean {
  return CLOSE_QUOTES.includes(ch)
}

/**
 * Split a query into tokens, preserving quoted phrases as single units.
 * `student:"Amina Kante"` → [{text:'student',...}, {text:'Amina Kante',quoted:true}]
 *
 * Implemented as a manual scan: regex alternation cannot backtrack into a
 * quoted phrase once the unquoted token has consumed it. Handles both
 * straight and curly quote characters.
 */
export function tokenize(query: string): QueryToken[] {
  const tokens: QueryToken[] = []
  const text = query.trim()
  if (!text) return tokens

  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (isOpenQuote(ch)) {
      // Quoted phrase: scan to the closing quote (any close style).
      let end = i + 1
      let phrase = ''
      while (end < text.length && !isCloseQuote(text[end])) {
        phrase += text[end]
        end += 1
      }
      if (phrase.trim()) tokens.push({ text: phrase, quoted: true })
      i = end + 1 // skip the closing quote (or end of string)
    } else if (ch === ' ') {
      i += 1
    } else {
      // Unquoted token: run to the next space or any quote.
      let end = i
      while (
        end < text.length &&
        text[end] !== ' ' &&
        !isOpenQuote(text[end]) &&
        !isCloseQuote(text[end])
      ) {
        end += 1
      }
      let token = text.slice(i, end)
      // Strip trailing field separators so `student:"Amina Kante"` yields
      // `student` (unquoted) + `Amina Kante` (quoted), not `student:`.
      token = token.replace(/[:.,;]+$/, '')
      if (token) tokens.push({ text: token, quoted: false })
      i = end
    }
  }
  return tokens
}

/** FTS5-safe token: escape MATCH-syntax characters. */
export function escapeFtsToken(token: string): string {
  return token.replace(/(["():*^])/g, '"$1"')
}

// ---------------------------------------------------------------------------
// Levenshtein typo tolerance
// ---------------------------------------------------------------------------

/** Classic Levenshtein distance with a rolling array (O(n·m) time, O(m) mem). */
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0
  if (!a.length) return b.length
  if (!b.length) return a.length
  let prev = new Array<number>(b.length + 1)
  let curr = new Array<number>(b.length + 1)
  for (let j = 0; j <= b.length; j++) prev[j] = j
  for (let i = 1; i <= a.length; i++) {
    curr[0] = i
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      curr[j] = Math.min(
        prev[j] + 1, // deletion
        curr[j - 1] + 1, // insertion
        prev[j - 1] + cost, // substitution
      )
    }
    ;[prev, curr] = [curr, prev]
  }
  return prev[b.length]
}

/**
 * Find the closest vocabulary term for a misspelled token.
 * Returns `null` when nothing is within `maxDistance`.
 */
export function correctToken(
  token: string,
  vocabulary: string[],
  maxDistance = 2,
): string | null {
  const lower = token.toLowerCase()
  let best: string | null = null
  let bestDist = Infinity
  for (const candidate of vocabulary) {
    if (candidate.length < 2) continue
    const d = levenshtein(lower, candidate)
    if (d < bestDist) {
      bestDist = d
      best = candidate
      if (d === 0) break
    }
  }
  return bestDist <= maxDistance ? best : null
}

// ---------------------------------------------------------------------------
// FTS5 MATCH expression construction
// ---------------------------------------------------------------------------

export interface BuildMatchOptions {
  /** Vocabulary for typo correction; skip correction when omitted. */
  vocabulary?: string[]
  /** Allow prefix matching (partial words). Default true. */
  prefix?: boolean
  /** Max typo distance (default 2). Pass 0 to disable typo correction. */
  typoDistance?: number
}

/**
 * Build an FTS5 MATCH expression from a query.
 *
 * Rules:
 *  - each token expands to its synonym family, joined with OR
 *  - quoted tokens become exact phrase matches
 *  - the final token of each term becomes a prefix match (partial matching)
 *  - when a token looks misspelled (no direct prefix candidate), the closest
 *    vocabulary term replaces it
 */
export function buildMatchQuery(
  query: string,
  options: BuildMatchOptions = {},
): string {
  const { vocabulary, prefix = true, typoDistance = 2 } = options
  const tokens = tokenize(query)
  if (tokens.length === 0) return ''

  const clauses: string[] = tokens.map((token) => {
    if (token.quoted) {
      // Exact phrase: OR across synonyms of the FIRST word, then the rest as
      // an adjacency phrase.
      const words = token.text.trim().split(/\s+/)
      const first = words[0]
      const rest = words.slice(1)
      const firstFamily = expandSynonyms(first)
      const phrases = firstFamily.map(
        (syn) => `"${escapeFtsToken(syn)}${rest.length ? ' ' + rest.map(escapeFtsToken).join(' ') : ''}"`,
      )
      return phrases.length === 1 ? phrases[0] : `(${phrases.join(' OR ')})`
    }

    // Unquoted token: prefix + synonym expansion + typo correction.
    const family = expandSynonyms(token.text)
    const variants = family.map((term) => {
      const safe = escapeFtsToken(term)
      return prefix ? `${safe}*` : safe
    })

    // Typo correction: when the token is not a prefix of any vocabulary
    // term, assume a misspelling and swap in the nearest vocabulary term.
    if (vocabulary && vocabulary.length > 0 && typoDistance > 0) {
      const rawLower = token.text.toLowerCase()
      const knownPrefix = vocabulary.some(
        (v) => v.startsWith(rawLower.slice(0, 3)),
      )
      if (!knownPrefix) {
        const corrected = correctToken(token.text, vocabulary, typoDistance)
        if (corrected && corrected.toLowerCase() !== rawLower) {
          const correctedFamily = expandSynonyms(corrected)
          variants.push(...correctedFamily.map((t) => `${escapeFtsToken(t)}*`))
        }
      }
    }

    return variants.length === 1 ? variants[0] : `(${variants.join(' OR ')})`
  })

  // AND between tokens by default; quoted phrases join with AND too.
  return clauses.join(' AND ')
}

/**
 * Vocabulary harvest: split an index document blob into candidate terms.
 * Used to build the typo-correction vocabulary from a sample of rows.
 */
export function harvestVocabulary(
  texts: Iterable<string>,
  limit = 2000,
): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const text of texts) {
    for (const match of text.toLowerCase().matchAll(/[a-z0-9]{2,}/g)) {
      const term = match[0]
      if (!seen.has(term)) {
        seen.add(term)
        out.push(term)
        if (out.length >= limit) return out
      }
    }
  }
  return out
}
