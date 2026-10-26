import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface SectionIntroProps {
  /** Small label above the title, e.g. "How it works". */
  eyebrow: string
  title: ReactNode
  /** The paragraph that explains the section. */
  lead?: ReactNode
  /** Rendered on the right of the title column, e.g. a link. */
  aside?: ReactNode
  className?: string
}

/**
 * The heading block of a landing section.
 *
 * The block is split in two on wide screens: the label and the title own the
 * left column, the explanation owns the right one.  The result is a clear
 * reading order - what this section is, then what it says - instead of a
 * stack of equally loud headings.
 */
export function SectionIntro({ eyebrow, title, lead, aside, className }: SectionIntroProps) {
  return (
    <div
      className={cn(
        'grid gap-x-16 gap-y-5 lg:grid-cols-[minmax(0,0.86fr)_minmax(0,1fr)] lg:items-start',
        className,
      )}
    >
      <div className="min-w-0">
        <p className="flex items-center gap-2.5 text-micro font-semibold tracking-[0.16em] text-brand-700 uppercase">
          <span aria-hidden="true" className="h-px w-6 bg-brand-300" />
          {eyebrow}
        </p>
        <h2 className="mt-4 max-w-[22ch] text-headline text-balance text-ink">{title}</h2>
        {aside ? <div className="mt-5">{aside}</div> : null}
      </div>

      {lead ? (
        <div className="max-w-prose text-body text-ink-muted lg:pt-1">{lead}</div>
      ) : null}
    </div>
  )
}