/**
 * useRealtimeEvents — Phase 6
 *
 * Central hook that:
 *  1. Connects to the WebSocket
 *  2. Routes events to toast notifications
 *  3. Exposes callbacks for state updates (signals, work items)
 *  4. Returns WS status for the ConnectionBar
 */

import { useCallback } from 'react'
import { useSignalWebSocket, WsStatus } from './useSignalWebSocket'
import { useToast } from '../components/Toast'
import { WsEvent, WorkItem, Signal } from '../types'

interface Options {
  onSignal?: (signal: Signal) => void
  onWorkItemCreated?: (wi: WorkItem) => void
  onWorkItemUpdated?: (wi: WorkItem) => void
}

const PRIORITY_TOAST_KIND: Record<string, 'error' | 'warning' | 'info'> = {
  P0: 'error',
  P1: 'warning',
  P2: 'info',
  P3: 'info',
}

export function useRealtimeEvents(options: Options = {}) {
  const toast = useToast()

  const handleEvent = useCallback((event: WsEvent) => {
    switch (event.type) {

      case 'signal': {
        options.onSignal?.(event.data)
        // Only toast on CRITICAL signals to avoid noise
        if (event.data.severity === 'CRITICAL') {
          toast.add({
            kind: 'error',
            title: `Critical: ${event.data.component_id}`,
            message: event.data.message.slice(0, 80),
            duration: 6000,
          })
        }
        break
      }

      case 'work_item_created': {
        options.onWorkItemCreated?.(event.data)
        const kind = PRIORITY_TOAST_KIND[event.data.priority] ?? 'info'
        toast.add({
          kind,
          title: `[${event.data.priority}] New Incident`,
          message: `${event.data.component_id} — ${event.data.title.slice(0, 60)}`,
          duration: 8000,
        })
        break
      }

      case 'work_item_updated': {
        options.onWorkItemUpdated?.(event.data)
        const wi = event.data
        // Only toast on meaningful transitions
        if (wi.status === 'CLOSED') {
          toast.add({
            kind: 'success',
            title: 'Incident Closed',
            message: `${wi.component_id} — MTTR: ${wi.mttr_seconds ? Math.round(wi.mttr_seconds / 60) + 'm' : 'N/A'}`,
            duration: 5000,
          })
        } else if (wi.status === 'RESOLVED') {
          toast.add({
            kind: 'success',
            title: 'Incident Resolved',
            message: wi.component_id,
            duration: 4000,
          })
        }
        break
      }
    }
  }, [toast, options])

  const { status, attempts, clientId } = useSignalWebSocket({
    onEvent: handleEvent,
  })

  return { status, attempts, clientId }
}
