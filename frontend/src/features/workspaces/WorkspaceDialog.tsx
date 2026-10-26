import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import type { WorkspaceRead } from '../../api/types'
import { Alert, Button, Input, Modal, Textarea } from '../../components'
import { useCreateWorkspace, useUpdateWorkspace } from '../../hooks/useWorkspaces'

export interface WorkspaceDialogProps {
  open: boolean
  mode: 'create' | 'edit'
  workspace?: WorkspaceRead | null
  onClose: () => void
  onSaved?: (workspace: WorkspaceRead) => void
}

const MAX_NAME = 255
const MAX_DESCRIPTION = 2000

export function WorkspaceDialog({
  open,
  mode,
  workspace = null,
  onClose,
  onSaved,
}: WorkspaceDialogProps) {
  const [name, setName] = useState(workspace?.name ?? '')
  const [description, setDescription] = useState(workspace?.description ?? '')
  const [nameError, setNameError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<{ message: string; code: string } | null>(null)
  const [wasOpen, setWasOpen] = useState(open)

  const createMutation = useCreateWorkspace()
  const updateMutation = useUpdateWorkspace()
  const isPending = createMutation.isPending || updateMutation.isPending

  // Re-seed the form each time the dialog is opened.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setName(workspace?.name ?? '')
      setDescription(workspace?.description ?? '')
      setNameError(null)
      setSubmitError(null)
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitError(null)

    const trimmedName = name.trim()
    if (!trimmedName) {
      setNameError('Workspace name is required.')
      return
    }
    if (trimmedName.length > MAX_NAME) {
      setNameError(`Workspace name must be ${MAX_NAME} characters or fewer.`)
      return
    }
    setNameError(null)

    try {
      if (mode === 'create') {
        const created = await createMutation.mutateAsync({
          name: trimmedName,
          description: description.trim() ? description.trim() : undefined,
        })
        onSaved?.(created)
        onClose()
      } else {
        if (!workspace) return
        const updated = await updateMutation.mutateAsync({
          id: workspace.id,
          payload: {
            name: trimmedName,
            description: description.trim(),
          },
        })
        onSaved?.(updated)
        onClose()
      }
    } catch (caught) {
      setSubmitError(describeError(caught))
    }
  }

  const isEdit = mode === 'edit'

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? 'Rename workspace' : 'Create workspace'}
      description={
        isEdit
          ? 'Update the name or description of this workspace.'
          : 'Create a workspace to group research documents for a company, sector or theme.'
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="workspace-dialog-form"
            loading={isPending}
            loadingLabel={isEdit ? 'Saving…' : 'Creating…'}
          >
            {isEdit ? 'Save changes' : 'Create workspace'}
          </Button>
        </>
      }
    >
      <form
        id="workspace-dialog-form"
        onSubmit={handleSubmit}
        noValidate
        className="flex flex-col gap-5"
      >
        {submitError ? (
          <Alert
            tone="danger"
            title={isEdit ? 'The workspace could not be updated' : 'The workspace could not be created'}
            code={submitError.code}
          >
            {submitError.message}
          </Alert>
        ) : null}

        <Input
          label="Workspace name"
          id="workspace-name"
          required
          value={name}
          maxLength={MAX_NAME}
          onChange={(event) => setName(event.target.value)}
          error={nameError}
          placeholder="e.g. Acme Corp — FY2024 filings"
        />

        <Textarea
          label="Description"
          id="workspace-description"
          value={description}
          maxLength={MAX_DESCRIPTION}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Optional"
          hint={`Optional. ${MAX_DESCRIPTION - description.length} characters remaining.`}
        />
      </form>
    </Modal>
  )
}