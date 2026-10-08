import { useEffect, useState } from 'react'

const KEY = 'mb-insight-filters'
const EMPTY = { start: '', end: '', phase: '', role: '', location: '', cohort: '', basis: 'inferred' }

function read() {
  try {
    return { ...EMPTY, ...JSON.parse(window.localStorage.getItem(KEY) || '{}') }
  } catch {
    return EMPTY
  }
}

// Shared by Economics and Leadership Actions so a filter set on one page carries to the other.
export function useFilters() {
  const [filters, setFilters] = useState(read)
  useEffect(() => {
    window.localStorage.setItem(KEY, JSON.stringify(filters))
  }, [filters])
  return [filters, (patch) => setFilters((current) => ({ ...current, ...patch })), () => setFilters(EMPTY)]
}

export function toQuery(filters, skip = []) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value && !skip.includes(key)) params.set(key, value)
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

function Select({ label, value, onChange, options, allLabel = 'All' }) {
  return (
    <label className="flex flex-col gap-1 text-[11px] uppercase tracking-wider text-ink/55 font-medium">
      {label}
      <select
        className="bg-card border border-line rounded-md px-2 py-1.5 text-sm text-ink normal-case tracking-normal font-normal min-w-[8rem]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {allLabel !== null ? <option value="">{allLabel}</option> : null}
        {options.map((option) => {
          const [val, text] = Array.isArray(option) ? option : [option, option]
          return (
            <option key={val} value={val}>
              {text}
            </option>
          )
        })}
      </select>
    </label>
  )
}

export function FilterBar({ filters, onChange, onReset, options, showPhase = true }) {
  const phaseLabels = { recruitment: 'Recruitment', training: 'Training', deployment: 'Deployment' }
  return (
    <div className="bg-card border border-line rounded-lg px-4 py-3 mb-4 flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-[11px] uppercase tracking-wider text-ink/55 font-medium">
        From
        <input
          type="date"
          value={filters.start}
          onChange={(event) => onChange({ start: event.target.value })}
          className="bg-card border border-line rounded-md px-2 py-1.5 text-sm text-ink font-normal"
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] uppercase tracking-wider text-ink/55 font-medium">
        To (as of)
        <input
          type="date"
          value={filters.end}
          onChange={(event) => onChange({ end: event.target.value })}
          className="bg-card border border-line rounded-md px-2 py-1.5 text-sm text-ink font-normal"
        />
      </label>
      {showPhase ? (
        <Select
          label="Stage"
          value={filters.phase}
          onChange={(phase) => onChange({ phase })}
          options={(options?.phases || []).map((phase) => [phase, phaseLabels[phase] || phase])}
        />
      ) : null}
      <Select label="Role" value={filters.role} onChange={(role) => onChange({ role })} options={options?.roles || []} />
      <Select label="Location" value={filters.location} onChange={(location) => onChange({ location })} options={options?.locations || []} />
      <Select label="Cohort" value={filters.cohort} onChange={(cohort) => onChange({ cohort })} options={options?.cohorts || []} />
      <Select
        label="Count basis"
        value={filters.basis}
        onChange={(basis) => onChange({ basis })}
        allLabel={null}
        options={[
          ['inferred', 'Reported + inferred'],
          ['reported', 'Reported only'],
        ]}
      />
      <button type="button" onClick={onReset} className="text-sm text-sea hover:underline pb-1.5 ml-auto">
        Reset filters
      </button>
    </div>
  )
}
