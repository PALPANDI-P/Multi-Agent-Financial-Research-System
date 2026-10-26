import type { ReactNode } from 'react'
import { Brand } from './Brand'
import { cn } from '../lib/cn'

export interface PublicHeaderLink {
  href: string
  label: string
}

export interface PublicHeaderProps {
  /** The in-page anchors of the public page. */
  links?: PublicHeaderLink[]
  /** The primary call to action of the header. */
  action?: ReactNode
  /** Renders a second, secondary call to action. */
  secondaryAction?: ReactNode
  className?: string
}

/**
 * The header of the public pages.
 *
 * The bar is translucent and blurred, so the content that scrolls underneath
 * stays readable without a heavy border.  It is sticky, and the anchors of
 * the page are hidden on the narrow viewports.
 */
export function PublicHeader({
  links = [],
  action,
  secondaryAction,
  className,
}: PublicHeaderProps) {
  return (
    <header
      className={cn(
        'sticky top-0 z-30 border-b border-line bg-canvas/80 backdrop-blur-xl',
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-page items-center justify-between gap-4 px-5 py-3.5 sm:px-8">
        <Brand />

        {links.length > 0 ? (
          <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-control px-2.5 py-1.5 text-small font-medium text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
              >
                {link.label}
              </a>
            ))}
          </nav>
        ) : null}

        <div className="flex shrink-0 items-center gap-2">
          {secondaryAction}
          {action}
        </div>
      </div>
    </header>
  )
}