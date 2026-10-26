import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface FeatureCardProps {
  title: ReactNode
  description: ReactNode
  icon?: ReactNode
  /** Optional bullet list rendered under the description. */
  details?: ReactNode
  className?: string
  /** The position of the entry in the index, printed in the mono face. */
  index?: string
}

/**
 * A single capability of the product, used by the landing page.
 *
 * The entry is flat: a rule above it, the icon and the number, then the
 * title and the explanation.  Six boxes of the same weight would read as a
 * grid of equal importance; a ruled index reads as a list of claims.
 */
export function FeatureCard({
  title,
  description,
  icon,
  details,
  className,
  index,
}: FeatureCardProps) {
  return (
    <article
      className={cn(
        'group flex h-full flex-col gap-3 border-t border-line pt-6 transition-colors duration-200',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        {icon ? (
          <span
            aria-hidden="true"
            className="inline-flex h-9 w-9 items-center justify-center rounded-control border border-line bg-surface-muted text-brand-700 transition-colors duration-200 group-hover:border-brand-200 group-hover:bg-brand-50"
          >
            {icon}
          </span>
        ) : (
          <span aria-hidden="true" className="h-9 w-9" />
        )}
        {index ? (
          <span className="font-mono text-micro text-ink-subtle tabular-nums">{index}</span>
        ) : null}
      </div>

      <h3 className="text-subtitle text-ink">{title}</h3>
      <p className="max-w-prose text-small leading-relaxed text-ink-muted">{description}</p>
      {details ? <div className="mt-auto text-small text-ink-muted">{details}</div> : null}
    </article>
  )
}