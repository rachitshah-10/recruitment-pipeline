
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

      {/* Bench-to-Client Matching with AI */}
      <BenchMatcher roster={data.roster} asOf={data.as_of} />

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

// ======================================================
// INTELLIGENT BENCH-TO-CLIENT MATCHING
// AI-ASSISTED REQUIREMENT EXTRACTION + MATCHING
// ======================================================

function BenchMatcher({ roster, asOf }) {
  const [clientName, setClientName] = useState('')
  const [role, setRole] = useState('Any')
  const [location, setLocation] = useState('Any')
  const [skills, setSkills] = useState('Python, FastAPI, AWS')
  const [profiles, setProfiles] = useState({})
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // AI requirement extraction state
  const [description, setDescription] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState('')
  const [aiResult, setAiResult] = useState(null)
  const [aiWarnings, setAiWarnings] = useState([])

  // NEW: Explicit review state for AI-extracted filters
  const [roleReviewRequired, setRoleReviewRequired] = useState(false)
  const [locationReviewRequired, setLocationReviewRequired] = useState(false)
  const [roleAnyApproved, setRoleAnyApproved] = useState(false)
  const [locationAnyApproved, setLocationAnyApproved] = useState(false)

  const bench = roster.filter(
    (person) => person.bucket === 'On bench'
  )

  const roles = [...new Set(
    bench.map((person) => person.career_stage).filter(Boolean)
  )].sort()

  const locations = [...new Set(
    bench.map((person) => person.location).filter(Boolean)
  )].sort()

  function clearResults() {
    setResults(null)
    setError('')
  }

  function updateProfile(id, value) {
    setProfiles((previous) => ({
      ...previous,
      [String(id)]: value
    }))
    clearResults()
  }

  // NEW: Map AI values to roster options without silently
  // changing an unresolved requirement into an unrestricted match.
  function resolveRosterOption(value, options, type) {
    const raw = String(value ?? '').trim()

    const normalizeOption = (text) =>
      String(text ?? '')
        .toLowerCase()
        .replace(/\./g, '')
        .replace(/[-_]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()

    const normalized = normalizeOption(raw)

    if (
      !normalized ||
      ['any', 'unknown', 'not specified', 'unspecified', 'none', 'n/a']
        .includes(normalized)
    ) {
      return {
        value: 'Any',
        reviewRequired: true,
        warning: `AI did not identify a specific ${type}. Select one or explicitly approve matching with Any ${type}.`
      }
    }

    const direct = options.find(
      (option) => normalizeOption(option) === normalized
    )

    if (direct) {
      return {
        value: direct,
        reviewRequired: false,
        warning: null
      }
    }

    const aliases = type === 'location'
      ? {
          usa: [
            'usa',
            'us',
            'united states',
            'united states of america'
          ],
          latam: [
            'latam',
            'latin america',
            'latin american'
          ]
        }
      : {
          fde: [
            'fde',
            'forward deployed engineer'
          ],
          'senior fde': [
            'senior fde',
            'senior forward deployed engineer'
          ]
        }

    const group = Object.values(aliases).find(
      (values) => values.includes(normalized)
    )

    if (group) {
      const equivalent = options.find((option) =>
        group.includes(normalizeOption(option))
      )

      if (equivalent) {
        return {
          value: equivalent,
          reviewRequired: false,
          warning: null
        }
      }
    }

    return {
      value: 'Any',
      reviewRequired: true,
      warning: `AI extracted ${type} "${raw}", but no matching roster option was found. Choose a ${type} or explicitly approve Any ${type}.`
    }
  }

  const roleBlocked =
    roleReviewRequired && role === 'Any' && !roleAnyApproved

  const locationBlocked =
    locationReviewRequired && location === 'Any' && !locationAnyApproved

  // Call FastAPI + Ollama extraction endpoint.
  async function extractWithAI() {
    setAiError('')
    setAiWarnings([])
    setAiResult(null)
    setRoleReviewRequired(false)
    setLocationReviewRequired(false)
    setRoleAnyApproved(false)
    setLocationAnyApproved(false)

    if (description.trim().length < 10) {
      setAiError('Enter a client requirement of at least 10 characters.')
      return
    }

    setAiLoading(true)
    clearResults()

    try {
      const response = await fetch(
        '/api/deployment/extract-requirements',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            description: description.trim()
          })
        }
      )

      const data = await response.json()

      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join('; ')
          : data.detail

        throw new Error(
          typeof detail === 'string'
            ? detail
            : 'AI requirement extraction failed.'
        )
      }

      const extractedSkills = Array.isArray(data.required_skills)
        ? data.required_skills.filter(
            (skill) => typeof skill === 'string' && skill.trim()
          )
        : []

      const resolvedRole = resolveRosterOption(
        data.role,
        roles,
        'role'
      )

      const resolvedLocation = resolveRosterOption(
        data.location,
        locations,
        'location'
      )

      const warnings = [
        resolvedRole.warning,
        resolvedLocation.warning
      ].filter(Boolean)

      if (!extractedSkills.length) {
        warnings.push(
          'No technical skills were extracted. Enter the required skills manually.'
        )
      }

      setRole(resolvedRole.value)
      setLocation(resolvedLocation.value)
      setSkills(extractedSkills.join(', '))
      setAiResult(data)
      setAiWarnings(warnings)

      setRoleReviewRequired(resolvedRole.reviewRequired)
      setLocationReviewRequired(resolvedLocation.reviewRequired)

    } catch (err) {
      setAiError(
        err.message || 'Unable to extract requirements with AI.'
      )
    } finally {
      setAiLoading(false)
    }
  }

  async function findMatches(event) {
    event.preventDefault()

    // NEW: Safety check before sending matching request
    if (roleBlocked || locationBlocked) {
      setError(
        'Review the AI-extracted role and location before matching. Select a roster option or explicitly approve unrestricted matching.'
      )
      return
    }

    setLoading(true)
    setError('')
    setResults(null)

    try {
      const requiredSkills = skills
        .split(',')
        .map((skill) => skill.trim())
        .filter(Boolean)

      if (!requiredSkills.length) {
        throw new Error('Enter at least one required skill.')
      }

      const response = await fetch(
        `/api/deployment/match?as_of=${encodeURIComponent(asOf)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            client: clientName.trim(),
            role,
            location,
            required_skills: requiredSkills,
            profiles: Object.fromEntries(
              Object.entries(profiles).map(([id, value]) => [
                id,
                value.split(',')
                  .map((skill) => skill.trim())
                  .filter(Boolean)
              ])
            )
          })
        }
      )

      const data = await response.json()

      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join('; ')
          : data.detail

        throw new Error(
          typeof detail === 'string'
            ? detail
            : 'Matching request failed.'
        )
      }

      setResults(data)
    } catch (err) {
      setError(err.message || 'Unable to find matches.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Panel
      title="Intelligent Bench-to-Client Matching"
      className="mt-4"
      extra={
        <span className="text-xs text-ink/50">
          {bench.length} bench employees
        </span>
      }
    >
      <div className="mb-5">
        <div className="inline-flex items-center gap-2 rounded-full bg-sea/10 text-sea px-3 py-1 text-xs font-semibold mb-3">
          AI-Assisted Deployment Matching
        </div>

        <p className="text-sm text-ink/65">
          Match available Forward Deployed Engineers with client
          requirements based on technical skills, role, and location.
          The matching engine provides explainable scores and
          identifies skill gaps.
        </p>

        <p className="text-xs text-ink/50 mt-2">
          AI extracts requirements using a local Llama 3.2 model.
          Candidate scoring remains rule-based. Employee skills are
          manually entered for this session and are not verified by
          the system.
        </p>
      </div>

      {/* AI REQUIREMENT ASSISTANT */}
      <div className="mb-6 rounded-xl border border-sea/30 bg-sea/5 p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h3 className="text-base font-semibold">
              AI Requirement Assistant
            </h3>
            <p className="text-xs text-ink/60 mt-1">
              Powered by local Llama 3.2 through Ollama
            </p>
          </div>

          <span className="rounded-full border border-sea/30 bg-paper px-3 py-1 text-xs font-medium text-sea">
            Local AI
          </span>
        </div>

        <p className="text-sm text-ink/70 mb-3">
          Describe the client's staffing requirement in plain English.
          The AI will extract the role, location, and technical skills
          into the matching form below.
        </p>

        <label className="block text-sm font-medium">
          Client requirement description
          <textarea
            value={description}
            onChange={(event) => {
              setDescription(event.target.value)
              setAiError('')
              setAiResult(null)
              setAiWarnings([])
              setRoleReviewRequired(false)
              setLocationReviewRequired(false)
              setRoleAnyApproved(false)
              setLocationAnyApproved(false)
              clearResults()
            }}
            rows={4}
            maxLength={3000}
            placeholder="Example: We need an FDE in USA with Python, FastAPI, AWS and RAG experience."
            className="mt-1.5 w-full bg-paper border border-line rounded-md px-3 py-2.5 text-sm resize-y"
          />
        </label>

        <div className="flex flex-wrap items-center gap-3 mt-3">
          <button
            type="button"
            onClick={extractWithAI}
            disabled={aiLoading || description.trim().length < 10}
            className="rounded-md bg-sea text-white px-5 py-2.5 text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {aiLoading
              ? 'AI is extracting requirements...'
              : 'Extract Requirements with AI'}
          </button>

          <span className="text-xs text-ink/50">
            Review the extracted fields before matching.
          </span>
        </div>

        {aiError && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700"
          >
            {aiError}
          </div>
        )}

        {aiResult && (
          <div className="mt-4 rounded-lg border border-line bg-paper p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold">
                AI Extraction Complete
              </h4>
              <span className="text-xs text-ink/50">
                Model: {aiResult.model || 'Local LLM'}
              </span>
            </div>

            <div className="grid md:grid-cols-3 gap-3 mt-3">
              <div className="rounded-md border border-line p-3">
                <div className="text-xs text-ink/50 mb-1">
                  Extracted role
                </div>
                <div className="text-sm font-semibold">
                  {aiResult.role || 'Any'}
                </div>
              </div>

              <div className="rounded-md border border-line p-3">
                <div className="text-xs text-ink/50 mb-1">
                  Extracted location
                </div>
                <div className="text-sm font-semibold">
                  {aiResult.location || 'Any'}
                </div>
              </div>

              <div className="rounded-md border border-line p-3">
                <div className="text-xs text-ink/50 mb-1">
                  Technical skills
                </div>
                <div className="text-sm font-semibold">
                  {Array.isArray(aiResult.required_skills) &&
                  aiResult.required_skills.length
                    ? aiResult.required_skills.join(', ')
                    : 'None extracted'}
                </div>
              </div>
            </div>

            <p className="text-xs text-ink/60 mt-3">
              The matching fields below have been updated where
              corresponding roster options were available.
              Unresolved role or location values require explicit
              review before matching.
            </p>
          </div>
        )}

        {aiWarnings.length > 0 && (
          <div
            role="alert"
            className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
          >
            <div className="font-semibold mb-2">
              Review required
            </div>
            <ul className="list-disc pl-5 space-y-1">
              {aiWarnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* EXISTING MATCHING FORM */}
      <form onSubmit={findMatches} className="space-y-5">
        <div className="grid md:grid-cols-2 gap-4">
          <label className="block text-sm font-medium">
            Client name
            <input
              required
              maxLength={100}
              value={clientName}
              onChange={(event) => {
                setClientName(event.target.value)
                clearResults()
              }}
              placeholder="Example: Banking Client ABC"
              className="mt-1.5 w-full bg-paper border border-line rounded-md px-3 py-2.5 text-sm"
            />
          </label>

          <label className="block text-sm font-medium">
            Required role
            <select
              value={role}
              onChange={(event) => {
                setRole(event.target.value)
                setRoleAnyApproved(false)
                clearResults()
              }}
              className="mt-1.5 w-full bg-paper border border-line rounded-md px-3 py-2.5 text-sm"
            >
              <option value="Any">Any role</option>
              {roles.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium">
            Required location
            <select
              value={location}
              onChange={(event) => {
                setLocation(event.target.value)
                setLocationAnyApproved(false)
                clearResults()
              }}
              className="mt-1.5 w-full bg-paper border border-line rounded-md px-3 py-2.5 text-sm"
            >
              <option value="Any">Any location</option>
              {locations.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium">
            Required technical skills
            <input
              required
              value={skills}
              onChange={(event) => {
                setSkills(event.target.value)
                clearResults()
              }}
              placeholder="Python, FastAPI, AWS, RAG"
              className="mt-1.5 w-full bg-paper border border-line rounded-md px-3 py-2.5 text-sm"
            />
            <span className="block text-xs text-ink/50 mt-1">
              Separate skills using commas.
            </span>
          </label>
        </div>

        {/* NEW: Explicit approval when an AI filter is unresolved */}
        {(roleReviewRequired || locationReviewRequired) && (
          <div
            className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
          >
            <h3 className="font-semibold mb-2">
              Confirm AI-extracted filters
            </h3>

            <p className="mb-3">
              The AI could not confidently map one or more requirements
              to the available bench roster. Select a specific role or
              location above, or explicitly approve unrestricted matching.
            </p>

            {roleReviewRequired && role === 'Any' && (
              <label className="flex items-start gap-2 mb-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={roleAnyApproved}
                  onChange={(event) => {
                    setRoleAnyApproved(event.target.checked)
                    clearResults()
                  }}
                  className="mt-1"
                />
                <span>
                  I confirm that matching across <strong>all roles</strong> is acceptable.
                </span>
              </label>
            )}

            {locationReviewRequired && location === 'Any' && (
              <label className="flex items-start gap-2 mb-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={locationAnyApproved}
                  onChange={(event) => {
                    setLocationAnyApproved(event.target.checked)
                    clearResults()
                  }}
                  className="mt-1"
                />
                <span>
                  I confirm that matching across <strong>all locations</strong> is acceptable.
                </span>
              </label>
            )}

            {(roleBlocked || locationBlocked) ? (
              <p className="font-semibold mt-3">
                Matching is blocked until the unresolved filters are reviewed.
              </p>
            ) : (
              <p className="font-semibold mt-3">
                Filter review complete. You may proceed with matching.
              </p>
            )}
          </div>
        )}

        <div className="border border-line rounded-lg p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h3 className="font-semibold text-sm">
              Available Bench Employees
            </h3>
            <span className="text-xs text-ink/50">
              {bench.length} available
            </span>
          </div>

          <p className="text-xs text-ink/60 mb-4">
            Enter known skills for each bench employee.
            Leave the field empty if the skills are unknown.
            Example data must be clearly identified as demo data.
          </p>

          {bench.length === 0 ? (
            <div className="rounded-md bg-paper p-4 text-sm text-ink/60">
              No employees are currently on the bench.
            </div>
          ) : (
            <div className="space-y-4">
              {bench.map((person) => (
                <div
                  key={person.id}
                  className="rounded-lg border border-line/80 p-3"
                >
                  <div className="flex flex-wrap justify-between gap-2 mb-2">
                    <div>
                      <div className="font-semibold text-sm">
                        {person.name}
                      </div>
                      <div className="text-xs text-ink/50 mt-0.5">
                        {person.career_stage} · {person.location}
                      </div>
                    </div>

                    <span className="rounded-full bg-amber-100 text-amber-800 px-2 py-1 text-xs h-fit">
                      On bench
                    </span>
                  </div>

                  <label className="block text-xs font-medium">
                    Employee technical skills
                    <input
                      value={profiles[String(person.id)] || ''}
                      onChange={(event) =>
                        updateProfile(person.id, event.target.value)
                      }
                      placeholder="Example: Python, SQL, AWS"
                      className="mt-1 w-full bg-paper border border-line rounded-md px-3 py-2 text-sm"
                    />
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={
            loading ||
            aiLoading ||
            bench.length === 0 ||
            roleBlocked ||
            locationBlocked
          }
          className="rounded-md bg-ink text-white px-6 py-3 text-sm font-semibold hover:opacity-90 disabled:opacity-50"
        >
          {loading
            ? 'Analyzing candidates...'
            : 'Find Best Bench Matches'}
        </button>
      </form>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {results && (
        <div className="mt-6 space-y-4">
          <div className="border-t border-line pt-5">
            <h3 className="text-lg font-semibold">
              Matching Recommendations
            </h3>

            <p className="text-sm text-ink/60 mt-1">
              Client: {results.client}
            </p>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
              <div className="rounded-lg bg-paper border border-line p-3">
                <div className="text-xs text-ink/50">
                  Bench employees
                </div>
                <div className="text-2xl font-bold mt-1">
                  {results.bench_count}
                </div>
              </div>

              <div className="rounded-lg bg-paper border border-line p-3">
                <div className="text-xs text-ink/50">
                  Role/location eligible
                </div>
                <div className="text-2xl font-bold mt-1">
                  {results.eligible_count}
                </div>
              </div>

              <div className="rounded-lg bg-paper border border-line p-3">
                <div className="text-xs text-ink/50">
                  Skill profiles entered
                </div>
                <div className="text-2xl font-bold mt-1">
                  {results.matches.filter(
                    (person) => person.profile_provided
                  ).length}
                </div>
              </div>
            </div>
          </div>

          {results.matches.length === 0 ? (
            <div className="rounded-lg border border-line p-5 text-sm text-ink/60">
              No bench employees meet the selected role and
              location requirements. Try adjusting the filters.
            </div>
          ) : (
            results.matches.map((person, index) => (
              <div
                key={person.id}
                className="rounded-lg border border-line p-4"
              >
                <div className="flex flex-wrap justify-between gap-3">
                  <div>
                    <div className="text-xs text-ink/50 mb-1">
                      Candidate #{index + 1}
                    </div>
                    <h4 className="text-base font-semibold">
                      {person.name}
                    </h4>
                    <p className="text-xs text-ink/60 mt-1">
                      {person.role} · {person.location}
                    </p>
                  </div>

                  <div className="text-right">
                    <div className="text-2xl font-bold font-mono">
                      {person.score === null
                        ? 'N/A'
                        : `${person.score}%`}
                    </div>
                    <div className="text-xs text-ink/50">
                      Skill match
                    </div>
                  </div>
                </div>

                {person.score !== null && (
                  <div className="h-2 bg-line rounded-full mt-4 overflow-hidden">
                    <div
                      className="h-full bg-sea rounded-full"
                      style={{
                        width: `${Math.max(
                          0,
                          Math.min(100, person.score)
                        )}%`
                      }}
                    />
                  </div>
                )}

                <div className="grid md:grid-cols-2 gap-3 mt-4">
                  <div className="rounded-md bg-sea/5 p-3">
                    <div className="text-xs font-semibold mb-1">
                      Matched Skills
                    </div>
                    <p className="text-sm">
                      {person.matched_skills.length
                        ? person.matched_skills.join(', ')
                        : 'None'}
                    </p>
                  </div>

                  <div className="rounded-md bg-paper p-3">
                    <div className="text-xs font-semibold mb-1">
                      Skill Gaps
                    </div>
                    <p className="text-sm">
                      {person.missing_skills.length
                        ? person.missing_skills.join(', ')
                        : 'None'}
                    </p>
                  </div>
                </div>

                <div className="mt-3 text-sm text-ink/70">
                  <span className="font-semibold">
                    Matching explanation:
                  </span>{' '}
                  {person.explanation}
                </div>

                {!person.profile_provided && (
                  <div className="mt-3 text-xs text-amber-700">
                    Skills not provided. Verify the employee's
                    technical profile before making a recommendation.
                  </div>
                )}
              </div>
            ))
          )}

          <p className="text-xs text-ink/50 border-t border-line pt-3">
            {results.disclaimer}
          </p>
        </div>
      )}
    </Panel>
  )
}
