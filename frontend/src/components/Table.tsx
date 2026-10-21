import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface TableProps {
  children: ReactNode
  className?: string
  /** Screen-reader caption describing the table. */
  caption?: string
}

export function Table({ children, className, caption }: TableProps) {
  return (
    <div className={cn('w-full overflow-x-auto scroll-thin', className)}>
      <table className="w-full min-w-[52rem] border-collapse text-left text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  )
}

export function TableHead({ children, className }: TableProps) {
  return <thead className={cn('bg-surface-muted', className)}>{children}</thead>
}

export function TableBody({ children, className }: TableProps) {
  return <tbody className={cn('divide-y divide-line', className)}>{children}</tbody>
}

export interface TableRowProps {
  children: ReactNode
  className?: string
}

export function TableRow({ children, className }: TableRowProps) {
  return <tr className={cn('bg-surface align-top', className)}>{children}</tr>
}

export interface TableHeadCellProps {
  children: ReactNode
  className?: string
  scope?: 'col' | 'row'
}

export function TableHeadCell({ children, className, scope = 'col' }: TableHeadCellProps) {
  return (
    <th
      scope={scope}
      className={cn(
        'px-4 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase whitespace-nowrap',
        className,
      )}
    >
      {children}
    </th>
  )
}

export interface TableCellProps {
  children: ReactNode
  className?: string
  colSpan?: number
}

export function TableCell({ children, className, colSpan }: TableCellProps) {
  return (
    <td colSpan={colSpan} className={cn('px-4 py-3 text-sm text-ink', className)}>
      {children}
    </td>
  )
}
