import { useEffect, useState, useCallback } from 'react'
import { observabilityApi, ObservabilitySnapshot } from '../services/rcaApi'
import { ThroughputChart } from '../components/ThroughputChart'
import { Activity, Database, Layers, Wifi, Clock, RefreshCw, BarChart2, AlertTriangle } from 'lucide-react'
import styles from './ObservabilityPage.module.css'

const PRIORITY_COLORS: Record<string, string> = {
  P0: 'var(--p0)', P1: 'var(--p1)', P2: 'var(--p2)', P3: 'var(--p3)',
}

const STATUS_COLORS: Record<string, string> = {
  OPEN: 'var(--color-open)', INVESTIGATING: 'var(--color-investigating)',
  RESOLVED: 'var(--color-resolved)', CLOSED: 'var(--color-closed)',
}

export default function ObservabilityPage() {
  const [snap, setSnap]             = useState<ObservabilitySnapshot | null>(null)
  const [loading, setLoading]       = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchSnap = useCallback(() => {
    setLoading(true)
    observabilityApi.full()
      .then(s => { setSnap(s); setLastUpdated(new Date()) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchSnap()
    const t = setInterval(fetchSnap, 10_000)
    return () => clearInterval(t)
  }, [fetchSnap])

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <BarChart2 size={16} />
          <h1 className={styles.title}>Observability</h1>
        </div>
        <div className={styles.headerRight}>
          {lastUpdated && (
            <span className={styles.lastUpdated}>
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button className={styles.refreshBtn} onClick={fetchSnap} disabled={loading}>
            <RefreshCw size={13} className={loading ? styles.spin : ''} />
            Refresh
          </button>
        </div>
      </div>

      {!snap ? (
        <div className={styles.skeletonGrid}>
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className={styles.skeleton} />)}
        </div>
      ) : (
        <>
          <div className={styles.statGrid}>
            <StatTile icon={<Activity size={15} />}  label="Total Signals"   value={snap.signals.total_ingested.toLocaleString()} />
            <StatTile icon={<Activity size={15} />}  label={`Rate/${snap.signals.window_seconds}s`} value={snap.signals.last_window} accent={snap.signals.last_window > 0} />
            <StatTile icon={<Layers size={15} />}    label="Queue Depth"     value={snap.queue.depth} accent={snap.queue.depth > 1000} sub={`${snap.queue.utilization_pct}%`} />
            <StatTile icon={<Wifi size={15} />}      label="WS Clients"      value={snap.websocket.connected_clients} />
            <StatTile icon={<Database size={15} />}  label="Open Incidents"  value={snap.work_items.open} accent={snap.work_items.open > 0} />
            <StatTile icon={<Clock size={15} />}     label="RCAs Filed"      value={snap.work_items.total_rcas} />
          </div>

          <div className={styles.gridTwo}>
            <section className={styles.card}>
              <h2 className={styles.cardTitle}><Layers size={13} /> Work Items by Status</h2>
              <div className={styles.statusBars}>
                {(['OPEN','INVESTIGATING','RESOLVED','CLOSED'] as const).map(s => {
                  const count = snap.work_items.by_status[s] || 0
                  const total = Object.values(snap.work_items.by_status).reduce((a, b) => a + b, 0)
                  const pct   = total > 0 ? Math.round(count / total * 100) : 0
                  return <StatusBar key={s} status={s} count={count} pct={pct} />
                })}
              </div>
            </section>

            <section className={styles.card}>
              <h2 className={styles.cardTitle}><Clock size={13} /> MTTR by Priority</h2>
              {Object.keys(snap.mttr).length === 0 ? (
                <p className={styles.emptyNote}>No MTTR data yet.</p>
              ) : (
                <div className={styles.mttrGrid}>
                  {Object.entries(snap.mttr).sort().map(([p, m]) => (
                    <div key={p} className={styles.mttrRow}>
                      <span className={styles.mttrPriority} style={{ color: PRIORITY_COLORS[p] }}>{p}</span>
                      <div className={styles.mttrBar}>
                        <div className={styles.mttrFill} style={{ width: `${Math.min(100, m.avg_minutes / 60 * 100)}%`, background: PRIORITY_COLORS[p] }} />
                      </div>
                      <span className={styles.mttrVal}>{m.avg_minutes}m</span>
                      <span className={styles.mttrSub}>n={m.sample_count}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className={styles.card} style={{ padding: 0 }}>
            <ThroughputChart />
          </div>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}><AlertTriangle size={13} /> Top Components — Signal Volume 24h</h2>
            {snap.top_components_24h.length === 0 ? (
              <p className={styles.emptyNote}>No signal data yet.</p>
            ) : (
              <ComponentTable rows={snap.top_components_24h} />
            )}
          </section>
        </>
      )}
    </div>
  )
}

function StatTile({ icon, label, value, sub, accent = false }: {
  icon: React.ReactNode; label: string; value: string | number; sub?: string; accent?: boolean
}) {
  return (
    <div className={`${styles.tile} ${accent ? styles.tileAccent : ''}`}>
      <div className={styles.tileIcon}>{icon}</div>
      <div>
        <p className={styles.tileValue}>{typeof value === 'number' ? value.toLocaleString() : value}</p>
        <p className={styles.tileLabel}>{label}</p>
        {sub && <p className={styles.tileSub}>{sub}</p>}
      </div>
    </div>
  )
}

function StatusBar({ status, count, pct }: { status: string; count: number; pct: number }) {
  return (
    <div className={styles.statusBarRow}>
      <span className={styles.statusBarLabel}>{status}</span>
      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{ width: `${pct}%`, background: STATUS_COLORS[status] }} />
      </div>
      <span className={styles.statusBarCount}>{count}</span>
    </div>
  )
}

function ComponentTable({ rows }: { rows: Array<{ component_id: string; severity: string; signal_count: number }> }) {
  const maxCount = Math.max(...rows.map(r => r.signal_count), 1)
  const SEV_COLOR: Record<string, string> = {
    CRITICAL: 'var(--p0)', HIGH: 'var(--p1)', MEDIUM: 'var(--p2)',
    LOW: 'var(--p3)', INFO: 'var(--text-muted)',
  }
  return (
    <div className={styles.compTable}>
      {rows.map((r, i) => (
        <div key={i} className={styles.compRow}>
          <span className={styles.compId}>{r.component_id}</span>
          <span className={styles.compSev} style={{ color: SEV_COLOR[r.severity] || 'var(--text-muted)' }}>{r.severity}</span>
          <div className={styles.compBarTrack}>
            <div className={styles.compBarFill} style={{ width: `${(r.signal_count / maxCount) * 100}%` }} />
          </div>
          <span className={styles.compCount}>{r.signal_count}</span>
        </div>
      ))}
    </div>
  )
}
