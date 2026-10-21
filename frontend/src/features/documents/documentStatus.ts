import type { BadgeTone } from '../../components/Badge'

/**
 * Maps the raw `processing_status` string emitted by the API to a badge tone.
 * The raw status text is always rendered next to the colour, so the badge is
 * never colour-only.
 */
const STATUS_TONES: Record<string, BadgeTone> = {
  queued: 'neutral',
  validating: 'info',
  extracting: 'info',
  chunking: 'info',
  embedding: 'info',
  indexing: 'info',
  completed: 'success',
  failed: 'danger',
}

export function statusTone(status: string): BadgeTone {
  return STATUS_TONES[status.trim().toLowerCase()] ?? 'neutral'
}

export function isFailedStatus(status: string): boolean {
  return status.trim().toLowerCase() === 'failed'
}
