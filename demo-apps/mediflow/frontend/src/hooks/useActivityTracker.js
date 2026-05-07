import { useRef, useCallback, useEffect } from 'react'
import { api } from '../api/client'

const FLUSH_INTERVAL = 5000

/**
 * Batched activity tracker — queues events in memory and flushes to the
 * backend every 5 seconds. Fire-and-forget; errors are silently swallowed.
 */
export function useActivityTracker(sessionId) {
  const queue = useRef([])
  const timer = useRef(null)

  const flush = useCallback(() => {
    if (queue.current.length === 0) return
    const batch = queue.current.splice(0)
    api.logActivity(sessionId, batch).catch(() => {})
  }, [sessionId])

  // Set up the interval
  useEffect(() => {
    timer.current = setInterval(flush, FLUSH_INTERVAL)
    return () => {
      clearInterval(timer.current)
      flush() // flush remaining on unmount
    }
  }, [flush])

  const trackAction = useCallback((actionType, detail = '', entityType = null, entityId = null) => {
    queue.current.push({
      action_type: actionType,
      action_detail: detail,
      entity_type: entityType,
      entity_id: entityId,
    })
  }, [])

  return trackAction
}
