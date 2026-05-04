export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
export type ComponentType = 'RDBMS' | 'NOSQL' | 'CACHE' | 'API' | 'QUEUE' | 'MCP_HOST'
export type WorkItemStatus = 'OPEN' | 'INVESTIGATING' | 'RESOLVED' | 'CLOSED'
export type Priority = 'P0' | 'P1' | 'P2' | 'P3'

export interface Signal {
  signal_id: string
  component_id: string
  component_type: ComponentType
  severity: Severity
  message: string
  payload?: Record<string, unknown>
  work_item_id?: string
  received_at: string
}

export interface WorkItem {
  id: string
  component_id: string
  component_type: string
  status: WorkItemStatus
  priority: Priority
  title: string
  description?: string
  signal_count: number
  mttr_seconds?: number
  created_at: string
  updated_at: string
  resolved_at?: string
  closed_at?: string
}

export interface MetricsSnapshot {
  signals_total: number
  signals_per_window: number
  work_items_open: number
  queue_depth: number
  queue_depth_live: number
  ws_connections: number
  timestamp: number
}

export type WsEvent =
  | { type: 'signal'; data: Signal }
  | { type: 'work_item_created'; data: WorkItem }
  | { type: 'work_item_updated'; data: WorkItem }
