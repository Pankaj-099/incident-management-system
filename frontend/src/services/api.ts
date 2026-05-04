import { Signal, MetricsSnapshot } from '../types'

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
    const body = await res.text()
    throw new ApiError(res.status, body)
  }
  return res.json() as Promise<T>
}

export interface HealthComponent {
  status: 'healthy' | 'unhealthy'
  error?: string
}

export interface HealthResponse {
  status: 'healthy' | 'degraded'
  version: string
  env: string
  uptime_seconds: number
  components: {
    postgres?: HealthComponent
    redis?: HealthComponent
    sqlite?: HealthComponent
  }
}

export const healthApi = {
  check: () => request<HealthResponse>('/health'),
  ping: () => request<{ ping: string }>('/health/ping'),
}

export const signalApi = {
  recent: (limit = 100) =>
    request<{ signals: Signal[]; count: number }>(`/signals/recent?limit=${limit}`),
  ingest: (payload: {
    component_id: string
    component_type?: string
    severity?: string
    message: string
    payload?: Record<string, unknown>
  }) =>
    request<{ accepted: boolean; signal_id: string; queue_depth: number }>('/ingest', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}

export const metricsApi = {
  snapshot: () => request<MetricsSnapshot>('/metrics'),
}
