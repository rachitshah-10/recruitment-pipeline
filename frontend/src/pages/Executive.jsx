import { dateLabel, dash, moneyCompact, pct } from '../format'
import { useDashboard } from '../api'
import { Callout, Cell, Kpi, PageHeader, Panel, State } from '../ui'

const ROLE_DOT = {
  Associate: 'bg-moss',
  FDE: 'bg-sea',
  Senior: 'bg-brass',
}

export default function Executive() {
  const { data, error, updatedAt } = useDashboard('/api/executive')

  return (
    <State data={data} error={error}>
      {data ? <ExecutiveView data={data} updatedAt={updatedAt} /> : null}
    </State>
  )
}

function ExecutiveView({ data, updatedAt }) {
  const kpis = data.kpis
  const maxRevenue = Math.max(...data.clients.map((client) => client.monthly_revenue), 1)

  return (
    <div className="px-5 py-6 lg:px-8">
      <PageHeader
        kicker="Executive"
        title="Pipeline, academy, and deployment"
        lede="Hiring counts are the latest week HR filed. Revenue and the roster are live as of today."
        asOf={dateLabel(data.as_of)}
        updatedAt={updatedAt}
      />

      <div className="grid grid-cols-2 xl:grid-cols-6 gap-3">
        <Kpi
          label="Offers accepted"
          value={dash(kpis.offers_accepted)}
          detail={`${dash(kpis.in_cto)} in the CTO round`}
        />
        <Kpi
          label="Slots next week"
          value={dash(kpis.slots_needed)}
          detail={data.week_ending ? `Week ending ${dateLabel(data.week_ending)}` : 'No hiring week on file'}
        />
        <Kpi
          label="Academy average"
          value={pct(kpis.training_average)}
          detail={kpis.training_week ? `Week ${kpis.training_week} · ${dash(kpis.active_students)} students` : 'No scores yet'}
        />
        <Kpi
          label="At clients"
          value={`${dash(kpis.active_at_client)} / ${dash(kpis.headcount)}`}
          detail={`Utilization ${pct(kpis.utilization)} of joined FDEs`}
        />
        <Kpi
          label="Monthly revenue"
          value={moneyCompact(kpis.monthly_revenue)}
          detail={`${moneyCompact(kpis.annualized_revenue)} annualised`}
        />
        <Kpi
          label="On bench"
          value={dash(kpis.on_bench)}
          detail={`${dash(kpis.contracts_ending_soon)} contracts ending within 60 days`}
        />
      </div>

      <div className="grid xl:grid-cols-5 gap-4 mt-4">
        <Panel title="Hiring by role" className="xl:col-span-3" extra={<span className="text-xs text-ink/50">Cohort 1 + Cohort 2</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-ink/50">
                  <th className="text-left font-medium pb-2">Stage</th>
                  {Object.entries(ROLE_DOT).map(([label, color]) => (
                    <th key={label} className="text-right font-medium pb-2 px-2">
                      <span className="inline-flex items-center gap-1.5 justify-end">
                        <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
                        {label}
                      </span>
                    </th>
                  ))}
                  <th className="text-right font-medium pb-2 px-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.funnel.map((stage) => (
                  <tr key={stage.label} className={stage.emphasis ? 'bg-[#fbf6ee]' : 'border-t border-line/80'}>
                    <td className={`py-2 pr-3 ${stage.cumulative ? 'text-ink/55' : ''}`}>
                      {stage.label}
                      {stage.cumulative ? <span className="ml-1.5 text-[10px] uppercase tracking-wide text-ink/35">cuml</span> : null}
                    </td>
                    <Cell value={stage.associate} />
                    <Cell value={stage.fde} />
                    <Cell value={stage.senior} />
                    <Cell value={stage.total} strong />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-ink/50 mt-3">A dash means HR has not reported that number. In pipeline adds every pending round, including offers waiting on a decision.</p>
        </Panel>

        <div className="xl:col-span-2 flex flex-col gap-4">
          <Panel title="Needs a decision">
            <div className="flex flex-col gap-2.5">
              {data.alerts.length ? (
                data.alerts.map((alert) => (
                  <Callout key={`${alert.title}-${alert.body}`} tone={alert.tone} title={alert.title}>
                    {alert.body}
                  </Callout>
                ))
              ) : (
                <p className="text-sm text-ink/60">Nothing flagged on this snapshot.</p>
              )}
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <Panel title="Client revenue" extra={<span className="text-xs text-ink/50">Active contracts</span>}>
          <div className="flex flex-col gap-3">
            {data.clients.map((client) => (
              <div key={client.client} className="grid grid-cols-[6.5rem_1fr_auto] gap-3 items-center text-sm">
                <span className="truncate">{client.client}</span>
                <div className="h-2 bg-line rounded-full overflow-hidden">
                  <div
                    className="h-full bg-moss rounded-full"
                    style={{ width: `${(client.monthly_revenue / maxRevenue) * 100}%` }}
                  />
                </div>
                <span className="font-mono text-xs text-ink/80 whitespace-nowrap">
                  {client.active_fdes} · {moneyCompact(client.monthly_revenue)}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Where people are"
          extra={<span className="text-xs text-ink/50">{data.available_now} available now · {data.available_later} later</span>}
        >
          <div className="flex flex-col gap-3">
            {data.locations.map((location) => (
              <div key={location.location}>
                <div className="flex justify-between text-sm mb-1">
                  <span>{location.location}</span>
                  <span className="font-mono text-xs text-ink/60">{location.total}</span>
                </div>
                <div className="h-2.5 flex rounded-full overflow-hidden bg-line">
                  <div className="bg-moss" style={{ width: `${(location.now / location.total) * 100}%` }} />
                  <div className="bg-sea/35" style={{ width: `${(location.later / location.total) * 100}%` }} />
                </div>
                <p className="text-[11px] text-ink/50 mt-1">
                  {location.now} now · {location.later} in training or not started
                </p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}
