import { useCallback, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, KeyboardEvent } from 'react'
import { cn } from '../lib/cn'

export interface DropzoneProps {
  /** Visible label text for the drop target. */
  label: string
  /** Id for the visually hidden file input. */
  id: string
  hint?: string
  error?: string | null
  accept?: string
  multiple?: boolean
  disabled?: boolean
  onFilesSelected: (files: File[]) => void
}

export function Dropzone({
  label,
  id,
  hint,
  error,
  accept,
  multiple = false,
  disabled = false,
  onFilesSelected,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const statusId = `${id}-status`
  const describedBy = [hint ? hintId : null, error ? errorId : null, statusId]
    .filter(Boolean)
    .join(' ')

  const emit = useCallback(
    (files: File[]) => {
      if (files.length === 0) {
        setAnnouncement('No file was selected.')
        return
      }
      const names = files.map((file) => file.name).join(', ')
      setAnnouncement(
        files.length === 1 ? `File selected: ${names}.` : `${files.length} files selected: ${names}.`,
      )
      onFilesSelected(files)
    },
    [onFilesSelected],
  )

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    emit(files)
    // Allow re-selecting the same file.
    event.target.value = ''
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    if (disabled) return
    const files = Array.from(event.dataTransfer?.files ?? [])
    emit(files)
  }

  const openPicker = () => {
    if (disabled) return
    inputRef.current?.click()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault()
      openPicker()
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled || undefined}
        aria-label={`${label}. Press Enter or Space to choose a file.`}
        aria-describedby={describedBy}
        onClick={openPicker}
        onKeyDown={handleKeyDown}
        onDragEnter={(event) => {
          event.preventDefault()
          if (!disabled) setIsDragging(true)
        }}
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setIsDragging(true)
        }}
        onDragLeave={(event) => {
          event.preventDefault()
          if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
          setIsDragging(false)
        }}
        onDrop={handleDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed px-4 py-8 text-center transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
          isDragging
            ? 'border-brand-500 bg-brand-50'
            : 'border-line-strong bg-surface hover:border-brand-500 hover:bg-surface-muted',
          disabled && 'cursor-not-allowed opacity-60',
          error && 'border-danger-500',
        )}
      >
        <svg
          className="h-7 w-7 text-ink-subtle"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden="true"
        >
          <path d="M12 16V4m0 0L8 8m4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" />
        </svg>
        <span className="text-sm font-medium text-ink">{label}</span>
        <span className="text-xs text-ink-subtle">
          Drag and drop a file here, or press Enter to browse.
        </span>
      </div>

      <input
        ref={inputRef}
        id={id}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={handleInputChange}
      />
      <label htmlFor={id} className="sr-only">
        {label}
      </label>

      <p id={statusId} className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>

      {hint ? (
        <p id={hintId} className="text-xs text-ink-subtle">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-danger-700">
          {error}
        </p>
      ) : null}
    </div>
  )
}

