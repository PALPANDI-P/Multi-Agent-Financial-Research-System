import { useState } from 'react'
import { describeError } from '../../api/client'
import type { DocumentRead } from '../../api/types'
import { Alert, Button, Modal } from '../../components'
import { useDeleteDocument } from '../../hooks/useDocuments'

export interface DeleteDocumentDialogProps {
  open: boolean
  document: DocumentRead | null
  workspaceId: string
  onClose: () => void
  onDeleted?: (document: DocumentRead) => void
}

export function DeleteDocumentDialog({
  open,
  document,
  workspaceId,
  onClose,
  onDeleted,
}: DeleteDocumentDialogProps) {
  const [error, setError] = useState<{ message: string; code: string } | null>(null)
  const [wasOpen, setWasOpen] = useState(open)
  const mutation = useDeleteDocument(workspaceId)

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
    if (!document) return
    setError(null)
    try {
      await mutation.mutateAsync(document.id)
      onDeleted?.(document)
      handleClose()
    } catch (caught) {
      setError(describeError(caught))
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Remove document"
      description="This permanently deletes the document and its indexed chunks. This cannot be undone."
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={mutation.isPending}
            loadingLabel="Removing…"
            onClick={handleConfirm}
          >
            Remove document
          </Button>
        </>
      }
    >
      {error ? (
        <Alert tone="danger" title="The document could not be removed" code={error.code}>
          {error.message}
        </Alert>
      ) : null}
      <p className="text-small text-ink-muted">
        You are about to remove{' '}
        <span className="font-semibold text-ink">
          {document?.original_filename ?? 'this document'}
        </span>
        {document?.document_title ? ` (${document.document_title})` : null}.
      </p>
    </Modal>
  )
}