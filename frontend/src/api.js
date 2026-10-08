import { useCallback, useEffect, useRef, useState } from 'react'

export function useDashboard(path) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)
  const loadRef = useRef(() => {})

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const response = await fetch(path, { cache: 'no-store' })
        if (!response.ok) {
          const body = await response.json().catch(() => ({}))
          throw new Error(body.detail || `Request failed (${response.status})`)
        }
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

    loadRef.current = load
    load()
    const timer = setInterval(load, 10000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [path])

  const reload = useCallback(() => loadRef.current(), [])

  return { data, error, updatedAt, reload }
}
