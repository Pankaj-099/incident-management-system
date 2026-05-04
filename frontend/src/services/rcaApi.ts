const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    let detail: string
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string'
        ? body.detail
        : body.detail?.message || JSON.stringify(body.detail)
    } catch { detail = await res.text() }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export type RootCauseCategory =
  | 'HARDWARE_FAILURE' | 'SOFTWARE_BUG' | 'CONFIGURATION_ERROR'
  | 'CAPACITY_EXHAUSTION' | 'NETWORK_ISSUE' | 'DEPENDENCY_FAILURE'
  | 'HUMAN_ERROR' | 'UNKNOWN'

export interface RCAPayload {
  incident_start: string        // ISO datetime
  incident_end: string          // ISO datetime
  root_cause_category: RootCauseCategory
  root_cause_description: string
  fix_applied: string
  prevention_steps: string
  submitted_by?: string
}

export interface RCARecord {
  id: string
  work_item_id: string
  incident_start: string
  incident_end: string
  root_cause_category: string
  root_cause_description: string
  fix_applied: string
  prevention_steps: string
  submitted_by?: string
  mttr_seconds: number
  created_at: string
}

export interface RCASubmitResult {
  success: boolean
  rca: RCARecord
  mttr_seconds: number
  mttr_minutes: number
  message: string
}

export interface ObservabilitySnapshot {
  timestamp: string
  queue: { depth: number; capacity: number; utilization_pct: number }
  websocket: { connected_clients: number }
  signals: { total_ingested: number; last_window: number; window_seconds: number }
  work_items: {
    by_status: Record<string, number>
    open: number; investigating: number; resolved: number; closed: number
    total_rcas: number
  }
  mttr: Record<string, {
    avg_seconds: number; avg_minutes: number
    min_seconds: number; max_seconds: number; sample_count: number
  }>
  top_components_24h: Array<{ component_id: string; severity: string; signal_count: number }>
  throughput_history_30m: Array<{ minute: string; count: number }>
}

export const rcaApi = {
  submit: (workItemId: string, payload: RCAPayload) =>
    request<RCASubmitResult>(`/work-items/${workItemId}/rca`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  get: (workItemId: string) =>
    request<{ rca: RCARecord | null; work_item_id: string }>(
      `/work-items/${workItemId}/rca`
    ),

  list: (limit = 50) =>
    request<{ rcas: RCARecord[]; count: number }>(`/rcas?limit=${limit}`),
}

export const observabilityApi = {
  full: () => request<ObservabilitySnapshot>('/metrics/full'),
  throughput: (minutes = 30) =>
    request<{ history: Array<{ minute: string; count: number }>; minutes: number }>(
      `/metrics/throughput?minutes=${minutes}`
    ),
  mttr: () =>
    request<{ mttr_by_priority: Record<string, { avg_seconds: number; avg_minutes: number; sample_count: number }> }>(
      '/metrics/mttr'
    ),
}
