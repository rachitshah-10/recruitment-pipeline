import { useState } from 'react'
import { dash, formatWhen } from './format'

export function PageHeader({ kicker, title, lede, asOf, updatedAt }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div className="max-w-3xl">
        <p className="text-[11px] uppercase tracking-[0.16em] text-moss font-semibold">{kicker}</p>
        <h1 className="text-2xl font-semibold tracking-tight mt-1">{title}</h1>
        {lede ? <p className="text-sm text-ink/70 mt-1.5 leading-relaxed">{lede}</p> : null}
      </div>
      <div className="text-xs text-ink/60 text-right">
        {asOf ? <p>As of {asOf}</p> : null}
        <p className="flex items-center justify-end gap-1.5 mt-1">
          <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-moss" />
          {updatedAt ? `Updated ${formatWhen(updatedAt)}` : 'Connecting'}
        </p>
      </div>
    </header>
  )
}

export function Kpi({ label, value, detail, sample = false }) {
  return (
    <section className={`bg-card border rounded-lg px-4 py-3 min-w-0 ${sample ? 'border-dashed border-brass bg-[#fbf6ec]' : 'border-line'}`}>
      <p className="text-[11px] uppercase tracking-wider text-ink/55 font-medium leading-snug flex items-center gap-1.5">
        {label}
        {sample ? <SampleMark /> : null}
      </p>
      <p className="mt-2 text-[1.6rem] leading-none font-mono tracking-tight">{value}</p>
      {detail ? <p className="mt-2 text-xs text-ink/60 leading-snug">{detail}</p> : null}
    </section>
  )
}

export function SampleMark() {
  return (
    <span
      title="Built from sample rates or demo demand that are not in the Excel workbook"
      className="normal-case tracking-normal inline-flex items-center rounded border border-dashed border-brass bg-[#fbf6ec] px-1.5 py-px text-[10px] font-semibold text-brass"
    >
      Sample
    </span>
  )
}

export function SourceKey() {
  return (
    <div className="grid md:grid-cols-2 gap-3 mb-4">
      <div className="rounded-lg border border-moss/30 bg-[#f2f8f6] px-3 py-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-moss">From the Excel workbook</p>
        <p className="text-xs text-ink/75 mt-1 leading-snug">
          Hiring counts by week, academy scores, and the people roster: names, location, stage, client, dates, and billing rate.
        </p>
      </div>
      <div className="rounded-lg border border-dashed border-brass bg-[#fbf6ec] px-3 py-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-brass flex items-center gap-1.5">
          Added for this prototype <SampleMark />
        </p>
        <p className="text-xs text-ink/75 mt-1 leading-snug">
          Activity hours, hourly and unit costs, weekly interviewer capacity, and four open-demand rows. Numbers that depend on them are marked Sample.
        </p>
      </div>
    </div>
  )
}

export function Panel({ title, extra, children, className = '' }) {
  return (
    <section className={`bg-card border border-line rounded-lg ${className}`}>
      {title ? (
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-line">
          <h2 className="text-sm font-semibold">{title}</h2>
          {extra}
        </div>
      ) : null}
      <div className="p-4">{children}</div>
    </section>
  )
}

const CALLOUT = {
  warning: 'bg-[#fbf6ee] border-brass/30',
  danger: 'bg-[#fdf4f3] border-clay/30',
  info: 'bg-[#f3f7fb] border-sea/20',
  good: 'bg-[#f2f8f6] border-moss/25',
}

export function Callout({ tone = 'info', title, children }) {
  return (
    <article className={`border rounded-lg px-3.5 py-3 ${CALLOUT[tone] || CALLOUT.info}`}>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-sm text-ink/75 mt-1 leading-snug">{children}</p>
    </article>
  )
}

export function State({ error, data, children }) {
  if (!data && error) {
    return (
      <div className="px-5 py-10 lg:px-8">
        <p className="font-semibold">The operations API is not responding.</p>
        <p className="text-sm text-ink/70 mt-1">{error}. Start the backend on port 8000 and refresh.</p>
      </div>
    )
  }
  if (!data) {
    return <div className="px-5 py-10 lg:px-8 text-sm text-ink/60">Loading operations data…</div>
  }
  return children
}

export function Cell({ value, strong = false }) {
  const empty = value === null || value === undefined
  return (
    <td className={`py-2 px-2 text-right font-mono text-[13px] ${strong ? 'font-semibold' : ''} ${empty ? 'text-ink/30' : ''}`}>
      {dash(value)}
    </td>
  )
}

export function Checks({ checks }) {
  return (
    <ul className="divide-y divide-line">
      {checks.map((check) => (
        <li key={check.label} className="flex items-start gap-3 py-2.5 text-sm">
          <span className={`font-mono text-xs mt-0.5 w-5 shrink-0 ${check.count ? 'text-clay font-semibold' : 'text-moss'}`}>
            {check.count}
          </span>
          <span className="text-ink/80">{check.label}</span>
        </li>
      ))}
    </ul>
  )
}

const STATUS = {
  'Active at client': 'bg-emerald-50 text-moss border-moss/20',
  'On bench': 'bg-amber-50 text-brass border-brass/30',
  'In training': 'bg-sky-50 text-sea border-sea/20',
  'Yet to join': 'bg-stone-100 text-ink/70 border-line',
  'Client starting soon': 'bg-indigo-50 text-indigo-800 border-indigo-200',
  'Contract ended': 'bg-red-50 text-clay border-clay/20',
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-line mb-4">
      {tabs.map(([id, label]) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`px-3 py-2 text-sm -mb-px border-b-2 ${
            active === id ? 'border-moss text-ink font-semibold' : 'border-transparent text-ink/60 hover:text-ink'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

const BADGE = {
  HIGH: 'bg-[#fdf4f3] text-clay border-clay/30',
  MEDIUM: 'bg-[#fbf6ee] text-brass border-brass/30',
  LOW: 'bg-[#f3f7fb] text-sea border-sea/20',
  OPEN: 'bg-stone-100 text-ink/70 border-line',
  ACCEPTED: 'bg-[#f2f8f6] text-moss border-moss/25',
  DISMISSED: 'bg-stone-100 text-ink/45 border-line line-through',
  ok: 'bg-[#f2f8f6] text-moss border-moss/25',
  partial: 'bg-[#fbf6ee] text-brass border-brass/30',
  assumption: 'bg-[#fbf6ee] text-brass border-brass/30',
  demo: 'bg-indigo-50 text-indigo-800 border-indigo-200',
  missing: 'bg-[#fdf4f3] text-clay border-clay/30',
  workbook: 'bg-[#f2f8f6] text-moss border-moss/25',
  inferred: 'bg-[#f3f7fb] text-sea border-sea/20',
  triggered: 'bg-[#fdf4f3] text-clay border-clay/30',
  not_triggered: 'bg-[#f2f8f6] text-moss border-moss/25',
  insufficient_data: 'bg-stone-100 text-ink/60 border-line',
}

export function Badge({ tone, children, title }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${BADGE[tone] || BADGE.OPEN}`}
    >
      {children ?? tone}
    </span>
  )
}

const COVERAGE_LABEL = { ok: '✓', partial: 'Partial', assumption: 'Assumption', demo: 'Demo data', missing: 'Missing' }

export function Coverage({ items, className = '', plain = false }) {
  if (!items?.length) return null
  const list = (
    <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
      {items.map((item) => (
        <li key={item.label} className="flex items-start justify-between gap-3 text-sm">
          <span>
            {item.label}
            <span className="block text-xs text-ink/55 leading-snug">{item.detail}</span>
          </span>
          <Badge tone={item.status}>{COVERAGE_LABEL[item.status] || item.status}</Badge>
        </li>
      ))}
    </ul>
  )
  if (plain) return <div className={className}>{list}</div>
  return (
    <Panel title="Data coverage" className={className} extra={<span className="text-xs text-ink/50">Missing data is never shown as zero</span>}>
      {list}
    </Panel>
  )
}

export function Bar({ value, max, tone = 'bg-moss' }) {
  const width = max ? Math.max(0, Math.min(100, ((value || 0) / max) * 100)) : 0
  return (
    <div className="h-2 rounded-full bg-line/80 overflow-hidden">
      <div className={`h-full ${tone}`} style={{ width: `${width}%` }} />
    </div>
  )
}

export function SortableTable({ columns, rows, initialSort, rowKey, onRowClick, selectedKey, empty = 'No rows.' }) {
  const [sort, setSort] = useState(initialSort || { key: columns[0].key, dir: 'desc' })
  const column = columns.find((col) => col.key === sort.key) || columns[0]
  const sorted = [...rows].sort((a, b) => {
    const get = column.sortValue || ((row) => row[column.key])
    const av = get(a)
    const bv = get(b)
    if (av === bv) return 0
    if (av === null || av === undefined) return 1
    if (bv === null || bv === undefined) return -1
    const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv
    return sort.dir === 'asc' ? cmp : -cmp
  })
  if (!rows.length) return <p className="text-sm text-ink/55">{empty}</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wider text-ink/50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`font-medium pb-2 px-2 select-none ${col.sortable === false ? '' : 'cursor-pointer hover:text-ink'} ${
                  col.align === 'right' ? 'text-right' : 'text-left'
                }`}
                onClick={() => {
                  if (col.sortable === false) return
                  setSort((current) => ({ key: col.key, dir: current.key === col.key && current.dir === 'desc' ? 'asc' : 'desc' }))
                }}
              >
                {col.label}
                {col.sample ? <span className="ml-1"><SampleMark /></span> : null}
                {sort.key === col.key ? (sort.dir === 'desc' ? ' ↓' : ' ↑') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, index) => {
            const key = rowKey ? rowKey(row) : index
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-t border-line/80 ${onRowClick ? 'cursor-pointer hover:bg-paper/60' : ''} ${
                  selectedKey !== undefined && selectedKey === key ? 'bg-[#f3f7fb]' : ''
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`py-2 px-2 align-top ${col.align === 'right' ? 'text-right font-mono text-[13px]' : ''}`}
                  >
                    {col.render ? col.render(row) : dash(row[col.key])}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function StatusPill({ status }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${STATUS[status] || 'bg-stone-100 border-line'}`}>
      {status}
    </span>
  )
}
