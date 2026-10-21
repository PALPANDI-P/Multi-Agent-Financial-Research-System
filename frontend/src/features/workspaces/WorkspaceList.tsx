import type { ReactNode } from 'react'
import type { WorkspaceRead } from '../../api/types'
import { EmptyState } from '../../components'
import { WorkspaceCard } from './WorkspaceCard'

export interface WorkspaceListProps {
  workspaces: WorkspaceRead[]
  emptyAction?: ReactNode
}

export function WorkspaceList({ workspaces, emptyAction }: WorkspaceListProps) {
  if (workspaces.length === 0) {
    return (
      <EmptyState
        title="No workspaces match your search"
        description="Try a different name, clear the search box, or create a new workspace to get started."
        action={emptyAction}
      />
    )
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {workspaces.map((workspace) => (
        <li key={workspace.id}>
          <WorkspaceCard workspace={workspace} />
        </li>
      ))}
    </ul>
  )
}

