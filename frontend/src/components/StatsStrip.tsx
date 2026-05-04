import { useEffect, useState } from 'react'
import { metricsApi } from '../services/api'
import { MetricsSnapshot } from '../types'
import styles from './StatsStrip.module.css'

export function StatsStrip() {
  const [m, setM] = useState<MetricsSnapshot | null>(null)

  useEffect(() => {
    const fetch = () => metricsApi.snapshot().then(setM).catch(() => {})
    fetch()
    const t = setInterval(fetch, 5000)
    return () => clearInterval(t)
  }, [])

  const stats = [
    { key: 'ingested',   label: 'Ingested',    val: m?.signals_total ?? '—',    mono: true  },
    { key: 'rate',       label: 'Rate / 5s',   val: m?.signals_per_window ?? '—', mono: true, accent: (m?.signals_per_window ?? 0) > 0 },
    { key: 'queue',      label: 'Queue',       val: m?.queue_depth_live ?? '—', mono: true, warn: (m?.queue_depth_live ?? 0) > 5000 },
    { key: 'open',       label: 'Open',        val: m?.work_items_open ?? '—',  mono: true, alert: (m?.work_items_open ?? 0) > 0 },
    { key: 'ws',         label: 'WS Clients',  val: m?.ws_connections ?? '—',   mono: true  },
  ]

  return (
    <div className={styles.strip}>
      {stats.map((s, i) => (
        <div key={s.key} className={`${styles.cell}
          ${s.alert ? styles.cellAlert : ''}
          ${s.warn  ? styles.cellWarn  : ''}
          ${s.accent ? styles.cellAccent : ''}`}
        >
          <span className={styles.cellLabel}>{s.label}</span>
          <span className={`${styles.cellVal} ${s.mono ? styles.mono : ''}`}>
            {typeof s.val === 'number' ? s.val.toLocaleString() : s.val}
          </span>
          {i < stats.length - 1 && <div className={styles.divider} />}
        </div>
      ))}
    </div>
  )
}
