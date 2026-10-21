const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

/** Human readable file size, e.g. `1.4 MB`. */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—'
  if (bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`

  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < BYTE_UNITS.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  const rounded = value >= 100 ? Math.round(value).toString() : value.toFixed(1)
  return `${rounded} ${BYTE_UNITS[unitIndex]}`
}

function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Absolute timestamp in the user's locale, e.g. `21 Oct 2026, 13:45`. */
export function formatDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** Locale-aware integer formatting. */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat().format(value)
}

/** Page reference for a chunk, collapsing single-page ranges. */
export function formatPageRange(
  pageStart: number | null | undefined,
  pageEnd: number | null | undefined,
): string {
  if (pageStart === null || pageStart === undefined) return '—'
  if (pageEnd === null || pageEnd === undefined || pageEnd === pageStart) {
    return `p. ${pageStart}`
  }
  return `pp. ${pageStart}–${pageEnd}`
}

/** Relevance score, fixed to four decimals so raw API precision is visible. */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return '—'
  return score.toFixed(4)
}

/** Elapsed time reported by the API, in milliseconds. */
export function formatDuration(milliseconds: number | null | undefined): string {
  if (milliseconds === null || milliseconds === undefined || Number.isNaN(milliseconds)) {
    return '—'
  }
  if (milliseconds < 1) return `${milliseconds.toFixed(2)} ms`
  if (milliseconds < 1000) return `${milliseconds.toFixed(1)} ms`
  return `${(milliseconds / 1000).toFixed(2)} s`
}

/** Truncates long text for compact list views. */
export function truncate(text: string, maxLength = 160): string {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1).trimEnd()}…`
}

/** Renders an unknown metadata value as readable text. */
export function formatMetadataValue(value: unknown): string {
  if (value === null) return 'null'
  if (value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/** Human readable label for a snake_case API key. */
export function humanizeKey(key: string): string {
  const spaced = key.replace(/[_-]+/g, ' ').trim()
  if (!spaced) return key
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
