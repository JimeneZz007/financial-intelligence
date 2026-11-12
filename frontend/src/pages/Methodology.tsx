import { ChevronDown, FlaskConical } from 'lucide-react'
import type { ReactNode } from 'react'

import { Panel } from '@/components/common/Panel'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import type { KpiDefinition } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { formatMonth } from '@/lib/format'
import { useKpiCatalog } from '@/lib/queries'

const PROCESS: { phase: string; question: string; output: string }[] = [
  { phase: 'Business understanding', question: 'Which decisions must the platform support?', output: 'Six business questions about revenue, margins, expenses and budget' },
  { phase: 'Data understanding', question: 'Which sources exist, at what grain and quality?', output: 'Sales, expense ledger and budget extracts with documented defects' },
  { phase: 'Data preparation', question: 'How is data cleaned, validated and modelled?', output: 'Validated pipeline into a star schema, reconciled to control totals' },
  { phase: 'Modeling', question: 'Which metrics and methods are applied?', output: 'Formal KPI catalog, exact decompositions and robust anomaly detection' },
  { phase: 'Evaluation', question: 'Are the results correct and useful?', output: 'Figures triangulated three ways; detector scored against known scenarios' },
  { phase: 'Presentation', question: 'How are results communicated?', output: 'This application and a Power BI report specification on the same model' },
]

const FACTS: { table: string; grain: string; date: string; unit: boolean; product: boolean; center: boolean; account: boolean }[] = [
  { table: 'fact_sales', grain: 'Day × business unit × product', date: 'Day', unit: true, product: true, center: false, account: false },
  { table: 'fact_operating_expenses', grain: 'Expense ledger entry', date: 'Day', unit: true, product: false, center: true, account: true },
  { table: 'fact_budget', grain: 'Month × business unit × account', date: 'Month', unit: true, product: false, center: false, account: true },
]

const METHODS: { name: string; summary: string; formula: string }[] = [
  {
    name: 'Variance analysis',
    summary:
      'Compares actuals with the budget or a comparison period. Favorability follows the effect on profit: spending below budget is favorable, selling below budget is not. Variances under 0.5% count as on target.',
    formula: 'variance = actual − reference      variance % = variance / |reference|',
  },
  {
    name: 'Operating income bridge',
    summary: 'Walks from one operating income to another, one line at a time. The steps add up exactly to the change.',
    formula: 'ΔOI = Δrevenue − Δdirect costs − Σ Δexpenses by group',
  },
  {
    name: 'Price, volume and mix',
    summary:
      'Splits a change in net revenue per product within each business unit. Price is net revenue per unit, so discounts count as price.',
    formula: 'volume = (Q₁−Q₀)·s₀·p₀    mix = (s₁−s₀)·Q₁·p₀    price = (p₁−p₀)·q₁',
  },
  {
    name: 'Margin mix and rate',
    summary: 'Splits a change in gross margin into categories becoming more or less profitable (rate) and revenue shifting between them (mix).',
    formula: 'rate = w₁·(m₁−m₀)      mix = (w₁−w₀)·(m₀−M₀)',
  },
  {
    name: 'Anomaly detection',
    summary:
      'Flags months whose budget variance is far from the typical variance of that business unit and account, using a median-based score that anomalies themselves barely move. A flag also needs a 1-point deviation; it is material from 0.5% of the unit’s average monthly revenue.',
    formula: 'z = 0.6745 · (variance % − median) / MAD      flag when |z| > 3.5',
  },
]

const LIMITATIONS = [
  'All data is synthetic. Patterns were designed by the author, so finding them shows the methods work on these patterns, not on real data.',
  'Results stop at operating income: no interest, taxes, balance sheet or cash flow.',
  'Operating expenses are not recorded by product, so operating income exists only by period and business unit.',
  'There is a single approved budget version: no forecasts or re-forecasts.',
  'Decompositions are arithmetic identities and anomalies are statistical flags. Neither establishes why something happened.',
  'The application has no authentication and is meant to run locally.',
]

function Mark({ on }: { on: boolean }) {
  return on ? (
    <span className="text-favorable-text" aria-label="Yes">●</span>
  ) : (
    <span className="text-subtle" aria-label="No">–</span>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-foreground/90">{children}</dd>
    </>
  )
}

function KpiEntry({ kpi }: { kpi: KpiDefinition }) {
  return (
    <details className="group border-b last:border-b-0" data-testid={`kpi-definition-${kpi.id}`}>
      <summary className="flex cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden">
        <ChevronDown aria-hidden className="size-4 shrink-0 text-subtle transition-transform group-open:rotate-180" />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold text-foreground">{kpi.name}</span>
          <code className="mt-0.5 block truncate font-mono text-[11px] text-muted-foreground">{kpi.formula}</code>
        </span>
        <span className="hidden shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground sm:inline">{kpi.unit}</span>
      </summary>
      <dl className="mb-4 ml-7 grid gap-x-6 gap-y-2 text-xs leading-relaxed sm:grid-cols-[8.5rem_1fr]">
        <Field label="Formula">
          <code className="font-mono text-[11px] break-words">{kpi.formula}</code>
        </Field>
        <Field label="Grain">{kpi.grain}</Field>
        <Field label="Filters">{kpi.filters}</Field>
        <Field label="Missing values">{kpi.null_handling}</Field>
        <Field label="Interpretation">{kpi.interpretation}</Field>
        <Field label="Limitations">{kpi.limitations}</Field>
      </dl>
    </details>
  )
}

export default function Methodology() {
  const catalog = useKpiCatalog()
  const { dimensions } = useFilters()
  const { period } = dimensions
  return (
    <div className="space-y-4">
      <section
        aria-label="About the data"
        className="flex gap-4 rounded-xl border border-brand/25 bg-brand/[0.06] p-5"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand/15 text-brand">
          <FlaskConical aria-hidden className="size-4" />
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">Everything here is synthetic</h2>
          <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-muted-foreground">
            {dimensions.company} is a fictional company. Its sales, expenses and budget are produced by a reproducible
            generator with a fixed seed and documented assumptions. No figure describes or approximates a real
            business.
          </p>
          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-xs">
            {[
              ['Period', `${formatMonth(period.start)} – ${formatMonth(period.end)} (${period.months.length} months)`],
              ['Currency', dimensions.currency],
              ['Business units', String(dimensions.business_units.length)],
              ['Products', `${dimensions.products.length} in ${dimensions.categories.length} categories`],
              ['Accounts', String(dimensions.accounts.length)],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-subtle">{label}</dt>
                <dd className="mt-0.5 font-medium text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Analytical process" description="CRISP-DM phases and what each one produced">
          <ol className="space-y-3.5">
            {PROCESS.map((step, index) => (
              <li key={step.phase} className="flex gap-3">
                <span className="tabular flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold text-muted-foreground">
                  {index + 1}
                </span>
                <div className="min-w-0 text-xs leading-relaxed">
                  <p className="text-[13px] font-semibold text-foreground">{step.phase}</p>
                  <p className="text-muted-foreground">{step.question}</p>
                  <p className="text-foreground/85">{step.output}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>

        <Panel title="Data model" description="Star schema: three facts sharing conformed dimensions">
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full text-xs" aria-label="Fact tables, their grain and their dimensions">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th scope="col" className="py-2 pr-3 font-medium">Fact table</th>
                  <th scope="col" className="px-2 py-2 text-center font-medium">Date</th>
                  <th scope="col" className="px-2 py-2 text-center font-medium">Unit</th>
                  <th scope="col" className="px-2 py-2 text-center font-medium">Product</th>
                  <th scope="col" className="px-2 py-2 text-center font-medium">Cost center</th>
                  <th scope="col" className="px-2 py-2 text-center font-medium">Account</th>
                </tr>
              </thead>
              <tbody>
                {FACTS.map((fact) => (
                  <tr key={fact.table} className="border-b last:border-b-0">
                    <th scope="row" className="py-2.5 pr-3 text-left font-normal">
                      <code className="font-mono text-[11px] text-foreground">{fact.table}</code>
                      <span className="mt-0.5 block text-muted-foreground">{fact.grain}</span>
                    </th>
                    <td className="px-2 text-center text-foreground/90">{fact.date}</td>
                    <td className="px-2 text-center"><Mark on={fact.unit} /></td>
                    <td className="px-2 text-center"><Mark on={fact.product} /></td>
                    <td className="px-2 text-center"><Mark on={fact.center} /></td>
                    <td className="px-2 text-center"><Mark on={fact.account} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-4 space-y-2 border-t pt-4 text-xs leading-relaxed text-muted-foreground">
            <li>
              <span className="font-medium text-foreground/90">Why only two global filters.</span> Period and business
              unit are the only dimensions shared by all three facts. Filtering operating income by product would need
              an arbitrary allocation of expenses.
            </li>
            <li>
              <span className="font-medium text-foreground/90">No double counting.</span> Revenue and direct costs live
              only in sales, operating expenses only in the ledger, and the budget is compared with actuals, never
              added to them. Facts are aggregated to a common grain before being combined.
            </li>
            <li>
              <span className="font-medium text-foreground/90">Ratios.</span> Every margin is a ratio of sums for the
              selected slice, never an average of percentages.
            </li>
          </ul>
        </Panel>
      </div>

      <Panel title="KPI catalog" description="Formal definition of every indicator, served by the API">
        <QueryBoundary query={catalog} minHeight={320}>
          {(data) => (
            <div>
              {data.kpis.map((kpi) => (
                <KpiEntry key={kpi.id} kpi={kpi} />
              ))}
            </div>
          )}
        </QueryBoundary>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Analytical methods" description="What each analysis computes" className="xl:col-span-2">
          <ul className="divide-y">
            {METHODS.map((method) => (
              <li key={method.name} className="py-3.5 first:pt-0 last:pb-0">
                <h3 className="text-[13px] font-semibold text-foreground">{method.name}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{method.summary}</p>
                <code className="mt-2 block overflow-x-auto rounded-md bg-muted/70 px-3 py-2 font-mono text-[11px] whitespace-pre text-foreground/90">
                  {method.formula}
                </code>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Limitations" description="What this platform does not claim">
          <ul className="space-y-3 text-xs leading-relaxed text-muted-foreground">
            {LIMITATIONS.map((item) => (
              <li key={item} className="flex gap-2.5">
                <span aria-hidden className="mt-1.5 size-1 shrink-0 rounded-full bg-subtle" />
                {item}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  )
}
