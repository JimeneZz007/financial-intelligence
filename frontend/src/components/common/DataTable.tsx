import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

export type SortDirection = 'asc' | 'desc'

export interface SortState {
  key: string
  direction: SortDirection
}

export interface Column<T> {
  key: string
  header: string
  align?: 'left' | 'right'
  render: (row: T) => ReactNode
  /** Value used for sorting; a column without it is not sortable. */
  sortValue?: (row: T) => number | string | null | undefined
  /** Longer explanation of the header, exposed as a tooltip. */
  title?: string
  className?: string
}

interface DataTableProps<T> {
  /** Accessible name of the table. */
  label: string
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  /** Row rendered in the footer (totals). */
  footer?: T
  /**
   * Controlled sorting: when provided, the table does not sort the rows itself
   * (the server already did) and only reports header clicks.
   */
  sort?: SortState
  onSortChange?: (sort: SortState) => void
  initialSort?: SortState
  emphasizedRow?: (row: T) => boolean
  dense?: boolean
  /** Show only the first rows after sorting (use with a "show all" control). */
  limit?: number
}

function compare(a: number | string | null | undefined, b: number | string | null | undefined): number {
  if (a == null && b == null) return 0
  if (a == null) return 1 // missing values always sort last
  if (b == null) return -1
  return typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b))
}

/** Sortable table. Headers are real buttons and expose `aria-sort` for assistive technology. */
export function DataTable<T>({
  label,
  columns,
  rows,
  rowKey,
  footer,
  sort,
  onSortChange,
  initialSort,
  emphasizedRow,
  dense,
  limit,
}: DataTableProps<T>) {
  const [localSort, setLocalSort] = useState<SortState | undefined>(initialSort)
  const controlled = sort !== undefined
  const active = controlled ? sort : localSort

  const sorted = useMemo(() => {
    if (controlled || !active) return rows
    const column = columns.find((item) => item.key === active.key)
    if (!column?.sortValue) return rows
    const factor = active.direction === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const left = column.sortValue!(a)
      const right = column.sortValue!(b)
      if (left == null || right == null) return compare(left, right)
      return factor * compare(left, right)
    })
  }, [rows, columns, active, controlled])

  const requestSort = (column: Column<T>) => {
    const next: SortState =
      active?.key === column.key
        ? { key: column.key, direction: active.direction === 'asc' ? 'desc' : 'asc' }
        : { key: column.key, direction: column.align === 'right' ? 'desc' : 'asc' }
    if (controlled) onSortChange?.(next)
    else setLocalSort(next)
  }

  const cellPadding = dense ? 'py-2' : 'py-2.5'

  return (
    <div className="scrollbar-thin overflow-x-auto">
      <Table aria-label={label}>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((column) => {
              const isSorted = active?.key === column.key
              const sortable = controlled ? Boolean(onSortChange) && column.sortValue !== undefined : column.sortValue !== undefined
              const Icon = !isSorted ? ChevronsUpDown : active?.direction === 'asc' ? ArrowUp : ArrowDown
              return (
                <TableHead
                  key={column.key}
                  title={column.title}
                  aria-sort={isSorted ? (active?.direction === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={cn('h-9 text-xs font-medium whitespace-nowrap text-muted-foreground', column.align === 'right' && 'text-right')}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => requestSort(column)}
                      className={cn(
                        '-mx-1.5 inline-flex items-center gap-1 rounded px-1.5 py-1 hover:text-foreground',
                        column.align === 'right' && 'flex-row-reverse',
                        isSorted && 'text-foreground',
                      )}
                    >
                      {column.header}
                      <Icon aria-hidden className={cn('size-3', !isSorted && 'opacity-50')} />
                    </button>
                  ) : (
                    column.header
                  )}
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(limit ? sorted.slice(0, limit) : sorted).map((row) => (
            <TableRow key={rowKey(row)} className={cn(emphasizedRow?.(row) && 'bg-muted/40 font-semibold')}>
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  className={cn(cellPadding, 'text-[13px] whitespace-nowrap', column.align === 'right' && 'tabular text-right', column.className)}
                >
                  {column.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
        {footer ? (
          <TableFooter>
            <TableRow className="hover:bg-transparent">
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  className={cn(cellPadding, 'text-[13px] font-semibold whitespace-nowrap', column.align === 'right' && 'tabular text-right')}
                >
                  {column.render(footer)}
                </TableCell>
              ))}
            </TableRow>
          </TableFooter>
        ) : null}
      </Table>
    </div>
  )
}

interface PaginationProps {
  page: number
  totalPages: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, totalItems, pageSize, onPageChange }: PaginationProps) {
  const first = totalItems === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(totalItems, page * pageSize)
  return (
    <nav aria-label="Table pagination" className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
      <p className="tabular" aria-live="polite">
        {first}–{last} of {totalItems} rows
      </p>
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="icon-sm" aria-label="Previous page" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft />
        </Button>
        <span className="tabular px-1.5">
          Page {page} of {totalPages}
        </span>
        <Button variant="outline" size="icon-sm" aria-label="Next page" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}
