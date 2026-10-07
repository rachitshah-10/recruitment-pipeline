export function dash(value) {
  if (value === null || value === undefined || value === '') return '–'
  return value
}

export function dateLabel(iso) {
  if (!iso) return '–'
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

export function money(value) {
  if (value === null || value === undefined) return '–'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function moneyCompact(value) {
  if (value === null || value === undefined) return '–'
  const abs = Math.abs(value)
  if (abs >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
  if (abs >= 1000) return `$${(value / 1000).toFixed(1)}K`
  return money(value)
}

export function pct(fraction) {
  if (fraction === null || fraction === undefined) return '–'
  return `${Math.round(fraction * 100)}%`
}

export function points(fraction) {
  if (fraction === null || fraction === undefined) return '–'
  const pts = Math.round(fraction * 100)
  return pts > 0 ? `+${pts} pts` : `${pts} pts`
}

export function rate(value) {
  if (value === null || value === undefined) return '–'
  const rounded = Math.round(value * 100) / 100
  return Number.isInteger(rounded) ? `$${rounded}` : `$${rounded.toFixed(2)}`
}

export function formatWhen(value) {
  return value.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function endsIn(days) {
  if (days === null || days === undefined) return null
  if (days < 0) return `Ended ${Math.abs(days)}d ago`
  if (days === 0) return 'Ends today'
  if (days === 1) return 'Ends tomorrow'
  return `Ends in ${days} days`
}
