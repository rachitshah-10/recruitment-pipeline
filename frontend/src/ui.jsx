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

export function Kpi({ label, value, detail }) {
  return (
    <section className="bg-card border border-line rounded-lg px-4 py-3 min-w-0">
      <p className="text-[11px] uppercase tracking-wider text-ink/55 font-medium leading-snug">{label}</p>
      <p className="mt-2 text-[1.6rem] leading-none font-mono tracking-tight">{value}</p>
      {detail ? <p className="mt-2 text-xs text-ink/60 leading-snug">{detail}</p> : null}
    </section>
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

export function StatusPill({ status }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${STATUS[status] || 'bg-stone-100 border-line'}`}>
      {status}
    </span>
  )
}
