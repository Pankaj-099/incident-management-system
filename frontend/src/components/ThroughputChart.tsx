import { useEffect, useState, useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { observabilityApi } from '../services/rcaApi'
import { Activity, RefreshCw } from 'lucide-react'
import styles from './ThroughputChart.module.css'

interface DataPoint { minute: string; count: number; label: string }

function formatMinute(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipTime}>{label}</p>
      <p className={styles.tooltipVal}>{payload[0].value} <span>signals</span></p>
    </div>
  )
}

export function ThroughputChart() {
  const [data, setData] = useState<DataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [peak, setPeak] = useState(0)
  const [total, setTotal] = useState(0)

  const fetchData = useCallback(() => {
    observabilityApi.throughput(30)
      .then(r => {
        const pts: DataPoint[] = r.history.map(h => ({
          minute: h.minute,
          count: h.count,
          label: formatMinute(h.minute),
        }))
        setData(pts)
        setPeak(Math.max(...pts.map(p => p.count), 0))
        setTotal(pts.reduce((s, p) => s + p.count, 0))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchData()
    const t = setInterval(fetchData, 10_000)
    return () => clearInterval(t)
  }, [fetchData])

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <Activity size={13} className={styles.titleIcon} />
          <span className={styles.title}>Signal Throughput</span>
          <span className={styles.subtitle}>30-minute window</span>
        </div>
        <div className={styles.stats}>
          <div className={styles.stat}>
            <span className={styles.statVal}>{total.toLocaleString()}</span>
            <span className={styles.statLabel}>total</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.stat}>
            <span className={styles.statVal}>{peak.toLocaleString()}</span>
            <span className={styles.statLabel}>peak/min</span>
          </div>
          <button className={styles.refreshBtn} onClick={fetchData}>
            <RefreshCw size={11} className={loading ? styles.spin : ''} />
          </button>
        </div>
      </div>

      <div className={styles.chartWrap}>
        {loading && data.length === 0 ? (
          <div className={styles.loading}>
            <div className={styles.loadingBars}>
              {Array.from({ length: 30 }).map((_, i) => (
                <div key={i} className={styles.loadBar}
                  style={{ height: `${Math.random() * 60 + 10}%`, animationDelay: `${i * 50}ms` }} />
              ))}
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={data} margin={{ top: 4, right: 0, left: -24, bottom: 0 }}>
              <defs>
                <linearGradient id="throughputGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f0f0f0" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#f0f0f0" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="2 4"
                stroke="rgba(255,255,255,0.04)"
                horizontal={true}
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fill: '#444', fontSize: 9, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                axisLine={false}
                interval={4}
              />
              <YAxis
                tick={{ fill: '#444', fontSize: 9, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#f0f0f0"
                strokeWidth={1.5}
                fill="url(#throughputGrad)"
                dot={false}
                activeDot={{ r: 3, fill: '#f0f0f0', strokeWidth: 0 }}
                animationDuration={400}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
