import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode
}

/**
 * A compact, keyboard-operable chip.
 *
 * Used for the suggested queries of a scenario and for the small filters of
 * the workspace page: a chip is a button that happens to look like a label.
 * It stays quiet until it is approached: the hover raises it by one pixel
 * and tints it with the accent.
 */
export function Chip({ icon, className, children, type = 'button', ...rest }: ChipProps) {
  return (
    <button
      type={type}
      className={cn(
        'group inline-flex items-center gap-2 rounded-pill border border-line bg-surface px-3.5 py-1.5',
        'text-small text-ink-muted transition-[background-color,border-color,color,transform,box-shadow]',
        'duration-150 ease-out-soft',
        'hover:-translate-y-px hover:border-brand-300 hover:bg-brand-50 hover:text-brand-800 hover:shadow-card',
        'active:translate-y-0',
        'disabled:pointer-events-none disabled:opacity-55',
        className,
      )}
      {...rest}
    >
      {icon ? (
        <span className="text-ink-subtle transition-colors duration-150 group-hover:text-brand-700" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children}
    </button>
  )
}