import { useState } from 'react'
import { dateLabel, dash, pct } from '../format'
import { useDashboard } from '../api'
import { Callout, Cell, Kpi, PageHeader, Panel, SampleMark, State } from '../ui'

const RATINGS = [
  ['strong_hire', 'Strong hire', 'bg-moss', 'bg-[#f2f8f6] text-moss border-moss/25'],
  ['hire', 'Hire', 'bg-moss/45', 'bg-[#f2f8f6] text-moss border-moss/25'],
  ['no_hire', 'No hire', 'bg-clay/45', 'bg-[#fdf4f3] text-clay border-clay/30'],
  ['strong_no_hire', 'Strong no hire', 'bg-clay', 'bg-[#fdf4f3] text-clay border-clay/30'],
]

const RATING_STYLE = Object.fromEntries(RATINGS.map(([, label, , pill]) => [label, pill]))

export default function Recruitment() {
  const [weekOverride, setWeekOverride] = useState(null)
  const path = weekOverride ? `/api/recruitment?week=${weekOverride}` : '/api/recruitment'
  const { data, error, updatedAt } = useDashboard(path)

  return (
    <State data={data} error={error}>
      {data ? (
        <RecruitmentView
          data={data}
          updatedAt={updatedAt}
          week={weekOverride || data.week_ending || ''}
          onWeek={setWeekOverride}
        />
      ) : null}
    </State>
  )
}

function RecruitmentView({ data, updatedAt, week, onWeek }) {
  return (
    <div className="px-5 py-6 lg:px-8">
      <PageHeader
        kicker="Recruitment"
        title="Hiring funnel by cohort"
        lede="Pending counts are people in that round right now. Cleared, offers, joined, and rejected are running totals since the cohort opened."
        asOf={dateLabel(data.as_of)}
        updatedAt={updatedAt}
      />

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <label className="text-sm text-ink/70 flex items-center gap-2">
          Week ending
          <select
            className="bg-card border border-line rounded-md px-2 py-1.5 text-sm text-ink"
            value={week}
            onChange={(event) => onWeek(event.target.value)}
          >
            {(data.weeks || []).map((value) => (
              <option key={value} value={value}>
                {dateLabel(value)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {data.pressure ? (
        <Callout tone="warning" title={data.pressure.headline}>
          {data.pressure.detail}
        </Callout>
      ) : null}

      <div className="flex flex-col gap-4 mt-4">
        {data.cohorts.map((cohort) => (
          <CohortBlock key={cohort.name} cohort={cohort} />
        ))}
        {data.cohorts.length === 0 ? (
          <Panel title="No hiring rows">
            <p className="text-sm text-ink/60">HR has not filed a row for this week.</p>
          </Panel>
        ) : null}
      </div>
    </div>
  )
}

function CohortBlock({ cohort }) {
  const summary = cohort.summary
  const queue = cohort.flow.filter((stage) => !stage.cumulative && stage.total)
  const max = Math.max(...queue.map((stage) => stage.total), 1)

  return (
    <Panel title={cohort.name}>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Kpi label="In pipeline" value={dash(summary.in_pipeline)} />
        <Kpi label="In CTO round" value={dash(summary.in_cto)} />
        <Kpi label="Offers accepted" value={dash(summary.offers_accepted)} />
        <Kpi label="Joined" value={dash(summary.joined)} />
        <Kpi label="Rejected" value={dash(summary.rejected)} />
        <Kpi label="Slots needed" value={dash(summary.slots_needed)} detail="Next week" />
      </div>

      <div className="grid lg:grid-cols-5 gap-6 mt-6">
        <div className="lg:col-span-3">
          <h3 className="text-xs uppercase tracking-wider text-ink/50 font-medium mb-3">People waiting</h3>
          {queue.length ? (
            <div className="flex flex-col gap-2.5">
              {queue.map((stage) => (
                <QueueBar key={stage.label} stage={stage} max={max} />
              ))}
              <div className="flex gap-4 text-[11px] text-ink/55 pt-1">
                <Legend color="bg-moss" label="Associate FDE" />
                <Legend color="bg-sea" label="FDE" />
                <Legend color="bg-brass" label="Senior FDE" />
              </div>
            </div>
          ) : (
            <p className="text-sm text-ink/55">No pending counts reported.</p>
          )}
        </div>
        <div className="lg:col-span-2">
          <h3 className="text-xs uppercase tracking-wider text-ink/50 font-medium mb-3">What HR wrote</h3>
          <div className="flex flex-col gap-3">
            {cohort.notes.map((note) => (
              <div key={`${note.role}-${note.text}`} className="text-sm leading-relaxed">
                <p className="font-medium">
                  {note.role}
                  {note.source ? <span className="text-ink/50 font-normal"> · {note.source}</span> : null}
                </p>
                <p className="text-ink/75 mt-1">{note.text}</p>
              </div>
            ))}
            {cohort.notes.length === 0 ? <p className="text-sm text-ink/55">No note on this row.</p> : null}
          </div>
        </div>
      </div>

      {cohort.feedback?.overall.total ? <Feedback feedback={cohort.feedback} /> : null}

      <div className="overflow-x-auto mt-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-ink/50">
              <th className="text-left font-medium pb-2">Stage</th>
              <th className="text-right font-medium pb-2 px-2">Associate</th>
              <th className="text-right font-medium pb-2 px-2">FDE</th>
              <th className="text-right font-medium pb-2 px-2">Senior</th>
              <th className="text-right font-medium pb-2 px-2">Total</th>
            </tr>
          </thead>
          <tbody>
            {cohort.flow.map((stage) => (
              <StageRow key={stage.label} stage={stage} />
            ))}
            <tr>
              <td colSpan={5} className="pt-4 pb-1 text-[11px] uppercase tracking-wider text-ink/45">
                Other counts
              </td>
            </tr>
            {cohort.other.map((stage) => (
              <StageRow key={stage.label} stage={stage} />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function Feedback({ feedback }) {
  const { overall } = feedback
  return (
    <div className={`mt-6 rounded-lg border px-4 py-4 ${feedback.sample ? 'border-dashed border-brass/60' : 'border-line'}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="text-xs uppercase tracking-wider text-ink/50 font-medium flex items-center gap-2">
          Interview feedback
          {feedback.sample ? <SampleMark /> : null}
        </h3>
        <p className="text-xs text-ink/60">
          {overall.total} verdicts on {feedback.candidates} candidates · <span className="font-semibold text-ink">{pct(overall.hire_rate)}</span> hire or strong hire
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {RATINGS.map(([key, label, color]) => (
          <div key={key} className="rounded-md border border-line bg-card px-3 py-2">
            <p className="text-[11px] uppercase tracking-wider text-ink/55 flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${color}`} />
              {label}
            </p>
            <p className="font-mono text-xl mt-1">{overall[key]}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-6 mt-5">
        <div className="lg:col-span-2">
          <h4 className="text-xs uppercase tracking-wider text-ink/50 font-medium mb-3">By round</h4>
          <div className="flex flex-col gap-2.5">
            {feedback.by_round.map((round) => (
              <div key={round.round} className="grid grid-cols-[2.5rem_1fr_3rem] gap-3 items-center">
                <span className="text-sm font-medium">{round.round}</span>
                <div className="h-5 bg-line/70 rounded-sm overflow-hidden flex">
                  {RATINGS.map(([key, label, color]) =>
                    round[key] ? (
                      <div
                        key={key}
                        className={color}
                        style={{ width: `${(round[key] / round.total) * 100}%` }}
                        title={`${label}: ${round[key]}`}
                      />
                    ) : null,
                  )}
                </div>
                <span className="font-mono text-xs text-right" title="Hire or strong hire">
                  {pct(round.hire_rate)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-3">
          <h4 className="text-xs uppercase tracking-wider text-ink/50 font-medium mb-3">Latest feedback</h4>
          <ul className="divide-y divide-line">
            {feedback.recent.map((item) => (
              <li key={item.id} className="py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    {item.candidate}
                    <span className="text-ink/50 font-normal">
                      {' '}
                      · {item.role} · {item.round} · {item.interviewer}
                    </span>
                  </p>
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${RATING_STYLE[item.rating]}`}>
                    {item.rating}
                  </span>
                </div>
                <p className="text-ink/70 mt-0.5 leading-snug">{item.comment}</p>
                <p className="text-[11px] text-ink/45 mt-0.5">{dateLabel(item.date)}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

function StageRow({ stage }) {
  return (
    <tr className={stage.emphasis ? 'bg-[#fbf6ee]' : 'border-t border-line/80'}>
      <td className={`py-2 pr-3 ${stage.cumulative ? 'text-ink/50' : ''}`}>{stage.label}</td>
      <Cell value={stage.associate} />
      <Cell value={stage.fde} />
      <Cell value={stage.senior} />
      <Cell value={stage.total} strong />
    </tr>
  )
}

function QueueBar({ stage, max }) {
  const parts = [
    ['associate', stage.associate, 'bg-moss'],
    ['fde', stage.fde, 'bg-sea'],
    ['senior', stage.senior, 'bg-brass'],
  ]
  return (
    <div className="grid grid-cols-[9.5rem_1fr_2rem] gap-3 items-center">
      <span className="text-sm">{stage.label}</span>
      <div className="h-6 bg-line/70 rounded-sm overflow-hidden flex">
        {parts.map(([key, value, color]) =>
          value ? (
            <div key={key} className={color} style={{ width: `${(value / max) * 100}%` }} title={`${value}`} />
          ) : null,
        )}
      </div>
      <span className="font-mono text-xs text-right">{stage.total}</span>
    </div>
  )
}

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
      {label}
    </span>
  )
}
