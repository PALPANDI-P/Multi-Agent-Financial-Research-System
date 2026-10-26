import { useState } from 'react'
import type { FormEvent } from 'react'
import { describeError } from '../../api/client'
import type { DocumentUploadResponse } from '../../api/types'
import { Alert, Button, Dropzone, Input } from '../../components'
import { CheckIcon, FileTextIcon } from '../../components/icons'
import { useUploadDocument } from '../../hooks/useDocuments'

export interface UploadPanelProps {
  workspaceId: string
}

interface FieldErrors {
  file?: string
  company_name?: string
  document_title?: string
  document_type?: string
  fiscal_period?: string
  source_url?: string
}

const DOCUMENT_TYPE_SUGGESTIONS = [
  '10-K',
  '10-Q',
  '8-K',
  '20-F',
  'Annual Report',
  'Earnings Release',
  'Press Release',
  'Prospectus',
  'Research Note',
]

function isValidHttpUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function UploadPanel({ workspaceId }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null)
  const [companyName, setCompanyName] = useState('')
  const [documentTitle, setDocumentTitle] = useState('')
  const [documentType, setDocumentType] = useState('')
  const [fiscalPeriod, setFiscalPeriod] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitError, setSubmitError] = useState<{ message: string; code: string } | null>(null)
  const [result, setResult] = useState<DocumentUploadResponse | null>(null)

  const upload = useUploadDocument(workspaceId)

  const resetForm = () => {
    setFile(null)
    setCompanyName('')
    setDocumentTitle('')
    setDocumentType('')
    setFiscalPeriod('')
    setSourceUrl('')
    setErrors({})
  }

  const validate = (): FieldErrors => {
    const next: FieldErrors = {}
    if (!file) next.file = 'Select a file to upload.'
    if (companyName.length > 255) next.company_name = 'Company name must be 255 characters or fewer.'
    if (documentTitle.length > 512)
      next.document_title = 'Document title must be 512 characters or fewer.'
    if (documentType.length > 64)
      next.document_type = 'Document type must be 64 characters or fewer.'
    if (fiscalPeriod.length > 64)
      next.fiscal_period = 'Fiscal period must be 64 characters or fewer.'
    if (sourceUrl.trim().length > 0 && !isValidHttpUrl(sourceUrl.trim())) {
      next.source_url = 'Enter a valid http(s) URL, or leave this field empty.'
    }
    return next
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitError(null)
    setResult(null)

    const validation = validate()
    setErrors(validation)
    if (Object.keys(validation).length > 0 || !file) return

    try {
      const response = await upload.mutateAsync({
        file,
        company_name: companyName.trim() || undefined,
        document_title: documentTitle.trim() || undefined,
        document_type: documentType.trim() || undefined,
        fiscal_period: fiscalPeriod.trim() || undefined,
        source_url: sourceUrl.trim() || undefined,
      })
      setResult(response)
      resetForm()
    } catch (caught) {
      setSubmitError(describeError(caught))
    }
  }

  const isPending = upload.isPending
  const progress = upload.progress ?? 0

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <Dropzone
        id="document-file"
        label="Drop the filing here"
        hint="The file is sent to the ingestion API. Accepted formats are validated server-side."
        error={errors.file ?? null}
        disabled={isPending}
        onFilesSelected={(files) => {
          setFile(files[0] ?? null)
          setErrors((current) => ({ ...current, file: undefined }))
        }}
      />

      {file ? (
        <div className="flex items-center gap-3 rounded-card border border-line bg-surface-muted/60 px-4 py-3">
          <span
            aria-hidden="true"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-control border border-line bg-surface text-brand-700"
          >
            <FileTextIcon size={17} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-small font-medium text-ink">{file.name}</span>
            <span className="mt-0.5 block font-mono text-caption text-ink-subtle">
              {file.type || 'unknown type'} · {(file.size / 1024).toFixed(1)} KB
            </span>
          </span>
          <span
            aria-hidden="true"
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-pill bg-success-50 text-success-700"
          >
            <CheckIcon size={13} />
          </span>
        </div>
      ) : null}

      <fieldset className="flex flex-col gap-4 border-0 p-0">
        <legend className="mb-1 flex items-center gap-2 text-micro font-semibold tracking-[0.12em] text-ink-subtle uppercase">
          <span aria-hidden="true" className="h-px w-4 bg-line-strong" />
          Document metadata — optional
        </legend>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Company name"
            id="upload-company-name"
            value={companyName}
            maxLength={255}
            onChange={(event) => setCompanyName(event.target.value)}
            error={errors.company_name ?? null}
            placeholder="Optional"
          />
          <Input
            label="Document title"
            id="upload-document-title"
            value={documentTitle}
            maxLength={512}
            onChange={(event) => setDocumentTitle(event.target.value)}
            error={errors.document_title ?? null}
            placeholder="Optional"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Input
              label="Document type"
              id="upload-document-type"
              list="upload-document-type-options"
              value={documentType}
              maxLength={64}
              onChange={(event) => setDocumentType(event.target.value)}
              error={errors.document_type ?? null}
              placeholder="Optional"
            />
            <datalist id="upload-document-type-options">
              {DOCUMENT_TYPE_SUGGESTIONS.map((suggestion) => (
                <option key={suggestion} value={suggestion} />
              ))}
            </datalist>
          </div>
          <Input
            label="Fiscal period"
            id="upload-fiscal-period"
            value={fiscalPeriod}
            maxLength={64}
            onChange={(event) => setFiscalPeriod(event.target.value)}
            error={errors.fiscal_period ?? null}
            placeholder="Optional, e.g. FY2024"
          />
        </div>

        <Input
          label="Source URL"
          id="upload-source-url"
          type="url"
          value={sourceUrl}
          onChange={(event) => setSourceUrl(event.target.value)}
          error={errors.source_url ?? null}
          placeholder="Optional, e.g. https://example.com/filing"
          hint="Where the document was originally published."
        />
      </fieldset>

      {isPending ? (
        <div className="rounded-card border border-line bg-surface px-4 py-4">
          <div className="flex items-baseline justify-between gap-4 text-small">
            <span className="font-medium text-ink">Uploading the document…</span>
            <span aria-live="polite" className="font-mono text-caption text-ink tabular-nums">
              {progress}%
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Upload progress"
            className="mt-3 h-1.5 w-full overflow-hidden rounded-pill bg-line-faint"
          >
            <div
              className="h-full rounded-pill bg-brand-600 shadow-[inset_0_1px_0_rgb(255_255_255/0.25)] transition-[width] duration-200 ease-out-soft"
              style={{ width: `${progress}%` }}
            />
          </div>
          {file ? (
            <p className="mt-2.5 truncate font-mono text-micro text-ink-subtle">{file.name}</p>
          ) : null}
        </div>
      ) : null}

      {submitError ? (
        <Alert tone="danger" title="The upload failed" code={submitError.code}>
          {submitError.message}
        </Alert>
      ) : null}

      {result ? (
        <Alert
          tone={result.duplicate ? 'warning' : 'success'}
          title={
            result.duplicate
              ? 'The API reported this file as a duplicate'
              : 'The document was accepted for processing'
          }
        >
          <p>
            Processing status: <span className="font-mono font-semibold">{result.processing_status}</span>
            {result.processing_stage ? (
              <>
                {' · '}stage: <span className="font-mono">{result.processing_stage}</span>
              </>
            ) : null}
          </p>
          <p className="mt-1.5 font-mono text-caption">
            document <span className="text-ink-muted">{result.document_id}</span>
          </p>
          <p className="mt-0.5 font-mono text-caption break-all">
            sha256 <span className="text-ink-muted">{result.content_hash}</span>
          </p>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
        <Button type="submit" loading={isPending} loadingLabel="Uploading…">
          Upload document
        </Button>
        {file ? (
          <Button
            variant="ghost"
            onClick={() => {
              setFile(null)
              setErrors((current) => ({ ...current, file: undefined }))
            }}
            disabled={isPending}
          >
            Clear selected file
          </Button>
        ) : null}
      </div>
    </form>
  )
}