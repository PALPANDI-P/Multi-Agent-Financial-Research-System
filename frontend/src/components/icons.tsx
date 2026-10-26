import type { ReactNode, SVGProps } from 'react'

/**
 * The icon set of the product.
 *
 * Every icon is a hand-written inline SVG on a 24x24 grid with a 1.5px
 * stroke and `currentColor` as the paint.  No icon package is used, so the
 * application stays dependency free and works completely offline.
 */

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'children'> & {
  /** Rendered size in pixels; the icons are drawn on a 24 unit grid. */
  size?: number
}

interface IconBaseProps extends IconProps {
  children: ReactNode
}

function IconBase({ size = 20, children, className, ...rest }: IconBaseProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
      {...rest}
    >
      {children}
    </svg>
  )
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 12h15" />
      <path d="m13 6 6 6-6 6" />
    </IconBase>
  )
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M20 12H5" />
      <path d="m11 18-6-6 6-6" />
    </IconBase>
  )
}

export function ArrowUpRightIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M7 17 17 7" />
      <path d="M8 7h9v9" />
    </IconBase>
  )
}

export function CheckIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m4.5 12.5 5 5 10-11" />
    </IconBase>
  )
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m6 9 6 6 6-6" />
    </IconBase>
  )
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m9 6 6 6-6 6" />
    </IconBase>
  )
}

export function CloseIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M6 6 18 18" />
      <path d="M18 6 6 18" />
    </IconBase>
  )
}

export function DocumentIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6" />
      <path d="M9 17h4" />
    </IconBase>
  )
}

export function FolderIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M3.75 6.75A1.5 1.5 0 0 1 5.25 5.25h3.9l1.6 2h7.99a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5z" />
    </IconBase>
  )
}

export function GridIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </IconBase>
  )
}

export function InfoIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="8.25" />
      <path d="M12 11v5" />
      <path d="M12 7.75h.01" />
    </IconBase>
  )
}

export function WarningIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M10.3 4.2 3.4 17a2 2 0 0 0 1.7 3h13.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9.5v4" />
      <path d="M12 16.75h.01" />
    </IconBase>
  )
}

export function SearchIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="11" cy="11" r="6.25" />
      <path d="m15.75 15.75 4 4" />
    </IconBase>
  )
}

export function UploadIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 15.5V4" />
      <path d="m7.5 8.5 4.5-4.5 4.5 4.5" />
      <path d="M4.5 15v3.25a1.75 1.75 0 0 0 1.75 1.75h11.5a1.75 1.75 0 0 0 1.75-1.75V15" />
    </IconBase>
  )
}

export function TrashIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4.75 7h14.5" />
      <path d="M9.5 7V5.5A1.5 1.5 0 0 1 11 4h2a1.5 1.5 0 0 1 1.5 1.5V7" />
      <path d="M6.75 7 7.4 19a1.5 1.5 0 0 0 1.5 1.4h6.2a1.5 1.5 0 0 0 1.5-1.4L17.25 7" />
      <path d="M10.5 11v5.5" />
      <path d="M13.5 11v5.5" />
    </IconBase>
  )
}

export function RefreshIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" />
      <path d="M19.75 4.75v4.5h-4.5" />
    </IconBase>
  )
}

export function PlusIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </IconBase>
  )
}

export function UserIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="8.25" r="3.5" />
      <path d="M5.5 19.5a6.5 6.5 0 0 1 13 0" />
    </IconBase>
  )
}

export function LogOutIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M14 5.5h3.5a1.5 1.5 0 0 1 1.5 1.5v10a1.5 1.5 0 0 1-1.5 1.5H14" />
      <path d="M10 8.5 6.5 12l3.5 3.5" />
      <path d="M6.75 12H15" />
    </IconBase>
  )
}

export function CopyIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="9" y="9" width="10.5" height="10.5" rx="2" />
      <path d="M15 5.5A1.5 1.5 0 0 0 13.5 4h-8A1.5 1.5 0 0 0 4 5.5v8A1.5 1.5 0 0 0 5.5 15" />
    </IconBase>
  )
}

export function QuoteIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M9.5 6.5C7 7.75 5.5 10 5.5 13v4.5h5V12H8c0-2 .75-3.5 2.5-4.25z" />
      <path d="M18.5 6.5C16 7.75 14.5 10 14.5 13v4.5h5V12H17c0-2 .75-3.5 2.5-4.25z" />
    </IconBase>
  )
}

export function TableIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="3.75" y="4.75" width="16.5" height="14.5" rx="2" />
      <path d="M3.75 9.75h16.5" />
      <path d="M9.75 9.75v9.5" />
    </IconBase>
  )
}

export function HashIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M5 9.5h14" />
      <path d="M5 14.5h14" />
      <path d="M10 4.5 8.5 19.5" />
      <path d="M15.5 4.5 14 19.5" />
    </IconBase>
  )
}

export function ClockIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="8.25" />
      <path d="M12 7.5V12l3 1.75" />
    </IconBase>
  )
}

export function ShieldIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 3.5 5 6v5.5c0 4 2.9 7.6 7 9 4.1-1.4 7-5 7-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </IconBase>
  )
}

export function DatabaseIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <ellipse cx="12" cy="6.5" rx="7" ry="2.75" />
      <path d="M5 6.5v11c0 1.52 3.13 2.75 7 2.75s7-1.23 7-2.75v-11" />
      <path d="M5 12c0 1.52 3.13 2.75 7 2.75s7-1.23 7-2.75" />
    </IconBase>
  )
}

export function LayersIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m12 3.75 8 4.25-8 4.25-8-4.25z" />
      <path d="m4 12.5 8 4.25 8-4.25" />
      <path d="m4 16.25 8 4.25 8-4.25" />
    </IconBase>
  )
}

export function MenuIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </IconBase>
  )
}

export function FileTextIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M14 3H7.5A1.5 1.5 0 0 0 6 4.5v15A1.5 1.5 0 0 0 7.5 21h9a1.5 1.5 0 0 0 1.5-1.5V7z" />
      <path d="M14 3v4h4" />
      <path d="M9 12h6" />
      <path d="M9 16h4" />
    </IconBase>
  )
}

export function FilterIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 6.5h16" />
      <path d="M7 12h10" />
      <path d="M10 17.5h4" />
    </IconBase>
  )
}

export function LinkIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M10.5 13.5a4 4 0 0 0 5.66 0l2.5-2.5a4 4 0 0 0-5.66-5.66l-1.2 1.2" />
      <path d="M13.5 10.5a4 4 0 0 0-5.66 0l-2.5 2.5a4 4 0 0 0 5.66 5.66l1.2-1.2" />
    </IconBase>
  )
}

export function TargetIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="8.25" />
      <circle cx="12" cy="12" r="3.75" />
    </IconBase>
  )
}
export function LockIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="5" y="10.5" width="14" height="9.5" rx="2" />
      <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
      <path d="M12 14.5v2" />
    </IconBase>
  )
}

export function SparkIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 3.5 13.7 9l5.5 1.7-5.5 1.7L12 18l-1.7-5.6L4.8 10.7 10.3 9z" />
      <path d="M18.5 3.5v3" />
      <path d="M17 5h3" />
    </IconBase>
  )
}

export function BookIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M5 5.5A1.5 1.5 0 0 1 6.5 4H19v14H6.5A1.5 1.5 0 0 0 5 19.5z" />
      <path d="M5 19.5A1.5 1.5 0 0 1 6.5 18H19v2H6.5A1.5 1.5 0 0 1 5 19.5z" />
      <path d="M9 8h6" />
    </IconBase>
  )
}
export function PencilIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4.5 19.5h3.2l9.1-9.1a2.26 2.26 0 0 0-3.2-3.2L4.5 16.3z" />
      <path d="m13.8 7.2 3.2 3.2" />
    </IconBase>
  )
}

export function ExternalIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M14 5h5v5" />
      <path d="M19 5 11 13" />
      <path d="M18 14.5v3.25A1.75 1.75 0 0 1 16.25 19.5H6.5A1.75 1.75 0 0 1 4.75 17.75V8A1.75 1.75 0 0 1 6.5 6.25h3.25" />
    </IconBase>
  )
}
/**
 * The indeterminate progress arc.
 *
 * The stroke is heavier than the 1.5px of the rest of the set on purpose: at
 * 16px a 1.5px arc reads as a smudge.  The caller owns the animation, so the
 * icon can also be used as a static "busy" mark.
 */
export function SpinnerIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="9" opacity="0.2" />
      <path d="M21 12a9 9 0 0 0-9-9" />
    </IconBase>
  )
}
/**
 * The alert mark: a circle with an exclamation.
 *
 * `WarningIcon` is the triangle of a warning; this one is the roundel of an
 * error that has to be read, used where the message is a failure rather than
 * a caution.
 */
export function AlertIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="8.25" />
      <path d="M12 7.75v5" />
      <path d="M12 16.25h.01" />
    </IconBase>
  )
}

/**
 * The workspace mark: a folder with a document standing in it.
 *
 * `FolderIcon` is the plain folder of the file system; this one is the
 * container of the product - a workspace that holds documents.
 */
export function WorkspaceIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M3.75 6.75A1.5 1.5 0 0 1 5.25 5.25h3.9l1.6 2h7.99a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5z" />
      <path d="M9.5 11.25h5" />
      <path d="M9.5 14.25h3.5" />
    </IconBase>
  )
}

/**
 * The page mark: a single sheet with a folded corner.
 *
 * Used where the reference of a citation - the page a passage was found on -
 * has to be visible as a shape and not only as a number.
 */
export function PageIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M6 3.75h8.5L19 8.25v12H6z" />
      <path d="M14 3.75v4.5h5" />
      <path d="M9.25 12.5h6.5" />
      <path d="M9.25 16h4" />
    </IconBase>
  )
}