import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'

export interface BrandMarkProps {
  /** Rendered size of the mark in pixels. */
  size?: number
  className?: string
}

/**
 * The mark of the product: a pine tile with three ascending bars - a filing
 * reduced to its most abstract shape.  Drawn inline so it inherits the
 * accent of the current theme.
 */
export function BrandMark({ size = 28, className }: BrandMarkProps) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-control bg-brand-solid text-on-accent',
        className,
      )}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg
        width={Math.round(size * 0.56)}
        height={Math.round(size * 0.56)}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
      >
        <path d="M5 17.5v-5" />
        <path d="M12 17.5v-10" />
        <path d="M19 17.5v-13" />
      </svg>
    </span>
  )
}

export interface BrandProps {
  /** Where the wordmark links to. */
  to?: string
  /** Short form for the narrow viewports. */
  compact?: boolean
  className?: string
  onNavigate?: () => void
}

/**
 * The wordmark of the product.  The name is set in the sans stack with a
 * tight tracking; the product description is the mono face, so the lock-up
 * reads like a tool rather than like a brand.
 */
export function Brand({ to = '/', compact = false, className, onNavigate }: BrandProps) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className={cn(
        'group flex min-w-0 items-center gap-2.5 rounded-control transition-opacity',
        className,
      )}
    >
      <BrandMark />
      <span className="flex min-w-0 flex-col leading-none">
        <span className="truncate text-small font-semibold tracking-tight text-ink">
          {compact ? 'Financial Research' : 'Multi-Agent Financial Research System'}
        </span>
        <span className="mt-1 hidden truncate font-mono text-micro tracking-tight text-ink-subtle sm:block">
          evidence retrieval workspace
        </span>
      </span>
    </Link>
  )
}