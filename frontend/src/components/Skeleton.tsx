import { cn } from '../lib/cn'

export interface SkeletonProps {
  className?: string
}

/**
 * A single shimmering placeholder block.
 *
 * The skeleton replaces the raw spinner wherever the shape of the content is
 * known - a list of rows, a card, a line of text.  The shimmer is decorative
 * and is removed by the reduced-motion rule.
 */
export function Skeleton({ className }: SkeletonProps) {
  return <span aria-hidden="true" className={cn('skeleton block', className)} />
}

export interface SkeletonTextProps {
  /** Number of lines to reserve. */
  lines?: number
  className?: string
}

export function SkeletonText({ lines = 3, className }: SkeletonTextProps) {
  return (
    <div className={cn('flex flex-col gap-2', className)} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          className={cn('h-3', index === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  )
}

export interface SkeletonCardProps {
  className?: string
}

/** The placeholder of a workspace card. */
export function SkeletonCard({ className }: SkeletonCardProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        'flex flex-col gap-4 rounded-card border border-line bg-surface p-5',
        className,
      )}
    >
      <Skeleton className="h-5 w-2/3" />
      <SkeletonText lines={2} />
      <div className="flex gap-4 border-t border-line pt-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  )
}

export interface SkeletonRowsProps {
  /** Number of placeholder rows. */
  rows?: number
  className?: string
}

/** The placeholder of a data table. */
export function SkeletonRows({ rows = 5, className }: SkeletonRowsProps) {
  return (
    <div className={cn('flex flex-col divide-y divide-line-faint', className)} aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-4 px-4 py-4 sm:px-5">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-3 w-1/5" />
          <Skeleton className="h-3 w-1/6" />
          <Skeleton className="h-5 w-20 rounded-pill" />
          <Skeleton className="ml-auto h-3 w-16" />
        </div>
      ))}
    </div>
  )
}