import { useState } from 'react'
import { ChevronDown, Download } from 'lucide-react'
import { dateLabel, pct } from '../format'
import { useDashboard } from '../api'
import { Kpi, PageHeader, State } from '../ui'

const BAND = {
  'Deploy-ready': 'text-moss',
  'Needs coaching': 'text-brass',
  'At risk': 'text-clay',
}

export default function Cohort() {
  const [code, setCode] = useState(null)
  const path = code ? `/api/academy?cohort=${encodeURIComponent(code)}` : '/api/academy'
  const { data, error, updatedAt } = useDashboard(path)

  return (
    <State data={data} error={error}>
      {data ? <CohortView data={data} updatedAt={updatedAt} onSelect={setCode} /> : null}
    </State>
  )
}

function CohortView({ data, updatedAt, onSelect }) {
  const selected = data.selected
  const [openId, setOpenId] = useState(null)

  return (
    <div className="px-5 py-6 lg:px-8">
      <PageHeader
        kicker="Cohort health"
        title="Who becomes supply, and when"
        lede={data.pipeline.sentence}
        asOf={dateLabel(data.as_of)}
        updatedAt={updatedAt}
      />

      <div className="grid md:grid-cols-3 gap-3">
        {data.cohorts.map((cohort) => {
          const active = cohort.code === data.selected_code
          return (
            <button
              key={cohort.code}
              type="button"
              onClick={() => {
                setOpenId(null)
                onSelect(cohort.code)
              }}
              className={`text-left rounded-lg border bg-card px-4 py-3 ${
                active ? 'border-moss ring-1 ring-moss' : 'border-line hover:border-ink/30'
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className="font-semibold">{cohort.name}</p>
                <p className="font-mono text-sm">{pct(cohort.class_overall)}</p>
              </div>
              <p className="mt-2 text-sm leading-snug">
                <span className="font-mono">{cohort.deploy_ready_unplaced}</span>
                <span className="text-ink/45 text-xs"> waiting</span>
                <span className="text-ink/45 text-xs"> · {cohort.placed} placed · {cohort.headcount} people</span>
              </p>
              <p className="text-xs text-ink/55 mt-1">
                Week {cohort.calendar_week ?? '–'} of {cohort.program_weeks}
                {cohort.provisional ? ' · provisional' : ''}
                {' · '}
                {dateLabel(cohort.supply_date)}
              </p>
            </button>
          )
        })}
      </div>

      {selected ? (
        <>
          <p className="mt-5 text-sm leading-relaxed text-ink/75 max-w-3xl">{selected.verdict}</p>

          <div className="grid md:grid-cols-3 gap-3 mt-4">
            <Kpi
              label="Quality"
              value={pct(selected.class_overall)}
              detail={`Hands-on ${pct(selected.class_hands_on)} · Proctored ${pct(selected.class_proctored)} · bar ${pct(selected.readiness_floor)}`}
            />
            <Kpi
              label="Clock"
              value={selected.calendar_week != null ? `Week ${selected.calendar_week}` : '–'}
              detail={
                selected.filing_lag
                  ? `Last score is week ${selected.filed_week} · ${selected.filing_lag} weeks behind · ${selected.weeks_left} left`
                  : `Score filed through week ${selected.filed_week ?? '–'} · ${selected.weeks_left ?? '–'} weeks left`
              }
            />
            <Kpi
              label="Placed"
              value={`${selected.placed} / ${selected.headcount}`}
              detail={`Supply ${dateLabel(selected.supply_date)} · ${selected.deploy_ready} deploy-ready`}
            />
          </div>

          <section className="mt-4 bg-card border border-line rounded-lg p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h2 className="text-sm font-semibold">Academy weeks</h2>
              <p className="text-xs text-ink/50">{selected.topic || 'No topic on the latest filed week'}</p>
            </div>
            <div className="grid grid-cols-6 sm:grid-cols-12 gap-1.5">
              {selected.track.map((week) => (
                <div
                  key={week.week}
                  title={week.topic || `Week ${week.week}`}
                  className={`rounded-md px-1 py-2 text-center border ${
                    week.current ? 'border-ink' : 'border-transparent'
                  } ${week.filed ? 'bg-moss text-white' : 'bg-line/70 text-ink/45'}`}
                >
                  <p className="text-[10px] uppercase tracking-wide opacity-80">W{week.week}</p>
                  <p className="font-mono text-xs mt-0.5">{week.overall != null ? pct(week.overall) : '·'}</p>
                </div>
              ))}
            </div>
          </section>

          <ul className="mt-4 border-t border-line">
            {selected.candidates.map((person) => (
              <Candidate
                key={person.id}
                person={person}
                open={openId === person.id}
                onToggle={() => setOpenId(openId === person.id ? null : person.id)}
              />
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}

function Candidate({ person, open, onToggle }) {
  return (
    <li className="border-b border-line">
      <div className="flex items-center gap-3 py-2.5">
        <button type="button" onClick={onToggle} className="min-w-0 flex-1 flex items-center gap-4 text-left">
          <ChevronDown className={`h-4 w-4 shrink-0 text-ink/40 transition-transform ${open ? 'rotate-180' : ''}`} />
          <div className="min-w-0 flex-1">
            <p className="font-medium truncate">{person.name}</p>
            <p className="text-xs text-ink/50 mt-0.5">
              {person.location}
              {person.placed ? ` · ${person.client}` : ' · Open'}
              {person.declining ? ' · scores falling' : ''}
            </p>
          </div>
          <p className="font-mono text-sm w-8 text-right">{Math.round(person.score)}</p>
          <p className={`text-xs w-28 ${BAND[person.band] || 'text-ink/60'}`}>{person.band}</p>
        </button>
        <a
          href={`/api/academy/resumes/${person.id}`}
          onClick={(event) => event.stopPropagation()}
          className="shrink-0 inline-flex items-center gap-1.5 rounded border border-line px-2.5 py-1 text-xs font-medium hover:border-ink/30"
        >
          <Download className="h-3.5 w-3.5" aria-hidden="true" />
          Resume
        </a>
      </div>
      {open ? <Profile person={person} /> : null}
    </li>
  )
}

function Profile({ person }) {
  const resume = person.resume
  return (
    <div className="grid lg:grid-cols-2 gap-6 pb-4 pl-8 text-sm">
      <div>
        <p className="text-[11px] uppercase tracking-wider text-ink/45 mb-2">Assessments</p>
        <ul className="space-y-1">
          {person.weeks.map((week) => (
            <li key={week.week} className="flex justify-between gap-3 text-xs">
              <span>
                W{week.week}
                {week.topic ? <span className="text-ink/55"> {week.topic}</span> : null}
              </span>
              <span className="font-mono shrink-0">{pct(week.hands_on)} / {pct(week.proctored)}</span>
            </li>
          ))}
        </ul>
        {person.reason ? <p className="text-xs text-ink/60 mt-3">{person.reason}</p> : null}
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-wider text-ink/45 mb-2">Resume</p>
        <p>{resume.education} · {resume.years_experience} years</p>
        <p className="mt-1 text-ink/70">{resume.skills.join(', ') || 'No skills listed'}</p>
        <p className="mt-1 text-ink/70">
          {resume.certifications.length ? resume.certifications.join(', ') : 'No certifications'}
        </p>
        {resume.missing_skills.length ? (
          <p className="mt-1 text-clay text-xs">Missing {resume.missing_skills.join(', ')}</p>
        ) : null}
      </div>
    </div>
  )
}
