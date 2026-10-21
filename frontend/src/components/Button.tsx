import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  loadingLabel?: string
  leadingIcon?: ReactNode
  trailingIcon?: ReactNode
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-brand-600 text-white shadow-sm hover:bg-brand-700 disabled:hover:bg-brand-600',
  secondary:
    'bg-surface text-ink border border-line-strong hover:bg-surface-muted disabled:hover:bg-surface',
  ghost: 'bg-transparent text-ink-muted hover:bg-surface-muted hover:text-ink',
  danger: 'bg-danger-600 text-white shadow-sm hover:bg-danger-700 disabled:hover:bg-danger-600',
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-11 px-5 text-base',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  loadingLabel = 'Working…',
  leadingIcon,
  trailingIcon,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-control font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
        'disabled:cursor-not-allowed disabled:opacity-60',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner hideLabel label={loadingLabel} /> : leadingIcon}
      {children}
      {loading ? null : trailingIcon}
    </button>
  )
}
