import { useCallback, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, KeyboardEvent } from 'react'
import { cn } from '../lib/cn'
import { UploadIcon } from './icons'

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
          'group relative flex cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden',
          'rounded-panel border border-dashed px-6 py-10 text-center',
          'transition-[border-color,background-color,transform] duration-200 ease-out-soft',
          isDragging
            ? 'scale-[1.005] border-brand-500 bg-brand-50'
            : 'border-line-strong bg-surface-muted/40 hover:border-brand-400 hover:bg-brand-50/60',
          disabled && 'cursor-not-allowed opacity-60',
          error && 'border-danger-600 bg-danger-50/40',
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            'inline-flex h-12 w-12 items-center justify-center rounded-panel border transition-colors duration-200',
            isDragging
              ? 'border-brand-200 bg-brand-100 text-brand-700'
              : 'border-line bg-surface text-ink-subtle group-hover:border-brand-200 group-hover:text-brand-600',
          )}
        >
          <UploadIcon size={22} />
        </span>

        <span className="space-y-1">
          <span className="block text-small font-semibold text-ink">{label}</span>
          <span className="block text-caption text-ink-subtle">
            Drag a file here, or press <span className="font-mono">Enter</span> to browse.
          </span>
        </span>

        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
          style={{
            backgroundImage:
              'radial-gradient(60% 60% at 50% 0%, rgb(63 115 97 / 0.06), transparent 70%)',
          }}
        />
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
        <p id={hintId} className="text-caption text-ink-subtle">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-caption font-medium text-danger-700">
          {error}
        </p>
      ) : null}
    </div>
  )
}