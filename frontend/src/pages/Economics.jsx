import { useEffect, useState } from 'react'
import { useDashboard } from '../api'
import { FilterBar, toQuery, useFilters } from '../filters'
import { dash, dateLabel, money, moneyCompact, pct } from '../format'
import { Badge, Bar, Coverage, Kpi, PageHeader, Panel, SampleMark, SourceKey, State } from '../ui'

function hours(value) {
  if (value === null || value === undefined) return '–'
  return `${Math.round(value).toLocaleString()} h`
}

function share(value) {
  if (value === null || value === undefined) return '–'
  return `${(value * 100).toFixed(1)}%`
}

const SORTS = {
  hours: { label: 'Hours', get: (a) => a.hours, share: (a) => a.share_hours },
  cost: { label: 'Cost', get: (a) => a.cost, share: (a) => a.share_cost },
}

export default function Economics() {
  const [filters, setFilters, resetFilters] = useFilters()
  const { data, error, updatedAt, reload } = useDashboard(`/api/economics${toQuery(filters)}`)

  return (
    <State data={data} error={error}>
      {data ? (
        <div className="px-5 py-6 lg:px-8">
          <PageHeader
            kicker="Economics"
            title="Where are we spending our time and money?"
            lede="Three results, one ranking, and the path from applicant to deployment. Hours and dollars use the sample rates at the bottom."
            asOf={dateLabel(data.as_of)}
            updatedAt={updatedAt}
          />
          <SourceKey />
          <FilterBar filters={filters} onChange={setFilters} onReset={resetFilters} options={data.options} />
          {error ? <p className="text-sm text-clay mb-3">Last refresh failed: {error}</p> : null}
          <p className="text-xs text-ink/60 mb-4">
            Hiring snapshot: week ending {dateLabel(data.week_ending)}. Counts are the latest week in range, {data.filters.basis === 'reported' ? 'reported only' : 'reported plus inferred from later stages'}.
            {data.notes[0] ? ` ${data.notes[0]}` : ''}
          </p>

          <Headline data={data} />
          <TimeChart burn={data.burn} />
          <Lifecycle hiring={data.hiring} />
          <Insight text={data.insights[0]} />

          <details className="mt-4 bg-card border border-line rounded-lg">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Data coverage</summary>
            <div className="px-4 pb-4">
              <Coverage items={data.coverage} plain />
            </div>
          </details>

          <details className="mt-3 bg-card border border-dashed border-brass rounded-lg">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold flex items-center gap-2">
              Sample rate assumptions <SampleMark />
            </summary>
            <div className="px-4 pb-4">
              <RatesEditor rates={data.rates} onSaved={reload} />
            </div>
          </details>
        </div>
      ) : null}
    </State>
  )
}

function Headline({ data }) {
  const k = data.burn.kpis
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <Kpi sample label="Total resource hours" value={hours(k.total_hours)} detail="Workbook volumes × sample hours per activity" />
      <Kpi sample label="Total resource cost" value={moneyCompact(k.total_cost)} detail="Those hours × sample hourly and unit costs" />
      <Kpi sample label="Cost per hire" value={money(k.cost_per_hire)} detail={`Sample recruitment cost ÷ ${dash(k.accepted)} accepted offers`} />
    </div>
  )
}

function TimeChart({ burn }) {
  const [sortBy, setSortBy] = useState('hours')
  const metric = SORTS[sortBy]
  const ranked = burn.activities.filter((activity) => metric.get(activity)).sort((a, b) => metric.get(b) - metric.get(a))
  const excluded = burn.activities.length - ranked.length
  const max = ranked.length ? metric.get(ranked[0]) : 0

  return (
    <Panel
      title="Where is our time going?"
      className="mt-4"
      extra={
        <label className="text-xs text-ink/60 flex items-center gap-2">
          Rank by
          <select className="bg-card border border-line rounded px-1.5 py-1 text-xs" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            {Object.entries(SORTS).map(([key, value]) => (
              <option key={key} value={key}>
                {value.label}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {ranked.length ? (
        <ol className="space-y-2.5">
          <li className="grid grid-cols-[1.5rem_minmax(0,14rem)_1fr_4.5rem_5rem_3.5rem] gap-2 text-[11px] uppercase tracking-wider text-ink/45">
            <span>#</span>
            <span>Activity</span>
            <span />
            <span className="text-right">Hours <SampleMark /></span>
            <span className="text-right">Cost <SampleMark /></span>
            <span className="text-right">% total</span>
          </li>
          {ranked.map((activity, index) => (
            <li key={activity.code} className="grid grid-cols-[1.5rem_minmax(0,14rem)_1fr_4.5rem_5rem_3.5rem] gap-2 items-center text-sm">
              <span className="font-mono text-xs text-ink/50">#{index + 1}</span>
              <span className="truncate" title={activity.label}>
                {activity.label}
              </span>
              <Bar value={metric.get(activity)} max={max} tone={activity.phase === 'recruitment' ? 'bg-moss' : activity.phase === 'training' ? 'bg-sea' : 'bg-brass'} />
              <span className="text-right font-mono text-xs">{hours(activity.hours)}</span>
              <span className="text-right font-mono text-xs">{moneyCompact(activity.cost)}</span>
              <span className="text-right font-mono text-xs">{share(metric.share(activity))}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-ink/55">No activity has a calculable {metric.label.toLowerCase()} with these filters.</p>
      )}
      <div className="flex flex-wrap gap-4 text-[11px] text-ink/55 mt-3">
        <span className="text-moss">Recruitment</span>
        <span className="text-sea">Training</span>
        <span className="text-brass">Deployment</span>
        {excluded ? <span>{excluded} external items have spend and no internal hours, so they are hidden when ranking by hours.</span> : null}
      </div>
    </Panel>
  )
}

function Lifecycle({ hiring }) {
  const lifecycleMax = Math.max(...hiring.lifecycle.map((stage) => stage.cost || 0), 1)
  return (
    <Panel title="Applicant to deployment" className="mt-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-ink/50">
              <th className="text-left font-medium pb-2 px-2">Stage</th>
              <th className="text-right font-medium pb-2 px-2">People entering</th>
              <th className="text-right font-medium pb-2 px-2">Conversion</th>
              <th className="text-left font-medium pb-2 px-2 w-48">Cost <SampleMark /></th>
            </tr>
          </thead>
          <tbody>
            {hiring.lifecycle.map((stage, index) => (
              <tr key={stage.key} className="border-t border-line/80 align-top">
                <td className="py-2 px-2">
                  <span className="text-ink/35 mr-1">{index ? '↓' : '●'}</span>
                  <span className="font-medium">{stage.label}</span>
                  {stage.origin ? (
                    <span className="ml-1.5">
                      <Badge tone={stage.origin}>{stage.origin}</Badge>
                    </span>
                  ) : null}
                </td>
                <td className="py-2 px-2 text-right font-mono">{dash(stage.people)}</td>
                <td className="py-2 px-2 text-right">
                  <span className="font-mono">{stage.conversion === null ? '–' : pct(stage.conversion)}</span>
                  <span className="block text-[11px] text-ink/50 leading-snug">{stage.conversion_note}</span>
                </td>
                <td className="py-2 px-2">
                  <span className="font-mono text-[13px]">{money(stage.cost)}</span>
                  <span className="block text-[11px] text-ink/50">
                    {money(stage.cost_per_outcome)} per {stage.outcome_label}
                  </span>
                  <Bar value={stage.cost} max={lifecycleMax} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ink/55 mt-3">
        Applicant through Accepted is the hiring sheet. Training and Deployment come from the roster, including people hired earlier, so conversion stops at that boundary.
      </p>
    </Panel>
  )
}

function Insight({ text }) {
  if (!text) return null
  return (
    <p className="mt-4 text-sm bg-card border border-line rounded-lg px-4 py-3">
      <span className="text-moss font-semibold">Insight. </span>
      {text}
    </p>
  )
}

const RATE_FIELDS = [
  ['hours_per_unit', 'Hours / unit'],
  ['hourly_cost_usd', '$ / hour'],
  ['unit_cost_usd', '$ / unit (external)'],
  ['weekly_capacity_units', 'Capacity / week'],
]

function RatesEditor({ rates, onSaved }) {
  const [draft, setDraft] = useState(() => rates)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!dirty) setDraft(rates)
  }, [rates, dirty])

  async function save() {
    setSaving(true)
    setMessage('')
    try {
      const response = await fetch('/api/economics/rates', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rates: draft }),
      })
      const json = await response.json()
      if (!response.ok) throw new Error(json.detail || 'Save failed')
      setDirty(false)
      setMessage('Saved. Metrics and recommendations now use these rates.')
      onSaved()
    } catch (err) {
      setMessage(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <p className="text-sm text-ink/70 mb-3">
        The workbook has no resource hours or costs. Each activity multiplies a workbook volume by these rates. Saving replaces the placeholders.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-ink/50">
              <th className="text-left font-medium pb-2 px-2">Activity</th>
              <th className="text-left font-medium pb-2 px-2">Per</th>
              <th className="text-left font-medium pb-2 px-2">Resource</th>
              {RATE_FIELDS.map(([key, label]) => (
                <th key={key} className="text-right font-medium pb-2 px-2">
                  {label}
                </th>
              ))}
              <th className="text-left font-medium pb-2 px-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {draft.map((rate, index) => (
              <tr key={rate.code} className="border-t border-line/80">
                <td className="py-1.5 px-2">
                  {rate.label}
                  <span className="block text-[11px] text-ink/50">
                    {rate.phase} · {rate.cost_type}
                  </span>
                </td>
                <td className="py-1.5 px-2 text-xs">{rate.driver_label}</td>
                <td className="py-1.5 px-2 text-xs">{dash(rate.resource_role)}</td>
                {RATE_FIELDS.map(([key]) => {
                  const applicable = key === 'unit_cost_usd' ? rate.cost_type === 'external' : rate.cost_type === 'internal'
                  return (
                    <td key={key} className="py-1.5 px-2 text-right">
                      {applicable ? (
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={rate[key] ?? ''}
                          onChange={(event) => {
                            const next = draft.slice()
                            next[index] = { ...rate, [key]: event.target.value }
                            setDraft(next)
                            setDirty(true)
                          }}
                          className="w-20 rounded border border-line bg-white px-1.5 py-1 text-sm font-mono text-right"
                        />
                      ) : (
                        <span className="text-ink/30">–</span>
                      )}
                    </td>
                  )
                })}
                <td className="py-1.5 px-2">{rate.is_placeholder ? <Badge tone="assumption">placeholder</Badge> : <Badge tone="ok">edited</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 mt-4">
        <button type="button" disabled={!dirty || saving} onClick={save} className="rounded-md bg-ink text-white text-sm px-3 py-2 disabled:opacity-50">
          {saving ? 'Saving…' : 'Save rates'}
        </button>
        {dirty ? (
          <button
            type="button"
            onClick={() => {
              setDirty(false)
              setDraft(rates)
            }}
            className="text-sm text-sea hover:underline"
          >
            Discard changes
          </button>
        ) : null}
        {message ? <span className="text-sm text-ink/70">{message}</span> : null}
      </div>
    </div>
  )
}
