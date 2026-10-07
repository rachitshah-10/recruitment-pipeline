import { useMemo, useState } from 'react'
import { dateLabel, dash, endsIn, money, moneyCompact, pct, rate } from '../format'
import { useDashboard } from '../api'
import { Checks, Kpi, PageHeader, Panel, State, StatusPill } from '../ui'

const FILTERS = [
  { id: 'All', match: () => true },
  { id: 'Active', match: (person) => person.bucket === 'Active at client' },
  { id: 'Bench', match: (person) => person.bucket === 'On bench' },
  { id: 'Training', match: (person) => person.bucket === 'In training' },
  { id: 'Yet to join', match: (person) => person.bucket === 'Yet to join' },
  { id: 'Ending soon', match: (person) => person.ending_soon },
]

export default function Deployment() {
  const { data, error, updatedAt } = useDashboard('/api/deployment')
  return (
    <State data={data} error={error}>
      {data ? <DeploymentView data={data} updatedAt={updatedAt} /> : null}
    </State>
  )
}

function DeploymentView({ data, updatedAt }) {
  const [filter, setFilter] = useState('All')
  const [client, setClient] = useState('All')
  const [query, setQuery] = useState('')
  const clients = useMemo(
    () => Array.from(new Set(data.roster.map((person) => person.client).filter(Boolean))).sort(),
    [data.roster],
  )
  const peak = Math.max(...data.joiners_by_month.map((month) => month.joiners), 1)
  const visible = data.roster.filter((person) => {
    const rule = FILTERS.find((item) => item.id === filter)
    if (rule && !rule.match(person)) return false
    if (client === 'Unassigned' && person.client) return false
    if (client !== 'All' && client !== 'Unassigned' && person.client !== client) return false
    if (query) {
      const haystack = `${person.name} ${person.location} ${person.client || ''} ${person.career_stage}`.toLowerCase()
      if (!haystack.includes(query.trim().toLowerCase())) return false
    }
    return true
  })

  return (
    <div className="px-5 py-6 lg:px-8">
      <PageHeader
        kicker="Deployment"
        title="Roster, bench, and revenue"
        lede="A contract counts toward revenue when it is active today: rate × hours/week × 4. Utilization is active FDEs divided by joined FDEs who are not trainees."
        asOf={dateLabel(data.as_of)}
        updatedAt={updatedAt}
      />

      <div className="grid grid-cols-2 xl:grid-cols-6 gap-3">
        <Kpi label="Headcount" value={data.headcount} detail={`${data.joined} joined · ${data.yet_to_join} yet to join`} />
        <Kpi label="Active at client" value={data.active_at_client} detail={`${pct(data.utilization)} utilization`} />
        <Kpi label="On bench" value={data.on_bench} detail={`${data.in_training} still in the academy`} />
        <Kpi label="Monthly revenue" value={moneyCompact(data.monthly_revenue)} detail={`${moneyCompact(data.annualized_revenue)} annualised`} />
        <Kpi label="Average rate" value={rate(data.avg_rate)} detail="USD per hour, active contracts" />
        <Kpi
          label="Ending in 60 days"
          value={data.contracts_ending_soon}
          detail={`${money(data.revenue_at_risk)} of the run-rate`}
        />
      </div>

      <div className="grid lg:grid-cols-5 gap-4 mt-4">
        <Panel title="Clients" className="lg:col-span-3">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-ink/50">
                  <th className="text-left font-medium pb-2">Client</th>
                  <th className="text-right font-medium pb-2">FDEs</th>
                  <th className="text-right font-medium pb-2">Monthly</th>
                  <th className="text-right font-medium pb-2">Avg rate</th>
                </tr>
              </thead>
              <tbody>
                {data.clients.map((row) => (
                  <tr key={row.client} className="border-t border-line/80">
                    <td className="py-2">{row.client}</td>
                    <td className="py-2 text-right font-mono">{row.active_fdes}</td>
                    <td className="py-2 text-right font-mono">{money(row.monthly_revenue)}</td>
                    <td className="py-2 text-right font-mono">{rate(row.avg_rate)}</td>
                  </tr>
                ))}
                <tr className="border-t border-line font-semibold">
                  <td className="py-2">Total active</td>
                  <td className="py-2 text-right font-mono">{data.active_at_client}</td>
                  <td className="py-2 text-right font-mono">{money(data.monthly_revenue)}</td>
                  <td className="py-2 text-right font-mono">{rate(data.avg_rate)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Joiners by month" className="lg:col-span-2">
          <div className="flex items-end gap-2 h-36">
            {data.joiners_by_month.map((month) => (
              <div key={month.month} className="flex-1 flex flex-col items-center justify-end h-full min-w-0">
                <span className="text-[10px] font-mono text-ink/70 mb-1">{month.joiners || ''}</span>
                <div
                  className={`w-full rounded-sm ${month.joiners ? 'bg-sea' : 'bg-line'}`}
                  style={{ height: `${Math.max((month.joiners / peak) * 100, month.joiners ? 10 : 3)}%` }}
                />
                <span className="text-[10px] text-ink/50 mt-1.5 text-center leading-tight">
                  {month.month.replace(' 20', " '")}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Roster" className="mt-4" extra={<span className="text-xs text-ink/50">{visible.length} shown</span>}>
        <div className="flex flex-wrap gap-2 mb-3">
          {FILTERS.map((item) => {
            const count = data.roster.filter(item.match).length
            const active = filter === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
                className={`rounded-full border px-3 py-1 text-xs font-medium ${
                  active ? 'bg-ink text-white border-ink' : 'bg-card text-ink/75 border-line hover:border-ink/30'
                }`}
              >
                {item.id}
                <span className={`ml-1.5 font-mono ${active ? 'text-white/70' : 'text-ink/40'}`}>{count}</span>
              </button>
            )
          })}
        </div>
        <div className="flex flex-wrap gap-2 mb-4">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search name, client, location"
            className="bg-paper border border-line rounded-md px-3 py-1.5 text-sm min-w-[16rem] flex-1"
          />
          <select
            value={client}
            onChange={(event) => setClient(event.target.value)}
            className="bg-paper border border-line rounded-md px-2 py-1.5 text-sm"
          >
            <option>All</option>
            <option>Unassigned</option>
            {clients.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[880px]">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-ink/50">
                <th className="text-left font-medium pb-2">Name</th>
                <th className="text-left font-medium pb-2">Location</th>
                <th className="text-left font-medium pb-2">Stage</th>
                <th className="text-left font-medium pb-2">Status</th>
                <th className="text-left font-medium pb-2">Client</th>
                <th className="text-left font-medium pb-2">Contract end</th>
                <th className="text-right font-medium pb-2">Rate</th>
                <th className="text-right font-medium pb-2">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((person) => (
                <tr key={person.id} className="border-t border-line/80 align-top">
                  <td className="py-2.5 pr-3">
                    <div className="font-medium">{person.name}</div>
                    {person.issues.map((issue) => (
                      <div key={issue} className="text-[11px] text-clay mt-0.5">{issue}</div>
                    ))}
                    <div className="text-[11px] text-ink/45 mt-0.5">
                      {person.source || 'Source unreported'} · started {dateLabel(person.start_date)}
                    </div>
                  </td>
                  <td className="py-2.5 pr-3">{person.location}</td>
                  <td className="py-2.5 pr-3">{person.career_stage}</td>
                  <td className="py-2.5 pr-3">
                    <StatusPill status={person.bucket} />
                    {person.ending_soon ? (
                      <div className="text-[11px] text-clay mt-1">{endsIn(person.days_to_contract_end)}</div>
                    ) : null}
                  </td>
                  <td className="py-2.5 pr-3">{person.client || '–'}</td>
                  <td className="py-2.5 pr-3">{dateLabel(person.client_end)}</td>
                  <td className="py-2.5 text-right font-mono">{rate(person.hourly_rate)}</td>
                  <td className="py-2.5 text-right font-mono">{money(person.monthly_revenue)}</td>
                </tr>
              ))}
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-sm text-ink/50">
                    No one matches this filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Data checks" className="mt-4">
        <Checks checks={data.checks} />
      </Panel>
    </div>
  )
}
