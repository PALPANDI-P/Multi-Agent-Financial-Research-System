export type ClassValue =
  | string
  | number
  | null
  | undefined
  | false
  | ClassValue[]
  | Record<string, boolean | null | undefined>

/**
 * Minimal class-name joiner: flattens arrays/objects and drops falsy values.
 * Keeps the component API free of an extra `clsx` dependency.
 */
export function cn(...values: ClassValue[]): string {
  const out: string[] = []

  const push = (value: ClassValue): void => {
    if (!value && value !== 0) return
    if (typeof value === 'string' || typeof value === 'number') {
      const trimmed = String(value).trim()
      if (trimmed) out.push(trimmed)
      return
    }
    if (Array.isArray(value)) {
      for (const item of value) push(item)
      return
    }
    if (typeof value === 'object') {
      for (const [key, enabled] of Object.entries(value)) {
        if (enabled) out.push(key)
      }
    }
  }

  for (const value of values) push(value)
  return out.join(' ')
}
