import { Table2, ChartNoAxesColumn } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface PanelProps {
  title: string
  description?: ReactNode
  /** Controls shown at the right of the header (tabs, selects, export). */
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  /** Dims the body while a new slice of data loads; the previous render stays in place. */
  stale?: boolean
}

/** Card surface used by every block of the dashboard. */
export function Panel({ title, description, actions, children, className, bodyClassName, stale }: PanelProps) {
  const headingId = useId()
  return (
    <section
      aria-labelledby={headingId}
      className={cn('flex min-w-0 flex-col rounded-xl border bg-card shadow-[0_1px_0_0_rgb(255_255_255/0.03)_inset]', className)}
    >
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 pt-4 pb-3">
        <div className="min-w-0">
          <h2 id={headingId} className="text-sm font-semibold tracking-tight text-foreground">
            {title}
          </h2>
          {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex max-w-full min-w-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      <div
        aria-busy={stale || undefined}
        className={cn('flex min-w-0 flex-1 flex-col px-5 pb-5 transition-opacity duration-200 *:min-w-0', stale && 'opacity-55', bodyClassName)}
      >
        {children}
      </div>
    </section>
  )
}

export interface TableView {
  columns: string[]
  rows: (string | number)[][]
}

interface ChartPanelProps extends PanelProps {
  /** The same data as a table: the accessible twin of the chart. */
  table?: TableView
  legend?: ReactNode
}

/** A panel whose chart can be swapped for its data table. */
export function ChartPanel({ table, legend, actions, children, ...panel }: ChartPanelProps) {
  const [showTable, setShowTable] = useState(false)
  const toggle = table ? (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-pressed={showTable}
          aria-label={showTable ? `Show chart: ${panel.title}` : `Show data table: ${panel.title}`}
          onClick={() => setShowTable((value) => !value)}
          className="text-muted-foreground"
        >
          {showTable ? <ChartNoAxesColumn /> : <Table2 />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{showTable ? 'Show chart' : 'Show data table'}</TooltipContent>
    </Tooltip>
  ) : null

  return (
    <Panel
      {...panel}
      actions={
        <>
          {actions}
          {toggle}
        </>
      }
    >
      {showTable && table ? (
        <div className="scrollbar-thin max-h-[340px] overflow-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {table.columns.map((column, index) => (
                  <TableHead key={column} className={cn('h-9 text-xs', index > 0 && 'text-right')}>
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {table.rows.map((row, rowIndex) => (
                <TableRow key={rowIndex}>
                  {row.map((cell, index) => (
                    <TableCell key={index} className={cn('py-2 text-xs', index > 0 && 'tabular text-right')}>
                      {cell}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <>
          {legend ? <div className="mb-2">{legend}</div> : null}
          {children}
        </>
      )}
    </Panel>
  )
}

export interface LegendItem {
  label: string
  color: string
  /** Mirrors the mark: a block for bars, a stroke for lines. */
  mark?: 'bar' | 'line'
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Legend">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn('inline-block shrink-0', item.mark === 'line' ? 'h-0.5 w-3.5 rounded-full' : 'size-2.5 rounded-[3px]')}
            style={{ backgroundColor: item.color }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  )
}
