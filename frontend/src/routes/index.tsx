import { createBrowserRouter } from 'react-router-dom'
import { DashboardPage } from '../pages/DashboardPage'
import { LandingPage } from '../pages/LandingPage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { WorkspaceDetailPage } from '../pages/WorkspaceDetailPage'
import { AppLayout } from './AppLayout'
import { LegacyWorkspaceRedirect } from './LegacyWorkspaceRedirect'
import { RequireAuth } from './RequireAuth'
import { RequireGuest } from './RequireGuest'

export const routes = [
  { path: '/', element: <LandingPage /> },
  {
    path: '/login',
    element: (
      <RequireGuest>
        <LoginPage />
      </RequireGuest>
    ),
  },
  {
    path: '/register',
    element: (
      <RequireGuest>
        <LoginPage />
      </RequireGuest>
    ),
  },
  {
    path: '/app',
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'workspaces/:id', element: <WorkspaceDetailPage /> },
    ],
  },
  { path: '/workspaces/:id', element: <LegacyWorkspaceRedirect /> },
  { path: '*', element: <NotFoundPage /> },
]

/** Builds the application router. */
export function createAppRouter() {
  return createBrowserRouter(routes)
}