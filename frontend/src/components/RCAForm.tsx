import { useState, useEffect } from 'react'
import { WorkItem } from '../types'
import { rcaApi, RCAPayload, RCARecord, RootCauseCategory, ApiError } from '../services/rcaApi'
import { CheckCircle, AlertTriangle, Clock, FileText, Loader } from 'lucide-react'
import styles from './RCAForm.module.css'

interface Props {
  workItem: WorkItem
  onSubmitted: (mttrMinutes: number) => void
}

const ROOT_CAUSE_OPTIONS: { value: RootCauseCategory; label: string }[] = [
  { value: 'SOFTWARE_BUG',          label: 'Software Bug' },
  { value: 'CONFIGURATION_ERROR',   label: 'Configuration Error' },
  { value: 'HARDWARE_FAILURE',      label: 'Hardware Failure' },
  { value: 'CAPACITY_EXHAUSTION',   label: 'Capacity Exhaustion' },
  { value: 'NETWORK_ISSUE',         label: 'Network Issue' },
  { value: 'DEPENDENCY_FAILURE',    label: 'Dependency Failure' },
  { value: 'HUMAN_ERROR',           label: 'Human Error' },
  { value: 'UNKNOWN',               label: 'Unknown' },
]

function toLocalDatetimeValue(iso: string): string {
  // Convert ISO to datetime-local input value format
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function toISOFromLocal(localVal: string): string {
  return new Date(localVal).toISOString()
}

export function RCAForm({ workItem, onSubmitted }: Props) {
  const [existingRca, setExistingRca] = useState<RCARecord | null>(null)
  const [loading, setLoading]   = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess]   = useState<{ mttr: number } | null>(null)
  const [error, setError]       = useState<string | null>(null)

  // Default incident_start from WI created_at, incident_end = now
  const defaultStart = toLocalDatetimeValue(workItem.created_at)
  const defaultEnd   = toLocalDatetimeValue(new Date().toISOString())

  const [form, setForm] = useState<{
    incident_start: string
    incident_end: string
    root_cause_category: RootCauseCategory
    root_cause_description: string
    fix_applied: string
    prevention_steps: string
    submitted_by: string
  }>({
    incident_start: defaultStart,
    incident_end: defaultEnd,
    root_cause_category: 'SOFTWARE_BUG',
    root_cause_description: '',
    fix_applied: '',
    prevention_steps: '',
    submitted_by: '',
  })

  // Load existing RCA if any
  useEffect(() => {
    rcaApi.get(workItem.id).then(r => {
      if (r.rca) {
        setExistingRca(r.rca)
        setForm(f => ({
          ...f,
          incident_start:         toLocalDatetimeValue(r.rca!.incident_start),
          incident_end:           toLocalDatetimeValue(r.rca!.incident_end),
          root_cause_category:    r.rca!.root_cause_category as RootCauseCategory,
          root_cause_description: r.rca!.root_cause_description,
          fix_applied:            r.rca!.fix_applied,
          prevention_steps:       r.rca!.prevention_steps,
          submitted_by:           r.rca!.submitted_by || '',
        }))
      }
    }).catch(() => {}).finally(() => setLoading(false))
  }, [workItem.id])

  function set(key: keyof typeof form, val: string) {
    setForm(f => ({ ...f, [key]: val }))
    setError(null)
  }

  // Live MTTR preview
  const mttrPreview = (() => {
    try {
      const start = new Date(form.incident_start).getTime()
      const end   = new Date(form.incident_end).getTime()
      const diff  = (end - start) / 1000
      if (diff <= 0) return null
      const h = Math.floor(diff / 3600)
      const m = Math.floor((diff % 3600) / 60)
      return h > 0 ? `${h}h ${m}m` : `${m}m`
    } catch { return null }
  })()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    const payload: RCAPayload = {
      incident_start:         toISOFromLocal(form.incident_start),
      incident_end:           toISOFromLocal(form.incident_end),
      root_cause_category:    form.root_cause_category,
      root_cause_description: form.root_cause_description.trim(),
      fix_applied:            form.fix_applied.trim(),
      prevention_steps:       form.prevention_steps.trim(),
      submitted_by:           form.submitted_by.trim() || undefined,
    }

    try {
      const result = await rcaApi.submit(workItem.id, payload)
      setSuccess({ mttr: result.mttr_minutes })
      setExistingRca(result.rca)
      onSubmitted(result.mttr_minutes)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <div className={styles.loading}><Loader size={16} className={styles.spin} /> Loading…</div>
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {existingRca && !success && (
        <div className={styles.existingBanner}>
          <FileText size={13} />
          <span>RCA previously submitted — re-submitting will replace it.</span>
        </div>
      )}

      {success && (
        <div className={styles.successBanner}>
          <CheckCircle size={15} />
          <div>
            <p className={styles.successTitle}>RCA submitted successfully</p>
            <p className={styles.successSub}>MTTR: <strong>{success.mttr} minutes</strong> — you can now close this incident.</p>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>
          <Clock size={13} /> Incident Timeline
        </h3>
        <div className={styles.timeRow}>
          <div className={styles.field}>
            <label className={styles.label}>Incident Start</label>
            <input
              type="datetime-local"
              className={styles.input}
              value={form.incident_start}
              onChange={e => set('incident_start', e.target.value)}
              required
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Incident End</label>
            <input
              type="datetime-local"
              className={styles.input}
              value={form.incident_end}
              onChange={e => set('incident_end', e.target.value)}
              required
            />
          </div>
        </div>
        {mttrPreview && (
          <div className={styles.mttrPreview}>
            <Clock size={11} />
            MTTR preview: <strong>{mttrPreview}</strong>
          </div>
        )}
      </div>

      {/* Root cause */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>
          <AlertTriangle size={13} /> Root Cause
        </h3>

        <div className={styles.field}>
          <label className={styles.label}>Category</label>
          <div className={styles.selectWrap}>
            <select
              className={styles.select}
              value={form.root_cause_category}
              onChange={e => set('root_cause_category', e.target.value as RootCauseCategory)}
            >
              {ROOT_CAUSE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className={styles.field}>
          <label className={styles.label}>
            Root Cause Description
            <span className={styles.required}>*</span>
            <span className={styles.minLen}>min 20 chars</span>
          </label>
          <textarea
            className={styles.textarea}
            rows={3}
            placeholder="Describe what caused the incident in detail…"
            value={form.root_cause_description}
            onChange={e => set('root_cause_description', e.target.value)}
            required
            minLength={20}
          />
          <CharCount val={form.root_cause_description} min={20} />
        </div>
      </div>

      {/* Resolution */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>
          <CheckCircle size={13} /> Resolution
        </h3>

        <div className={styles.field}>
          <label className={styles.label}>
            Fix Applied <span className={styles.required}>*</span>
            <span className={styles.minLen}>min 10 chars</span>
          </label>
          <textarea
            className={styles.textarea}
            rows={3}
            placeholder="What was done to resolve the incident?"
            value={form.fix_applied}
            onChange={e => set('fix_applied', e.target.value)}
            required
            minLength={10}
          />
          <CharCount val={form.fix_applied} min={10} />
        </div>

        <div className={styles.field}>
          <label className={styles.label}>
            Prevention Steps <span className={styles.required}>*</span>
            <span className={styles.minLen}>min 10 chars</span>
          </label>
          <textarea
            className={styles.textarea}
            rows={3}
            placeholder="How will you prevent this from happening again?"
            value={form.prevention_steps}
            onChange={e => set('prevention_steps', e.target.value)}
            required
            minLength={10}
          />
          <CharCount val={form.prevention_steps} min={10} />
        </div>
      </div>

      {/* Author */}
      <div className={styles.field}>
        <label className={styles.label}>Submitted By <span className={styles.optional}>(optional)</span></label>
        <input
          type="text"
          className={styles.input}
          placeholder="e.g. jane.doe"
          value={form.submitted_by}
          onChange={e => set('submitted_by', e.target.value)}
        />
      </div>

      {error && (
        <div className={styles.errorBanner}>
          <AlertTriangle size={13} />
          <span>{error}</span>
        </div>
      )}

      <button type="submit" className={styles.submitBtn} disabled={submitting}>
        {submitting
          ? <><Loader size={14} className={styles.spin} /> Submitting…</>
          : existingRca
          ? 'Re-submit RCA'
          : 'Submit RCA'
        }
      </button>
    </form>
  )
}

function CharCount({ val, min }: { val: string; min: number }) {
  const len = val.trim().length
  const ok  = len >= min
  return (
    <span className={`${styles.charCount} ${ok ? styles.charOk : styles.charWarn}`}>
      {len} / {min} min
    </span>
  )
}
