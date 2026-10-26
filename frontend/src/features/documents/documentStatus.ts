import type { BadgeTone } from '../../components/Badge'

/**
 * Maps the raw `processing_status` string emitted by the API to a badge tone.
 *
 * Every one of the eight states owns a distinguishable colour, and the raw
 * status text is always rendered next to it, so the badge is never
 * colour-only.
 */
const STATUS_TONES: Record<string, BadgeTone> = {
  queued: 'queued',
  validating: 'validating',
  extracting: 'extracting',
  chunking: 'chunking',
  embedding: 'embedding',
  indexing: 'indexing',
  completed: 'completed',
  failed: 'failed',
}

export function statusTone(status: string): BadgeTone {
  return STATUS_TONES[status.trim().toLowerCase()] ?? 'neutral'
}

export function isFailedStatus(status: string): boolean {
  return status.trim().toLowerCase() === 'failed'
}