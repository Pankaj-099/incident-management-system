/**
 * useSignalWebSocket — Phase 6
 *
 * Improvements over Phase 2:
 * - Responds to server "ping" events with a "pong" to keep connection alive
 * - Emits "connected" event data (client_id, active_connections)
 * - Exponential backoff reconnect (capped at 30s)
 * - Tracks reconnect attempt count for UI display
 * - Calls onStatusChange so consumers can show live connection state
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { WsEvent } from '../types'

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseSignalWebSocketOptions {
  onEvent: (event: WsEvent) => void
  onStatusChange?: (status: WsStatus) => void
}

const WS_BASE              = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
const MAX_RECONNECT        = 15
const BASE_RECONNECT_MS    = 1000
const MAX_RECONNECT_MS     = 30_000

export function useSignalWebSocket({ onEvent, onStatusChange }: UseSignalWebSocketOptions) {
  const [status, setStatus]   = useState<WsStatus>('disconnected')
  const [attempts, setAttempts] = useState(0)
  const [clientId, setClientId] = useState<string | null>(null)
  const wsRef      = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const updateStatus = useCallback((s: WsStatus) => {
    setStatus(s)
    onStatusChange?.(s)
  }, [onStatusChange])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    updateStatus('connecting')
    const ws = new WebSocket(`${WS_BASE}/ws/signals`)
    wsRef.current = ws

    ws.onopen = () => {
      updateStatus('connected')
      attemptsRef.current = 0
      setAttempts(0)
    }

    ws.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data)

        // Respond to heartbeat pings
        if (parsed.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong', ts: new Date().toISOString() }))
          return
        }

        // Extract client_id from "connected" event
        if (parsed.type === 'connected') {
          setClientId(parsed.data?.client_id ?? null)
          return
        }

        onEventRef.current(parsed as WsEvent)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      updateStatus('disconnected')
      wsRef.current = null
      if (attemptsRef.current < MAX_RECONNECT) {
        const delay = Math.min(
          BASE_RECONNECT_MS * Math.pow(1.5, attemptsRef.current),
          MAX_RECONNECT_MS
        )
        attemptsRef.current++
        setAttempts(attemptsRef.current)
        timerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      updateStatus('error')
      ws.close()
    }
  }, [updateStatus])

  useEffect(() => {
    connect()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { status, attempts, clientId }
}
