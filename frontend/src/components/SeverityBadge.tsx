import { Severity } from '../types'
import styles from './SeverityBadge.module.css'

const SEVERITY_CONFIG: Record<Severity, { label: string; cls: string }> = {
  CRITICAL: { label: 'CRIT',   cls: styles.critical },
  HIGH:     { label: 'HIGH',   cls: styles.high },
  MEDIUM:   { label: 'MED',    cls: styles.medium },
  LOW:      { label: 'LOW',    cls: styles.low },
  INFO:     { label: 'INFO',   cls: styles.info },
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const cfg = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.INFO
  return <span className={`${styles.badge} ${cfg.cls}`}>{cfg.label}</span>
}
