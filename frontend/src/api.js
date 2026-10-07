import { useEffect, useState } from 'react'

export function useDashboard(path) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const response = await fetch(path, { cache: 'no-store' })
        if (!response.ok) throw new Error(`Request failed (${response.status})`)
        const json = await response.json()
        if (!cancelled) {
          setData(json)
          setError(null)
          setUpdatedAt(new Date())
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Unable to reach the API')
      }
    }

    load()
    const timer = setInterval(load, 10000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [path])

  return { data, error, updatedAt }
}
