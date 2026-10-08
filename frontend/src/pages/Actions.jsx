import { useState } from 'react'
import { useDashboard } from '../api'
import { FilterBar, toQuery, useFilters } from '../filters'
import { dash, dateLabel, moneyCompact } from '../format'
import { Badge, Coverage, PageHeader, Panel, SampleMark, SourceKey, State } from '../ui'

const VIEWS = [
  ['all', 'All'],
  ['high', 'High priority'],
  ['Recruitment', 'Recruitment'],
  ['Cohort', 'Cohort'],
  ['Deployment', 'Deployment'],
  ['Economics', 'Economics'],
]
const STATUS_VIEWS = [
  ['OPEN', 'Open'],
  ['ACCEPTED', 'Accepted'],
  ['DISMISSED', 'Dismissed'],
  ['', 'Any status'],
]
const DOT = { HIGH: 'bg-clay', MEDIUM: 'bg-brass', LOW: 'bg-sea' }
const COMPONENT_LABELS = { impact: 'Impact', urgency: 'Urgency', revenue_risk: 'Revenue risk', confidence: 'Confidence' }

function impactText(impact) {
  if (!impact || impact.value === null || impact.value === undefined) return null
  const value = moneyCompact(impact.value)
  if (impact.type === 'revenue') return `${impact.estimated ? '≈ ' : ''}${value}/month`
  return `${value} ${impact.period === 'period' ? 'in period' : impact.period}`
}

export default function Actions() {
  const [filters, setFilters, resetFilters] = useFilters()
  const { data, error, updatedAt, reload } = useDashboard(`/api/actions${toQuery(filters, ['phase'])}`)
  const [view, setView] = useState('high')
  const [statusView, setStatusView] = useState('OPEN')
  const [openId, setOpenId] = useState(null)
  const [busy, setBusy] = useState('')
  const [actionError, setActionError] = useState('')

  async function setStatus(id, status) {
    setBusy(id + status)
    setActionError('')
    try {
      const response = await fetch(`/api/actions/${encodeURIComponent(id)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      const json = await response.json()
      if (!response.ok) throw new Error(json.detail || 'Update failed')
      await reload()
    } catch (err) {
      setActionError(err.message || 'Update failed')
    } finally {
      setBusy('')
    }
  }

  return (
    <State data={data} error={error}>
      {data ? (
        <ActionsView
          data={data}
          updatedAt={updatedAt}
          error={error}
          filters={filters}
          setFilters={setFilters}
          resetFilters={resetFilters}
          view={view}
          setView={setView}
          statusView={statusView}
          setStatusView={setStatusView}
          openId={openId}
          setOpenId={setOpenId}
          setStatus={setStatus}
          busy={busy}
          actionError={actionError}
        />
      ) : null}
    </State>
  )
}

function ActionsView(props) {
  const { data, updatedAt, error, filters, setFilters, resetFilters, view, setView, statusView, setStatusView, openId, setOpenId } = props
  const recs = data.recommendations.filter((rec) => {
    if (statusView && rec.status !== statusView) return false
    if (view === 'high') return rec.priority === 'HIGH'
    if (view !== 'all') return rec.category === view
    return true
  })
  const open = data.recommendations.find((rec) => rec.id === openId)

  return (
    <div className="px-5 py-6 lg:px-8">
      <PageHeader
        kicker="Leadership action center"
        title="What should we do next?"
        lede="High-priority decisions first. Each card is one reason and one action. Evidence and the rule audit sit behind the card."
        asOf={dateLabel(data.as_of)}
        updatedAt={updatedAt}
      />
      <SourceKey />
      <FilterBar filters={filters} onChange={setFilters} onReset={resetFilters} options={data.options} showPhase={false} />
      {error ? <p className="text-sm text-clay mb-3">Last refresh failed: {error}</p> : null}
      {data.notes.map((note) => (
        <p key={note} className="text-xs text-brass mb-2">
          {note}
        </p>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex flex-wrap gap-1.5">
          {VIEWS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setView(id)}
              className={`rounded-full border px-3 py-1 text-sm ${view === id ? 'bg-ink text-white border-ink' : 'bg-card border-line text-ink/70 hover:text-ink'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="text-sm text-ink/70 flex items-center gap-2">
          Status
          <select className="bg-card border border-line rounded-md px-2 py-1 text-sm" value={statusView} onChange={(e) => setStatusView(e.target.value)}>
            {STATUS_VIEWS.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {props.actionError ? <p className="text-sm text-clay mb-2">{props.actionError}</p> : null}

      <p className="text-sm font-semibold mb-2">
        {recs.length} recommendation{recs.length === 1 ? '' : 's'} <span className="font-normal text-ink/55">· sorted by score</span>
      </p>
      <div className="space-y-3">
        {recs.map((rec) => (
          <RecCard key={rec.id} rec={rec} onOpen={() => setOpenId(rec.id)} />
        ))}
        {!recs.length ? (
          <Panel>
            <p className="text-sm text-ink/60">
              No recommendations match this view. {data.recommendations.length ? 'Try another category or status.' : 'No rule fired for the current filters.'}
            </p>
          </Panel>
        ) : null}
      </div>

      <details className="mt-6 bg-card border border-line rounded-lg">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">How these were chosen</summary>
        <div className="px-4 pb-4">
          <ul className="divide-y divide-line">
            {data.rules.map((rule) => (
              <li key={rule.rule} className="py-2.5 grid grid-cols-[3rem_minmax(0,14rem)_8rem_1fr] gap-3 items-start text-sm">
                <span className="font-mono text-xs text-ink/50">{rule.rule}</span>
                <span className="font-medium">{rule.name}</span>
                <span>
                  <Badge tone={rule.status}>{rule.status.replace('_', ' ')}</Badge>
                  {rule.count ? <span className="text-xs text-ink/50 ml-1">×{rule.count}</span> : null}
                </span>
                <span className="text-ink/70">{rule.detail}</span>
              </li>
            ))}
          </ul>
          <ScoringNote config={data.config} />
          <Coverage items={data.coverage} plain className="mt-4" />
        </div>
      </details>

      {open ? <Detail rec={open} onClose={() => setOpenId(null)} setStatus={props.setStatus} busy={props.busy} /> : null}
    </div>
  )
}

function ScoringNote({ config }) {
  const weights = Object.entries(config.score_weights)
    .map(([key, value]) => `${COMPONENT_LABELS[key]} ${Math.round(value * 100)}%`)
    .join(' · ')
  return (
    <p className="text-xs text-ink/55 mt-3 leading-relaxed">
      Score = {weights}, each component 0–100. HIGH ≥ {config.priority_high}, MEDIUM ≥ {config.priority_medium}. Confidence is the lowest of the data origins a rule used: workbook{' '}
      {config.confidence.workbook}, inferred {config.confidence.inferred}, assumption {config.confidence.assumption}, demo {config.confidence.demo}.
    </p>
  )
}

function RecCard({ rec, onOpen }) {
  return (
    <article className={`bg-card border rounded-lg px-4 py-3.5 ${rec.uses_sample ? 'border-dashed border-brass' : 'border-line'} ${rec.status === 'DISMISSED' ? 'opacity-60' : ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${DOT[rec.priority]}`} />
            <span className="font-mono text-xs text-ink/50">#{rec.rank}</span>
            <h3 className="font-semibold uppercase tracking-wide text-[15px]">{rec.title}</h3>
            <Badge tone={rec.priority}>{rec.priority}</Badge>
            {rec.status !== 'OPEN' ? <Badge tone={rec.status}>{rec.status}</Badge> : null}
            {rec.uses_sample ? <SampleMark /> : null}
          </div>
          <p className="text-sm mt-2">{rec.summary}</p>
          <p className="text-sm mt-1.5">
            <span className="text-ink/55">Do this: </span>
            {rec.recommended_action}
          </p>
        </div>
        <button type="button" onClick={onOpen} className="rounded-md border border-ink text-ink text-xs font-semibold tracking-wider px-3 py-1.5 hover:bg-ink hover:text-white shrink-0">
          VIEW EVIDENCE
        </button>
      </div>
    </article>
  )
}

function Detail({ rec, onClose, setStatus, busy }) {
  const impact = impactText(rec.impact)
  const breakdown = rec.score_breakdown
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <aside className="relative w-full max-w-2xl h-full overflow-y-auto bg-paper border-l border-line shadow-xl">
        <div className="sticky top-0 bg-paper border-b border-line px-5 py-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-moss font-semibold">
              {rec.category} · {rec.rule_code} {rec.rule_name}
            </p>
            <h2 className="text-lg font-semibold mt-0.5">{rec.title}</h2>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm">
              <Badge tone={rec.priority}>{rec.priority}</Badge>
              <span>
                Score <span className="font-mono font-semibold">{rec.score}</span>
              </span>
              <span>
                Confidence <span className="font-mono">{rec.confidence}%</span>
              </span>
              <Badge tone={rec.status}>{rec.status}</Badge>
            </div>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-sea hover:underline">
            Close
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <Panel title="Why are we saying this?">
            <p className="text-sm mb-3">{rec.summary}</p>
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 text-sm">
              {rec.metrics.map((m) => (
                <div key={m.label} className="contents">
                  <dt className="text-ink/65">{m.label}</dt>
                  <dd className="font-mono text-right">{String(dash(m.value))}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel title="Triggered by">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-ink/50">
                  <th className="text-left font-medium pb-2 pr-2">Metric</th>
                  <th className="text-right font-medium pb-2 px-2">Current value</th>
                  <th className="text-right font-medium pb-2 px-2">Threshold</th>
                  <th className="text-left font-medium pb-2 pl-2">Source dataset</th>
                </tr>
              </thead>
              <tbody>
                {rec.triggered_by.map((t) => (
                  <tr key={t.metric} className="border-t border-line/80 align-top">
                    <td className="py-1.5 pr-2">{t.metric}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{String(t.value)}</td>
                    <td className="py-1.5 px-2 text-right font-mono whitespace-nowrap">
                      {t.comparator} {String(t.threshold)}
                    </td>
                    <td className="py-1.5 pl-2 text-xs text-ink/70">{t.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="Business impact">
            <ol className="space-y-1 text-sm">
              {rec.impact_chain.map((step, index) => (
                <li key={step}>
                  {index ? <span className="block text-ink/35 pl-3">↓</span> : null}
                  <span className="inline-block border border-line rounded px-2 py-1 bg-card">{step}</span>
                </li>
              ))}
            </ol>
            <p className="text-sm mt-3">
              {impact ? (
                <>
                  <span className="text-ink/60">Estimated impact: </span>
                  <span className="font-mono font-semibold">{impact}</span>
                </>
              ) : (
                <span className="text-clay">Revenue impact cannot currently be calculated from available data.</span>
              )}
            </p>
            {rec.impact.note && !rec.impact.note.startsWith('Revenue impact cannot currently be calculated from available data') ? (
              <p className="text-xs text-ink/55 mt-1">{rec.impact.note}</p>
            ) : null}
          </Panel>

          <Panel title="Recommended action">
            <p className="text-sm font-medium">{rec.recommended_action}</p>
            <p className="text-sm mt-2">
              <span className="text-ink/60">Expected effect: </span>
              {rec.expected_effect}
            </p>
            <p className="text-sm mt-2 text-ink/70">
              <span className="text-ink/60">Why it matters: </span>
              {rec.why_it_matters}
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              {rec.status !== 'ACCEPTED' ? (
                <button
                  type="button"
                  disabled={!!busy}
                  onClick={() => setStatus(rec.id, 'ACCEPTED')}
                  className="rounded-md bg-moss text-white text-sm font-semibold px-3 py-2 disabled:opacity-50"
                >
                  ACCEPT ACTION
                </button>
              ) : null}
              {rec.status !== 'DISMISSED' ? (
                <button
                  type="button"
                  disabled={!!busy}
                  onClick={() => setStatus(rec.id, 'DISMISSED')}
                  className="rounded-md border border-line bg-card text-sm font-semibold px-3 py-2 disabled:opacity-50"
                >
                  DISMISS
                </button>
              ) : null}
              {rec.status !== 'OPEN' ? (
                <button type="button" disabled={!!busy} onClick={() => setStatus(rec.id, 'OPEN')} className="text-sm text-sea hover:underline px-2">
                  Reopen
                </button>
              ) : null}
            </div>
            <p className="text-xs text-ink/50 mt-2">Prototype: status is saved to recommendation_status; no workflow is triggered.</p>
          </Panel>

          <Panel title="Evidence">
            <ul className="space-y-1 text-sm">
              {rec.evidence.map((line) => (
                <li key={line}>· {line}</li>
              ))}
            </ul>
          </Panel>

          {rec.supporting_metrics.length ? (
            <Panel title="Supporting metrics">
              <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 text-sm">
                {rec.supporting_metrics.map((m) => (
                  <div key={m.label} className="contents">
                    <dt className="text-ink/65">{m.label}</dt>
                    <dd className="font-mono text-right">{String(dash(m.value))}</dd>
                  </div>
                ))}
              </dl>
            </Panel>
          ) : null}

          <Panel title={`Why score ${rec.score}?`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-ink/50">
                  <th className="text-left font-medium pb-2 pr-2">Component</th>
                  <th className="text-right font-medium pb-2 px-2">Weight</th>
                  <th className="text-right font-medium pb-2 px-2">Value</th>
                  <th className="text-right font-medium pb-2 px-2">Points</th>
                  <th className="text-left font-medium pb-2 pl-2">Basis</th>
                </tr>
              </thead>
              <tbody>
                {breakdown.components.map((c) => (
                  <tr key={c.key} className="border-t border-line/80 align-top">
                    <td className="py-1.5 pr-2">{COMPONENT_LABELS[c.key]}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{Math.round(c.weight * 100)}%</td>
                    <td className="py-1.5 px-2 text-right font-mono">{c.value}</td>
                    <td className="py-1.5 px-2 text-right font-mono">{c.contribution}</td>
                    <td className="py-1.5 pl-2 text-xs text-ink/65">{c.basis}</td>
                  </tr>
                ))}
                <tr className="border-t border-ink/30 font-semibold">
                  <td className="py-1.5 pr-2">Total</td>
                  <td />
                  <td />
                  <td className="py-1.5 px-2 text-right font-mono">{rec.score}</td>
                  <td className="py-1.5 pl-2 text-xs text-ink/65 font-normal">
                    {rec.priority}: HIGH ≥ {breakdown.thresholds.high}, MEDIUM ≥ {breakdown.thresholds.medium}
                  </td>
                </tr>
              </tbody>
            </table>
          </Panel>

          <Panel title="Data freshness">
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
              <dt className="text-ink/65">Hiring snapshot (week ending)</dt>
              <dd className="font-mono text-right">{dateLabel(rec.data_freshness.hiring_week)}</dd>
              <dt className="text-ink/65">Latest scored training week</dt>
              <dd className="font-mono text-right">{dash(rec.data_freshness.training_week)}</dd>
              <dt className="text-ink/65">Roster as of</dt>
              <dd className="font-mono text-right">{dateLabel(rec.data_freshness.roster_as_of)}</dd>
              <dt className="text-ink/65">Recommendation first seen</dt>
              <dd className="font-mono text-right">{rec.created_at.replace('T', ' ')}</dd>
              <dt className="text-ink/65">Last calculated</dt>
              <dd className="font-mono text-right">{rec.data_freshness.generated_at.replace('T', ' ')}</dd>
              <dt className="text-ink/65">Source tables</dt>
              <dd className="font-mono text-right">{rec.data_sources.join(', ')}</dd>
            </dl>
          </Panel>
        </div>
      </aside>
    </div>
  )
}
