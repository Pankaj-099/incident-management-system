import { useState, useEffect } from 'react'
import { Signal } from '../types'
import { signalApi } from '../services/api'
import { SeverityBadge } from './SeverityBadge'
import { formatDistanceToNow } from 'date-fns'
import { Radio, RefreshCw } from 'lucide-react'
import styles from './SignalFeed.module.css'

const MAX_SIGNALS = 200

interface Props {
  externalSignals?: Signal[]
}

export function SignalFeed({ externalSignals = [] }: Props) {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [paused, setPaused]   = useState(false)
  const pausedRef = { current: paused }
  pausedRef.current = paused

  useEffect(() => {
    signalApi.recent(100)
      .then(({ signals: s }) => setSignals(s))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // Receive external signals from parent event bus
  useEffect(() => {
    if (!externalSignals.length || pausedRef.current) return
    // Only add the latest external signal (avoid re-processing the whole array)
    const latest = externalSignals[0]
    if (!latest) return
    setSignals(prev => {
      if (prev[0]?.signal_id === latest.signal_id) return prev
      return [latest, ...prev].slice(0, MAX_SIGNALS)
    })
  }, [externalSignals])

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <Radio size={14} />
          <span className={styles.title}>Live Signal Feed</span>
        </div>
        <div className={styles.controls}>
          <span className={styles.count}>{signals.length} signals</span>
          <button
            className={`${styles.btn} ${paused ? styles.btnActive : ''}`}
            onClick={() => setPaused(p => !p)}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            className={styles.btn}
            onClick={() => {
              setLoading(true)
              signalApi.recent(100).then(({ signals: s }) => {
                setSignals(s)
                setLoading(false)
              })
            }}
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      <div className={styles.feed}>
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => <div key={i} className={styles.skeleton} />)
        ) : signals.length === 0 ? (
          <div className={styles.empty}>
            <p>No signals yet. Send a POST to <code>/ingest</code> to start.</p>
          </div>
        ) : (
          signals.map((sig, idx) => (
            <SignalRow key={sig.signal_id} signal={sig} isNew={idx === 0 && !loading} />
          ))
        )}
      </div>
    </div>
  )
}

function SignalRow({ signal, isNew }: { signal: Signal; isNew: boolean }) {
  const time = (() => {
    try { return formatDistanceToNow(new Date(signal.received_at), { addSuffix: true }) }
    catch { return '—' }
  })()
  return (
    <div className={`${styles.row} ${isNew ? styles.rowNew : ''}`}>
      <SeverityBadge severity={signal.severity} />
      <span className={styles.componentId}>{signal.component_id}</span>
      <span className={styles.message}>{signal.message}</span>
      <span className={styles.time}>{time}</span>
    </div>
  )
}
