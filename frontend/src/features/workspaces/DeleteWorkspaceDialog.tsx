import { useState } from 'react'
import { describeError } from '../../api/client'
import type { WorkspaceRead } from '../../api/types'
import { Alert, Button, Modal } from '../../components'
import { useDeleteWorkspace } from '../../hooks/useWorkspaces'

export interface DeleteWorkspaceDialogProps {
  open: boolean
  workspace: WorkspaceRead | null
  onClose: () => void
  onDeleted?: (workspace: WorkspaceRead) => void
}

export function DeleteWorkspaceDialog({
  open,
  workspace,
  onClose,
  onDeleted,
}: DeleteWorkspaceDialogProps) {
  const [error, setError] = useState<{ message: string; code: string } | null>(null)
  const [wasOpen, setWasOpen] = useState(open)
  const mutation = useDeleteWorkspace()

  // Reset the local error state when the dialog is (re-)opened.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) setError(null)
  }

  const handleClose = () => {
    setError(null)
    mutation.reset()
    onClose()
  }

  const handleConfirm = async () => {
    if (!workspace) return
    setError(null)
    try {
      await mutation.mutateAsync(workspace.id)
      onDeleted?.(workspace)
      handleClose()
    } catch (caught) {
      setError(describeError(caught))
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Delete workspace"
      description="This permanently deletes the workspace together with all of its documents and indexed chunks."
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={mutation.isPending}
            loadingLabel="Deleting…"
            onClick={handleConfirm}
          >
            Delete workspace
          </Button>
        </>
      }
    >
      {error ? (
        <Alert tone="danger" title="The workspace could not be deleted" code={error.code}>
          {error.message}
        </Alert>
      ) : null}
      <p className="text-small text-ink-muted">
        You are about to delete{' '}
        <span className="font-semibold text-ink">{workspace?.name ?? 'this workspace'}</span>, which
        contains {workspace?.document_count ?? 0} document(s).
      </p>
    </Modal>
  )
}