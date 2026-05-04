import { useState } from 'react'
import { signalApi } from '../services/api'
import { Zap, ChevronDown } from 'lucide-react'
import styles from './SignalTester.module.css'

const PRESETS = [
  { label: 'RDBMS Outage',    component_id: 'RDBMS_PRIMARY',    component_type: 'RDBMS',    severity: 'CRITICAL', message: 'Primary database connection refused' },
  { label: 'Cache Miss Spike', component_id: 'CACHE_CLUSTER_01', component_type: 'CACHE',    severity: 'HIGH',     message: 'Cache hit rate dropped below 10%' },
  { label: 'API Latency',      component_id: 'API_GATEWAY_01',   component_type: 'API',      severity: 'HIGH',     message: 'P99 latency exceeded 5000ms threshold' },
  { label: 'Queue Backlog',    component_id: 'ASYNC_QUEUE_01',   component_type: 'QUEUE',    severity: 'MEDIUM',   message: 'Queue depth exceeds 50,000 messages' },
  { label: 'MCP Host Down',    component_id: 'MCP_HOST_02',      component_type: 'MCP_HOST', severity: 'CRITICAL', message: 'MCP host health check failed' },
  { label: 'NoSQL Slow Query', component_id: 'NOSQL_CLUSTER_01', component_type: 'NOSQL',    severity: 'MEDIUM',   message: 'Query execution time > 10s' },
]

export function SignalTester() {
  const [selected, setSelected] = useState(0)
  const [sending, setSending] = useState(false)
  const [burst, setBurst] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const preset = PRESETS[selected]

  async function sendSignal() {
    setSending(true)
    setResult(null)
    try {
      if (burst) {
        // Send 10 rapid signals to the same component for debounce testing
        const promises = Array.from({ length: 10 }, (_, i) =>
          signalApi.ingest({ ...preset, message: `${preset.message} (burst ${i + 1})` })
        )
        await Promise.all(promises)
        setResult('✓ Burst of 10 signals sent')
      } else {
        const res = await signalApi.ingest(preset)
        setResult(`✓ Accepted: ${res.signal_id.slice(0, 8)}… queue=${res.queue_depth}`)
      }
    } catch (e) {
      setResult(`✗ ${e instanceof Error ? e.message : 'Error'}`)
    } finally {
      setSending(false)
      setTimeout(() => setResult(null), 4000)
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <Zap size={14} />
        <span className={styles.title}>Signal Tester</span>
      </div>

      <div className={styles.body}>
        <div className={styles.selectWrap}>
          <select
            className={styles.select}
            value={selected}
            onChange={e => setSelected(Number(e.target.value))}
          >
            {PRESETS.map((p, i) => (
              <option key={i} value={i}>{p.label}</option>
            ))}
          </select>
          <ChevronDown size={13} className={styles.chevron} />
        </div>

        <div className={styles.preview}>
          <span className={styles.previewKey}>component</span>
          <span className={styles.previewVal}>{preset.component_id}</span>
          <span className={styles.previewKey}>severity</span>
          <span className={styles.previewVal}>{preset.severity}</span>
        </div>

        <div className={styles.footer}>
          <label className={styles.burstLabel}>
            <input type="checkbox" checked={burst} onChange={e => setBurst(e.target.checked)} />
            Burst ×10
          </label>
          <button className={styles.sendBtn} onClick={sendSignal} disabled={sending}>
            {sending ? 'Sending…' : 'Fire Signal'}
          </button>
        </div>

        {result && (
          <p className={`${styles.result} ${result.startsWith('✗') ? styles.resultError : styles.resultOk}`}>
            {result}
          </p>
        )}
      </div>
    </div>
  )
}
