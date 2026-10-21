import { createBrowserRouter } from 'react-router-dom'
import { DashboardPage } from '../pages/DashboardPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { WorkspaceDetailPage } from '../pages/WorkspaceDetailPage'
import { AppLayout } from './AppLayout'

export const routes = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'workspaces/:id', element: <WorkspaceDetailPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

/** Builds the application router. */
export function createAppRouter() {
  return createBrowserRouter(routes)
}