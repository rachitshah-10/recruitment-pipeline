import { dateLabel, dash, pct, points } from '../format'
import { useDashboard } from '../api'
import { Checks, Kpi, PageHeader, Panel, State, StatusPill } from '../ui'

export default function Cohort() {
  const { data, error, updatedAt } = useDashboard('/api/cohort')
  return (
    <State data={data} error={error}>
      {data ? <CohortView data={data} updatedAt={updatedAt} /> : null}
    </State>
  )
}

function CohortView({ data, updatedAt }) {
  const latest = data.latest
  const summary = data.trainee_summary
  const sameStart = summary.start_dates.length === 1 ? summary.start_dates[0] : null
  const samePlace = summary.locations.length === 1 ? summary.locations[0] : null
  const sameSource = summary.sources.length === 1 ? summary.sources[0] : null

  return (
    <div className="px-5 py-6 lg:px-8">
      <PageHeader
        kicker="Cohort health"
        title="Academy scores and the current batch"
        lede="Weekly scores come from the trainers' sheet. The names are trainees on the roster, which is the batch that has already joined."
        asOf={dateLabel(data.as_of)}
        updatedAt={updatedAt}
      />

      <div className="grid grid-cols-2 xl:grid-cols-6 gap-3">
        <Kpi label="Latest week" value={latest ? `Week ${latest.week}` : '–'} detail={latest ? 'Scores filed' : 'No scores yet'} />
        <Kpi label="Overall" value={pct(latest?.overall)} detail={`Average so far ${pct(data.average_overall)}`} />
        <Kpi label="Hands-on" value={pct(latest?.hands_on)} />
        <Kpi label="Proctored" value={pct(latest?.proctored)} />
        <Kpi label="Active students" value={dash(latest?.active_students)} detail={`${dash(data.students_vs_first_week)} vs first reported week`} />
        <Kpi
          label="Vs previous week"
          value={points(data.change_vs_previous)}
          detail={data.previous_week ? `Against week ${data.previous_week}` : 'No earlier week on file'}
        />
      </div>

      <div className="grid lg:grid-cols-5 gap-4 mt-4">
        <Panel
          title="Overall by week"
          className="lg:col-span-3"
          extra={<span className="text-xs text-ink/50">{data.weeks_reported} {data.weeks_reported === 1 ? 'week' : 'weeks'} reported</span>}
        >
          {latest?.topic ? <p className="text-sm text-ink/75 mb-4">{latest.topic}</p> : null}
          <div className="flex items-end gap-1.5 h-44">
            {data.weeks.map((week) => (
              <div key={week.week} className="flex-1 flex flex-col items-center justify-end h-full min-w-0">
                <span className="text-[10px] font-mono text-ink/70 mb-1">
                  {week.overall != null ? pct(week.overall) : ''}
                </span>
                <div
                  className={`w-full rounded-sm ${week.reported ? 'bg-moss' : 'bg-line'}`}
                  style={{ height: week.overall != null ? `${Math.max(week.overall * 100, 8)}%` : '4px' }}
                />
                <span className="text-[10px] text-ink/50 mt-1.5">W{week.week}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-ink/50 mt-3">
            Best {data.best_week ? `week ${data.best_week.week} (${pct(data.best_week.overall)})` : '–'}
            {' · '}
            Lowest {data.lowest_week ? `week ${data.lowest_week.week} (${pct(data.lowest_week.overall)})` : '–'}
          </p>
        </Panel>

        <Panel title="This batch" className="lg:col-span-2">
          <p className="text-3xl font-mono tracking-tight">{summary.count}</p>
          <p className="text-sm text-ink/70 mt-1">named trainees on the roster</p>
          <ul className="mt-4 text-sm flex flex-col gap-2 text-ink/80">
            <li>{samePlace ? `All based in ${samePlace.name}` : summary.locations.map((item) => `${item.count} ${item.name}`).join(' · ') || 'No location'}</li>
            <li>{sameSource ? `All ${sameSource.name.toLowerCase()} hires` : summary.sources.map((item) => `${item.count} ${item.name}`).join(' · ')}</li>
            <li>{sameStart ? `All started ${dateLabel(sameStart.date)}` : 'Start dates are mixed'}</li>
            <li>{dash(latest?.active_students)} active students on the latest score report</li>
          </ul>
        </Panel>
      </div>

      <Panel title="Trainees" className="mt-4" extra={<span className="text-xs text-ink/50">{summary.count} people</span>}>
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-2">
          {data.trainees.map((person) => (
            <article key={person.id} className="border border-line rounded-md px-3 py-2.5 bg-paper/60">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-medium leading-snug">{person.name}</h3>
                <StatusPill status={person.bucket} />
              </div>
              <p className="text-xs text-ink/55 mt-1.5">
                {person.location} · {person.source || 'Source unreported'} · {dateLabel(person.start_date)}
              </p>
            </article>
          ))}
        </div>
      </Panel>

      <Panel title="Score checks" className="mt-4">
        <Checks checks={data.checks} />
      </Panel>
    </div>
  )
}
