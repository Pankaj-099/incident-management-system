import { useState, useEffect } from 'react'
import { WorkItem } from '../types'
import { workItemApi, TransitionOption, ApiError } from '../services/workItemApi'
import { ArrowRight, Lock, AlertTriangle, CheckCircle, Loader } from 'lucide-react'
import styles from './WorkflowPanel.module.css'

interface Props {
  workItem: WorkItem
  onTransitioned: (updated: WorkItem) => void
}

const STATUS_FLOW = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']

const STATUS_COLORS: Record<string, string> = {
  OPEN:          'var(--color-open)',
  INVESTIGATING: 'var(--color-investigating)',
  RESOLVED:      'var(--color-resolved)',
  CLOSED:        'var(--color-closed)',
}

export function WorkflowPanel({ workItem, onTransitioned }: Props) {
  const [transitions, setTransitions] = useState<TransitionOption[]>([])
  const [loading, setLoading] = useState(true)
  const [transitioning, setTransitioning] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    workItemApi.transitions(workItem.id)
      .then(r => setTransitions(r.transitions))
      .catch(() => setTransitions([]))
      .finally(() => setLoading(false))
  }, [workItem.id, workItem.status])

  async function handleTransition(targetStatus: string) {
    setTransitioning(targetStatus)
    setError(null)
    setSuccess(null)
    try {
      const result = await workItemApi.transition(workItem.id, targetStatus)
      setSuccess(result.message)
      onTransitioned(result.work_item)
      setTimeout(() => setSuccess(null), 3000)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Transition failed'
      setError(msg)
    } finally {
      setTransitioning(null)
    }
  }

  const currentIdx = STATUS_FLOW.indexOf(workItem.status)

  return (
    <div className={styles.panel}>
      {/* Flow tracker */}
      <div className={styles.flowTracker}>
        {STATUS_FLOW.map((s, i) => {
          const isPast    = i < currentIdx
          const isCurrent = i === currentIdx
          const isFuture  = i > currentIdx
          return (
            <div key={s} className={styles.flowStep}>
              <div
                className={`${styles.flowDot}
                  ${isCurrent ? styles.dotCurrent : ''}
                  ${isPast    ? styles.dotPast    : ''}
                  ${isFuture  ? styles.dotFuture  : ''}`}
                style={isCurrent ? { background: STATUS_COLORS[s], boxShadow: `0 0 10px ${STATUS_COLORS[s]}66` } : {}}
              >
                {isPast && <CheckCircle size={10} />}
              </div>
              <span
                className={`${styles.flowLabel}
                  ${isCurrent ? styles.labelCurrent : ''}
                  ${isPast    ? styles.labelPast    : ''}`}
              >
                {s}
              </span>
              {i < STATUS_FLOW.length - 1 && (
                <div className={`${styles.flowLine} ${isPast ? styles.lineFilled : ''}`} />
              )}
            </div>
          )
        })}
      </div>

      {/* Transition buttons */}
      <div className={styles.actions}>
        {loading ? (
          <div className={styles.loadingRow}>
            <Loader size={14} className={styles.spin} />
            <span>Loading transitions…</span>
          </div>
        ) : transitions.length === 0 ? (
          <div className={styles.terminal}>
            <Lock size={14} />
            <span>
              {workItem.status === 'CLOSED'
                ? 'This incident is closed — no further transitions.'
                : 'No transitions available from current state.'}
            </span>
          </div>
        ) : (
          transitions.map(t => (
            <TransitionButton
              key={t.status}
              option={t}
              isClosed={t.status === 'CLOSED'}
              loading={transitioning === t.status}
              disabled={transitioning !== null}
              onClick={() => handleTransition(t.status)}
            />
          ))
        )}
      </div>

      {/* Feedback messages */}
      {error && (
        <div className={styles.errorMsg}>
          <AlertTriangle size={13} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className={styles.successMsg}>
          <CheckCircle size={13} />
          <span>{success}</span>
        </div>
      )}

      {/* RCA hint for RESOLVED state */}
      {workItem.status === 'RESOLVED' && (
        <div className={styles.rcaHint}>
          <AlertTriangle size={12} />
          <span>RCA must be submitted before closing this incident.</span>
        </div>
      )}
    </div>
  )
}

function TransitionButton({
  option, isClosed, loading, disabled, onClick,
}: {
  option: TransitionOption
  isClosed: boolean
  loading: boolean
  disabled: boolean
  onClick: () => void
}) {
  return (
    <button
      className={`${styles.transitionBtn} ${isClosed ? styles.btnClosed : styles.btnPrimary}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className={styles.btnContent}>
        <span className={styles.btnLabel}>
          {loading ? <Loader size={13} className={styles.spin} /> : <ArrowRight size={13} />}
          {option.label}
        </span>
        <span className={styles.btnDesc}>{option.description}</span>
      </span>
    </button>
  )
}
