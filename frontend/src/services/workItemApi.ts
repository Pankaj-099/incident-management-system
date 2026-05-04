import { WorkItem, Signal } from '../types'

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
        : body.detail?.message || body.detail?.error || JSON.stringify(body.detail)
    } catch { detail = await res.text() }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export interface WorkItemsResponse { items: WorkItem[]; total: number; cached: boolean }
export interface WorkItemStats {
  by_status: Record<string, number>; by_priority: Record<string, number>
  total_open: number; total_investigating: number; total_resolved: number; total_closed: number
  cached: boolean
}
export interface TransitionOption { status: string; label: string; description: string }
export interface TransitionsResponse { work_item_id: string; current_status: string; transitions: TransitionOption[] }
export interface TransitionResult { success: boolean; work_item: WorkItem; message: string }

export const workItemApi = {
  list: (params?: { status?: string; priority?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.status)   q.set('status', params.status)
    if (params?.priority) q.set('priority', params.priority)
    if (params?.limit)    q.set('limit', String(params.limit))
    if (params?.offset)   q.set('offset', String(params.offset))
    const qs = q.toString()
    return request<WorkItemsResponse>(`/work-items${qs ? `?${qs}` : ''}`)
  },
  get:         (id: string) => request<WorkItem>(`/work-items/${id}`),
  stats:       ()           => request<WorkItemStats>('/work-items/stats'),
  signals:     (id: string) => request<{ work_item_id: string; signals: Signal[]; count: number }>(`/work-items/${id}/signals`),
  transitions: (id: string) => request<TransitionsResponse>(`/work-items/${id}/transitions`),
  transition:  (id: string, status: string, actor?: string) =>
    request<TransitionResult>(`/work-items/${id}/transition`, {
      method: 'PATCH',
      body: JSON.stringify({ status, actor }),
    }),
}
