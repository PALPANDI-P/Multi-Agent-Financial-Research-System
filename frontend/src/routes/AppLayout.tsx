import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Brand, UserMenu } from '../components'
import { useAuth } from '../hooks/useAuth'
import { cn } from '../lib/cn'

const NAV_ITEM_CLASSES =
  'relative rounded-control px-2.5 py-1.5 text-small font-medium text-ink-muted transition-colors duration-150 hover:bg-surface-muted hover:text-ink'

const NAV_ITEM_ACTIVE_CLASSES =
  'text-ink after:absolute after:-bottom-2 after:left-2.5 after:right-2.5 after:h-px after:rounded-pill after:bg-brand-500'

/**
 * The shell of the signed-in application: the top navigation bar with the
 * product name, the link to the workspace, the link back to the landing page
 * and the menu of the user.
 */
export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [isSigningOut, setIsSigningOut] = useState(false)
  const [isScrolled, setIsScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleSignOut = async () => {
    setIsSigningOut(true)
    try {
      await logout()
    } finally {
      setIsSigningOut(false)
      navigate('/login', { replace: true })
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header
        className={cn(
          'sticky top-0 z-30 border-b border-line backdrop-blur-xl transition-[background-color,box-shadow] duration-200',
          isScrolled ? 'bg-canvas/85 shadow-card' : 'bg-canvas/60',
        )}
      >
        <div className="mx-auto flex w-full max-w-page items-center justify-between gap-3 px-5 py-3 sm:px-8">
          <div className="flex min-w-0 items-center gap-6">
            <Brand to="/app" compact />

            <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
              <NavLink
                to="/app"
                end
                className={({ isActive }) =>
                  cn(NAV_ITEM_CLASSES, isActive && NAV_ITEM_ACTIVE_CLASSES)
                }
              >
                Workspace
              </NavLink>
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  cn(NAV_ITEM_CLASSES, isActive && NAV_ITEM_ACTIVE_CLASSES)
                }
              >
                Product
              </NavLink>
            </nav>
          </div>

          {user ? (
            <UserMenu
              fullName={user.full_name}
              email={user.email}
              role={user.role}
              isSigningOut={isSigningOut}
              onSignOut={() => void handleSignOut()}
            />
          ) : null}
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex w-full max-w-page flex-col gap-1 px-5 py-5 text-caption text-ink-subtle sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p>Every value in the workspace is read from the configured API.</p>
          <p>
            <Link
              to="/"
              className="rounded-xs font-medium text-ink-muted transition-colors hover:text-ink"
            >
              Product overview
            </Link>
          </p>
        </div>
      </footer>
    </div>
  )
}