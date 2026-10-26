import { Navigate, useParams } from 'react-router-dom'

/**
 * Redirects the legacy workspace URL (`/workspaces/:id`) to the workspace of
 * the signed-in area (`/app/workspaces/:id`).
 */
export function LegacyWorkspaceRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/app/workspaces/${id ?? ''}`} replace />
}