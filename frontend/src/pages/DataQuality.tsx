import { Check, CircleX, Inbox, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Segmented, ShowAllToggle } from '@/components/common/controls'
import { DataTable, type Column } from '@/components/common/DataTable'
import { Panel } from '@/components/common/Panel'
import { QueryBoundary, StateMessage } from '@/components/common/QueryBoundary'
import { StatStrip, type Stat } from '@/components/common/StatStrip'
import type { DataQualityResponse, QualityCheckItem } from '@/lib/api'
import { formatDateTime, formatInteger, formatPercent } from '@/lib/format'
import { useDataQuality } from '@/lib/queries'
import { cn } from '@/lib/utils'

type RunItem = NonNullable<DataQualityResponse['latest_run']>
type LoadItem = DataQualityResponse['table_loads'][number]

const CHECK_STATUS = {
  PASS: { label: 'Pass', icon: Check, className: 'bg-favorable/12 text-favorable-text ring-favorable/25' },
  WARN: { label: 'Handled', icon: TriangleAlert, className: 'bg-caution/12 text-caution ring-caution/30' },
  FAIL: { label: 'Fail', icon: CircleX, className: 'bg-unfavorable/12 text-unfavorable-text ring-unfavorable/25' },
} as const

function CheckBadge({ status }: { status: string }) {
  const spec = CHECK_STATUS[status as keyof typeof CHECK_STATUS] ?? CHECK_STATUS.FAIL
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset', spec.className)}>
      <spec.icon aria-hidden className="size-3" />
      {spec.label}
    </span>
  )
}

const RUN_STATUS = {
  SUCCESS: { ...CHECK_STATUS.PASS, label: 'Succeeded' },
  RUNNING: { ...CHECK_STATUS.WARN, label: 'Running' },
  FAILED: { ...CHECK_STATUS.FAIL, label: 'Failed' },
} as const

function RunBadge({ status }: { status: string }) {
  const spec = RUN_STATUS[status as keyof typeof RUN_STATUS] ?? RUN_STATUS.FAILED
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset', spec.className)}>
      <spec.icon aria-hidden className="size-3" />
      {spec.label}
    </span>
  )
}

// Problems first: failed rules, then the ones the pipeline handled, then clean passes.
const STATUS_ORDER: Record<string, number> = { FAIL: 0, WARN: 1, PASS: 2 }
const RULES_PREVIEW = 12

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1).toLowerCase()

// --------------------------------------------------------------------------- //
// Summary
// --------------------------------------------------------------------------- //
function summaryStats(data: DataQualityResponse): Stat[] {
  const { latest_run: run, summary } = data
  if (!run || !summary) return []
  return [
    {
      label: 'Latest pipeline run',
      value: run.status === 'SUCCESS' ? 'Succeeded' : capitalize(run.status),
      detail: `${formatDateTime(run.finished_at ?? run.started_at)} · ${run.duration_seconds?.toFixed(1) ?? '—'} s`,
    },
    {
      label: 'Rules passed',
      value: `${summary.passed} of ${summary.total_checks}`,
      detail: `${summary.warnings} handled automatically · ${summary.failed} failed`,
    },
    {
      label: 'Rows loaded',
      value: formatInteger(summary.rows_loaded),
      detail: `${formatPercent(summary.load_rate, 2)} of ${formatInteger(summary.rows_read)} rows read`,
    },
    {
      label: 'Rows set aside',
      value: formatInteger(summary.rows_rejected + summary.rows_deduplicated),
      detail: `${formatInteger(summary.rows_rejected)} quarantined · ${formatInteger(summary.rows_deduplicated)} duplicates`,
    },
  ]
}

// --------------------------------------------------------------------------- //
// Row accounting
// --------------------------------------------------------------------------- //
const LOAD_COLUMNS: Column<LoadItem>[] = [
  {
    key: 'source',
    header: 'Source extract',
    render: (row) => (
      <span className="flex flex-col">
        <span className="font-medium text-foreground">{row.source_file}</span>
        <span className="text-[11px] text-subtle">→ {row.target_table}</span>
      </span>
    ),
  },
  { key: 'read', header: 'Read', align: 'right', render: (row) => formatInteger(row.rows_read) },
  {
    key: 'standardized',
    header: 'Repaired',
    align: 'right',
    title: 'Rows with recoverable format problems that were standardised and kept',
    render: (row) => formatInteger(row.rows_standardized),
  },
  {
    key: 'rejected',
    header: 'Quarantined',
    align: 'right',
    title: 'Rows that broke a rule and were not loaded',
    render: (row) => formatInteger(row.rows_rejected),
  },
  { key: 'duplicates', header: 'Duplicates', align: 'right', render: (row) => formatInteger(row.rows_deduplicated) },
  {
    key: 'loaded',
    header: 'Loaded',
    align: 'right',
    render: (row) => <span className="font-medium text-foreground">{formatInteger(row.rows_loaded)}</span>,
  },
  {
    key: 'rate',
    header: 'Load rate',
    align: 'right',
    render: (row) => formatPercent(row.rows_read ? row.rows_loaded / row.rows_read : null, 2),
  },
]

// --------------------------------------------------------------------------- //
// Rules
// --------------------------------------------------------------------------- //
type StatusFilter = 'all' | 'WARN' | 'PASS' | 'FAIL'
type StageFilter = 'all' | 'SOURCE' | 'WAREHOUSE'

const CHECK_COLUMNS: Column<QualityCheckItem>[] = [
  { key: 'status', header: 'Result', sortValue: (row) => STATUS_ORDER[row.status] ?? 0, render: (row) => <CheckBadge status={row.status} /> },
  {
    key: 'rule',
    header: 'Rule',
    sortValue: (row) => row.check_name,
    className: 'whitespace-normal',
    render: (row) => (
      <span className="flex min-w-64 flex-col">
        <span className="text-foreground">{row.check_name}</span>
        <span className="text-[11px] text-subtle">{row.check_code}</span>
      </span>
    ),
  },
  { key: 'dataset', header: 'Dataset', sortValue: (row) => row.dataset, render: (row) => row.dataset },
  { key: 'dimension', header: 'Dimension', sortValue: (row) => row.quality_dimension, render: (row) => capitalize(row.quality_dimension) },
  { key: 'stage', header: 'Stage', sortValue: (row) => row.stage, render: (row) => capitalize(row.stage) },
  { key: 'checked', header: 'Rows checked', align: 'right', sortValue: (row) => row.rows_checked, render: (row) => formatInteger(row.rows_checked) },
  {
    key: 'failed',
    header: 'Rows affected',
    align: 'right',
    sortValue: (row) => row.rows_failed,
    render: (row) => (row.rows_failed ? <span className="font-medium text-foreground">{formatInteger(row.rows_failed)}</span> : '0'),
  },
]

function RulesPanel({ checks }: { checks: QualityCheckItem[] }) {
  const [status, setStatus] = useState<StatusFilter>('all')
  const [stage, setStage] = useState<StageFilter>('all')
  const [expanded, setExpanded] = useState(false)
  const visible = useMemo(
    () => checks.filter((check) => (status === 'all' || check.status === status) && (stage === 'all' || check.stage === stage)),
    [checks, status, stage],
  )
  return (
    <Panel
      title="Data-quality rules"
      description={`${visible.length} of ${checks.length} rules of the latest run`}
      actions={
        <>
          <Segmented
            label="Filter rules by result"
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: 'All' },
              { value: 'WARN', label: 'Handled' },
              { value: 'PASS', label: 'Pass' },
              { value: 'FAIL', label: 'Fail' },
            ]}
          />
          <Segmented
            label="Filter rules by stage"
            value={stage}
            onChange={setStage}
            options={[
              { value: 'all', label: 'All stages' },
              { value: 'SOURCE', label: 'Source' },
              { value: 'WAREHOUSE', label: 'Warehouse' },
            ]}
          />
        </>
      }
    >
      {visible.length === 0 ? (
        <StateMessage icon={<Inbox />} title="No rules match these filters" hint="Choose another result or stage." minHeight={200} />
      ) : (
        <div>
          <DataTable
            label="Data-quality rules"
            columns={CHECK_COLUMNS}
            rows={visible}
            rowKey={(row) => row.check_code}
            initialSort={{ key: 'status', direction: 'asc' }}
            limit={expanded ? undefined : RULES_PREVIEW}
            dense
          />
          {visible.length > RULES_PREVIEW ? (
            <ShowAllToggle expanded={expanded} total={visible.length} noun="rules" onToggle={() => setExpanded((value) => !value)} />
          ) : null}
        </div>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-subtle">
        "Handled" means the pipeline found a problem and resolved it by repairing, deduplicating or quarantining the
        rows. A failed blocking rule aborts the run and rolls the load back, so the warehouse keeps its previous data.
      </p>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Tables and history
// --------------------------------------------------------------------------- //
const RUN_COLUMNS: Column<RunItem>[] = [
  { key: 'id', header: 'Run', render: (row) => `#${row.run_id}` },
  { key: 'started', header: 'Started', render: (row) => formatDateTime(row.started_at) },
  { key: 'duration', header: 'Duration', align: 'right', render: (row) => (row.duration_seconds == null ? '—' : `${row.duration_seconds.toFixed(1)} s`) },
  { key: 'status', header: 'Result', render: (row) => <RunBadge status={row.status} /> },
  {
    key: 'detail',
    header: 'Detail',
    className: 'whitespace-normal',
    render: (row) =>
      row.error_message ? (
        <span className="line-clamp-2 max-w-md text-xs text-unfavorable-text" title={row.error_message}>
          {row.error_message}
        </span>
      ) : row.data_period_start && row.data_period_end ? (
        `${row.data_period_start} to ${row.data_period_end}`
      ) : (
        '—'
      ),
  },
]

function TableCounts({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts)
  return (
    <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
      {entries.map(([table, count]) => (
        <div key={table} className="flex items-baseline justify-between gap-3 border-b py-2 text-[13px] last:border-b-0">
          <dt className="font-mono text-xs text-muted-foreground">{table}</dt>
          <dd className="tabular font-medium text-foreground">{formatInteger(count)}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function DataQuality() {
  const quality = useDataQuality()
  return (
    <QueryBoundary
      query={quality}
      minHeight={480}
      isEmpty={(data) => data.latest_run === null}
      emptyTitle="The pipeline has not run yet"
      emptyHint="Run `make pipeline` to generate the data, migrate the schema and load the warehouse."
    >
      {(data) => (
        <div className="space-y-4">
          <StatStrip label="Data quality summary" stats={summaryStats(data)} />
          <Panel
            title="Row accounting"
            description="Every row read from a source extract is repaired, quarantined, removed as a duplicate or loaded"
          >
            <DataTable label="Rows per source extract" columns={LOAD_COLUMNS} rows={data.table_loads} rowKey={(row) => row.target_table} />
          </Panel>
          <RulesPanel checks={data.checks} />
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Warehouse tables" description="Rows currently stored in each table of the star schema">
              <TableCounts counts={data.table_row_counts} />
            </Panel>
            <Panel title="Run history" description="Most recent pipeline runs, including failed ones">
              <DataTable label="Pipeline run history" columns={RUN_COLUMNS} rows={data.recent_runs} rowKey={(row) => String(row.run_id)} dense />
            </Panel>
          </div>
        </div>
      )}
    </QueryBoundary>
  )
}
