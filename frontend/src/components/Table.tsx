import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface TableProps {
  children: ReactNode
  className?: string
  /** Screen-reader caption describing the table. */
  caption?: string
  /** The minimum width of the table element, as a utility class. */
  minWidth?: string
}

export function Table({ children, className, caption, minWidth = 'min-w-[64rem]' }: TableProps) {
  return (
    <div className={cn('w-full overflow-x-auto scroll-thin', className)}>
      <table className={cn('w-full border-collapse text-left text-small', minWidth)}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  )
}

export function TableHead({ children, className }: TableProps) {
  return <thead className={cn(className)}>{children}</thead>
}

export function TableBody({ children, className }: TableProps) {
  return <tbody className={cn('divide-y divide-line', className)}>{children}</tbody>
}

export interface TableRowProps {
  children: ReactNode
  className?: string
}

export function TableRow({ children, className }: TableRowProps) {
  return <tr className={cn('bg-surface transition-colors', className)}>{children}</tr>
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
        'border-b border-line bg-surface-muted/60 px-4 py-2.5 text-micro font-semibold tracking-[0.08em] text-ink-subtle uppercase whitespace-nowrap sm:px-5',
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
    <td colSpan={colSpan} className={cn('px-4 py-3.5 text-small text-ink sm:px-5', className)}>
      {children}
    </td>
  )
}

/**
 * The identity cell of a row.
 *
 * It is a `th` with `scope="row"`, so a screen reader announces the name of
 * the row while the cell is read - but it is styled like the other cells,
 * because in a data table the row header is data, not a label.
 */
export function TableRowHeader({ children, className }: TableCellProps) {
  return (
    <th
      scope="row"
      className={cn('px-4 py-3.5 text-left text-small font-normal text-ink sm:px-5', className)}
    >
      {children}
    </th>
  )
}