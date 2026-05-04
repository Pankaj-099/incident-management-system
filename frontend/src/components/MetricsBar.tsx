import { useEffect, useState } from 'react'
import { metricsApi } from '../services/api'
import { MetricsSnapshot } from '../types'
import { Activity, Database, Layers, Wifi } from 'lucide-react'
import styles from './MetricsBar.module.css'

export function MetricsBar() {
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null)

  useEffect(() => {
    const fetch = () =>
      metricsApi.snapshot().then(setMetrics).catch(() => {})
    fetch()
    const t = setInterval(fetch, 5000)
    return () => clearInterval(t)
  }, [])

  if (!metrics) return <div className={styles.bar}><span className={styles.loading}>Loading metrics…</span></div>

  return (
    <div className={styles.bar}>
      <MetricTile icon={<Activity size={13} />} label="Signals / 5s" value={metrics.signals_per_window} />
      <MetricTile icon={<Database size={13} />} label="Total Signals" value={metrics.signals_total.toLocaleString()} />
      <MetricTile icon={<Layers size={13} />} label="Queue Depth" value={metrics.queue_depth_live} accent={metrics.queue_depth_live > 1000} />
      <MetricTile icon={<Wifi size={13} />} label="WS Clients" value={metrics.ws_connections} />
      <MetricTile icon={<Activity size={13} />} label="Open Incidents" value={metrics.work_items_open} accent={metrics.work_items_open > 0} />
    </div>
  )
}

function MetricTile({
  icon,
  label,
  value,
  accent = false,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  accent?: boolean
}) {
  return (
    <div className={`${styles.tile} ${accent ? styles.tileAccent : ''}`}>
      <span className={styles.tileIcon}>{icon}</span>
      <div>
        <p className={styles.tileValue}>{value}</p>
        <p className={styles.tileLabel}>{label}</p>
      </div>
    </div>
  )
}
