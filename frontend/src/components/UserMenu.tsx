import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { ChevronDownIcon, LogOutIcon, UserIcon } from './icons'

export interface UserMenuProps {
  fullName: string
  email: string
  role: string
  /** Called when the user asks to sign out. */
  onSignOut: () => void
  isSigningOut?: boolean
  signOutLabel?: string
}

/** The initials of a name, used by the avatar of the menu. */
function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

/**
 * The account menu of the application bar.
 *
 * A real menu, not a `<details>` element: it closes on Escape and on a click
 * outside, it moves the focus back to its trigger when it closes, and the
 * items are reachable with the arrow keys.
 */
export function UserMenu({
  fullName,
  email,
  role,
  onSignOut,
  isSigningOut = false,
  signOutLabel = 'Sign out',
}: UserMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuId = useId()

  const close = useCallback(() => {
    setIsOpen((open) => {
      if (open) triggerRef.current?.focus()
      return false
    })
  }, [])

  useEffect(() => {
    if (!isOpen) return

    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        close()
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, close])

  const handleTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setIsOpen(true)
    }
  }

  const handleMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    const items = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"]'),
    )
    if (items.length === 0) return
    event.preventDefault()
    const index = items.indexOf(document.activeElement as HTMLElement)
    const next = event.key === 'ArrowDown' ? index + 1 : index - 1
    items[(next + items.length) % items.length]?.focus()
  }

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={menuId}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={handleTriggerKeyDown}
        className={cn(
          'flex items-center gap-2 rounded-pill border py-1 pr-2 pl-1 text-left transition-colors duration-150',
          isOpen
            ? 'border-brand-300 bg-brand-50'
            : 'border-transparent hover:border-line hover:bg-surface-muted',
        )}
      >
        <span
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-pill bg-brand-100 text-micro font-semibold text-brand-800"
          aria-hidden="true"
        >
          {initialsOf(fullName)}
        </span>
        <span className="hidden min-w-0 flex-col leading-none sm:flex">
          <span className="max-w-32 truncate text-small font-semibold text-ink">{fullName}</span>
          <span className="mt-0.5 max-w-32 truncate font-mono text-micro text-ink-subtle">
            {email}
          </span>
        </span>
        <ChevronDownIcon
          size={14}
          className={cn('text-ink-subtle transition-transform duration-200', isOpen && 'rotate-180')}
        />
      </button>

      {isOpen ? (
        <div
          id={menuId}
          role="menu"
          aria-label="Account"
          onKeyDown={handleMenuKeyDown}
          className="anim-scale-in absolute right-0 z-40 mt-2 w-72 origin-top-right overflow-hidden rounded-card border border-line bg-surface p-1.5 shadow-panel"
        >
          <div className="rounded-control px-2.5 py-2.5">
            <p className="truncate text-small font-semibold text-ink">{fullName}</p>
            <p className="mt-0.5 truncate text-caption text-ink-muted">{email}</p>
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-pill bg-surface-muted px-2 py-0.5 font-mono text-micro text-ink-muted">
              <UserIcon size={12} className="text-ink-subtle" />
              {role}
            </p>
          </div>

          <div className="my-1.5 h-px bg-line-faint" />

          <Link
            to="/"
            role="menuitem"
            className="flex items-center gap-2 rounded-control px-2.5 py-2 text-small text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
          >
            Product overview
          </Link>

          <button
            type="button"
            role="menuitem"
            disabled={isSigningOut}
            onClick={() => {
              setIsOpen(false)
              onSignOut()
            }}
            className="flex w-full items-center gap-2 rounded-control px-2.5 py-2 text-left text-small text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink disabled:opacity-55"
          >
            <LogOutIcon size={16} className="text-ink-subtle" />
            {isSigningOut ? 'Signing out…' : signOutLabel}
          </button>
        </div>
      ) : null}
    </div>
  )
}