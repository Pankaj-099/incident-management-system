import { useEffect, useState, useCallback } from 'react'
import { healthApi, HealthResponse } from '../services/api'
import { CheckCircle, XCircle, RefreshCw, Clock, Server } from 'lucide-react'
import styles from './HealthPage.module.css'

type ComponentStatus = 'healthy' | 'unhealthy' | 'unknown'

function StatusDot({ status }: { status: ComponentStatus }) {
  return (
    <span
      className={`${styles.dot} ${
        status === 'healthy'
          ? styles.dotGreen
          : status === 'unhealthy'
          ? styles.dotRed
          : styles.dotGray
      }`}
    />
  )
}

function ComponentCard({
  name,
  status,
  error,
}: {
  name: string
  status: ComponentStatus
  error?: string
}) {
  return (
    <div className={`${styles.card} ${status === 'unhealthy' ? styles.cardError : ''}`}>
      <div className={styles.cardHeader}>
        <StatusDot status={status} />
        <span className={styles.cardName}>{name}</span>
        <span
          className={`${styles.badge} ${
            status === 'healthy'
              ? styles.badgeGreen
              : status === 'unhealthy'
              ? styles.badgeRed
              : styles.badgeGray
          }`}
        >
          {status}
        </span>
      </div>
      {error && <p className={styles.cardError}>{error}</p>}
    </div>
  )
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const fetchHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await healthApi.check()
      setHealth(data)
      setLastChecked(new Date())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to reach backend')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const timer = setInterval(fetchHealth, 15_000)
    return () => clearInterval(timer)
  }, [fetchHealth])

  const components = health
    ? [
        { name: 'PostgreSQL', key: 'postgres' as const },
        { name: 'Redis', key: 'redis' as const },
        { name: 'SQLite', key: 'sqlite' as const },
      ]
    : []

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <Server size={18} />
          <h1 className={styles.title}>System Health</h1>
        </div>
        <button className={styles.refreshBtn} onClick={fetchHealth} disabled={loading}>
          <RefreshCw size={14} className={loading ? styles.spin : ''} />
          Refresh
        </button>
      </div>

      {lastChecked && (
        <p className={styles.lastChecked}>
          <Clock size={12} />
          Last checked {lastChecked.toLocaleTimeString()} — auto-refreshes every 15s
        </p>
      )}

      {error ? (
        <div className={styles.errorBanner}>
          <XCircle size={16} />
          <span>{error}</span>
        </div>
      ) : health ? (
        <>
          <div
            className={`${styles.overallStatus} ${
              health.status === 'healthy' ? styles.overallGreen : styles.overallYellow
            }`}
          >
            {health.status === 'healthy' ? (
              <CheckCircle size={20} />
            ) : (
              <XCircle size={20} />
            )}
            <div>
              <p className={styles.overallLabel}>Overall Status</p>
              <p className={styles.overallValue}>{health.status.toUpperCase()}</p>
            </div>
            <div className={styles.overallMeta}>
              <span>v{health.version}</span>
              <span>{health.env}</span>
              <span>up {Math.floor(health.uptime_seconds / 60)}m {Math.floor(health.uptime_seconds % 60)}s</span>
            </div>
          </div>

          <div className={styles.grid}>
            {components.map(({ name, key }) => {
              const comp = health.components[key]
              return (
                <ComponentCard
                  key={key}
                  name={name}
                  status={comp?.status ?? 'unknown'}
                  error={comp?.error}
                />
              )
            })}
          </div>
        </>
      ) : (
        <div className={styles.skeleton}>
          {[0, 1, 2].map((i) => (
            <div key={i} className={styles.skeletonCard} />
          ))}
        </div>
      )}
    </div>
  )
}
