import { WorkItemStatus, Priority } from '../types'
import styles from './StatusBadge.module.css'

const STATUS_CONFIG: Record<WorkItemStatus, { label: string; cls: string }> = {
  OPEN:          { label: 'Open',          cls: styles.open },
  INVESTIGATING: { label: 'Investigating', cls: styles.investigating },
  RESOLVED:      { label: 'Resolved',      cls: styles.resolved },
  CLOSED:        { label: 'Closed',        cls: styles.closed },
}

const PRIORITY_CONFIG: Record<Priority, { cls: string }> = {
  P0: { cls: styles.p0 },
  P1: { cls: styles.p1 },
  P2: { cls: styles.p2 },
  P3: { cls: styles.p3 },
}

export function StatusBadge({ status }: { status: WorkItemStatus }) {
  const cfg = STATUS_CONFIG[status]
  return <span className={`${styles.badge} ${cfg.cls}`}>{cfg.label}</span>
}

export function PriorityTag({ priority }: { priority: Priority }) {
  const cfg = PRIORITY_CONFIG[priority]
  return <span className={`${styles.priority} ${cfg.cls}`}>{priority}</span>
}
