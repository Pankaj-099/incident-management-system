import { useEffect, useState } from 'react'
import { WorkItem, Signal } from '../types'
import { workItemApi } from '../services/workItemApi'
import { StatusBadge, PriorityTag } from './StatusBadge'
import { SeverityBadge } from './SeverityBadge'
import { WorkflowPanel } from './WorkflowPanel'
import { RCAForm } from './RCAForm'
import { formatDistanceToNow, format } from 'date-fns'
import { X, Clock, Radio, AlertTriangle, GitBranch, FileText } from 'lucide-react'
import styles from './WorkItemDrawer.module.css'

interface Props {
  workItemId: string | null
  onClose: () => void
}

type Tab = 'workflow' | 'rca' | 'signals' | 'details'

export function WorkItemDrawer({ workItemId, onClose }: Props) {
  const [wi, setWi] = useState<WorkItem | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [loadingWi, setLoadingWi] = useState(false)
  const [loadingSig, setLoadingSig] = useState(false)
  const [activeTab, setActiveTab] = useState<Tab>('workflow')
  const [rcaSubmitted, setRcaSubmitted] = useState(false)

  useEffect(() => {
    if (!workItemId) { setWi(null); setSignals([]); return }
    setActiveTab('workflow')
    setRcaSubmitted(false)
    setLoadingWi(true)
    workItemApi.get(workItemId).then(setWi).finally(() => setLoadingWi(false))
    setLoadingSig(true)
    workItemApi.signals(workItemId).then(r => setSignals(r.signals)).finally(() => setLoadingSig(false))
  }, [workItemId])

  if (!workItemId) return null

  const tabs: { id: Tab; label: string; icon?: React.ReactNode }[] = [
    { id: 'workflow', label: 'Workflow',  icon: <GitBranch size={12} /> },
    { id: 'rca',      label: 'RCA',       icon: <FileText size={12} /> },
    { id: 'signals',  label: `Signals${signals.length > 0 ? ` (${signals.length})` : ''}` },
    { id: 'details',  label: 'Details' },
  ]

  return (
    <>
      <div className={styles.backdrop} onClick={onClose} />
      <aside className={styles.drawer}>
        <div className={styles.drawerHeader}>
          <button className={styles.closeBtn} onClick={onClose}><X size={16} /></button>
          {wi && (
            <div className={styles.wiMeta}>
              <div className={styles.wiTitleRow}>
                <PriorityTag priority={wi.priority} />
                <StatusBadge status={wi.status} />
              </div>
              <h2 className={styles.wiTitle}>{wi.title}</h2>
              <p className={styles.wiComponent}>{wi.component_id} · {wi.component_type}</p>
            </div>
          )}
          {loadingWi && <div className={styles.loadingBar} />}
        </div>

        {wi && (
          <div className={styles.wiStats}>
            <StatChip icon={<Radio size={12} />} label="Signals" value={wi.signal_count} />
            <StatChip icon={<Clock size={12} />} label="Age" value={formatDistanceToNow(new Date(wi.created_at))} />
            {wi.mttr_seconds != null && (
              <StatChip icon={<AlertTriangle size={12} />} label="MTTR" value={`${Math.round(wi.mttr_seconds / 60)}m`} />
            )}
          </div>
        )}

        <div className={styles.tabs}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.icon}
              {tab.label}
              {tab.id === 'rca' && rcaSubmitted && <span className={styles.tabDot} />}
            </button>
          ))}
        </div>

        <div className={styles.drawerBody}>
          {activeTab === 'workflow' && wi && (
            <div className={styles.tabPad}>
              <WorkflowPanel workItem={wi} onTransitioned={(updated) => setWi(updated)} />
            </div>
          )}

          {activeTab === 'rca' && wi && (
            <div className={styles.tabPad}>
              <RCAForm
                workItem={wi}
                onSubmitted={(mttr) => {
                  setRcaSubmitted(true)
                  setWi(prev => prev ? { ...prev, mttr_seconds: mttr * 60 } : prev)
                }}
              />
            </div>
          )}

          {activeTab === 'signals' && (
            loadingSig ? (
              <div className={styles.loading}>Loading signals…</div>
            ) : signals.length === 0 ? (
              <div className={styles.empty}>No signals linked yet</div>
            ) : (
              <div className={styles.signalList}>
                {signals.map(sig => (
                  <div key={sig.signal_id} className={styles.sigRow}>
                    <SeverityBadge severity={sig.severity} />
                    <div className={styles.sigContent}>
                      <p className={styles.sigMsg}>{sig.message}</p>
                      <p className={styles.sigTime}>
                        {sig.received_at ? format(new Date(sig.received_at), 'HH:mm:ss.SSS') : '—'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {activeTab === 'details' && wi && (
            <div className={styles.detailGrid}>
              <DetailRow label="Work Item ID" value={wi.id} mono />
              <DetailRow label="Component"    value={wi.component_id} />
              <DetailRow label="Type"         value={wi.component_type} />
              <DetailRow label="Status"       value={wi.status} />
              <DetailRow label="Priority"     value={wi.priority} />
              <DetailRow label="Signal Count" value={String(wi.signal_count)} />
              <DetailRow label="Created"      value={format(new Date(wi.created_at), 'MMM d, yyyy HH:mm:ss')} />
              {wi.resolved_at && <DetailRow label="Resolved" value={format(new Date(wi.resolved_at), 'MMM d, yyyy HH:mm:ss')} />}
              {wi.closed_at   && <DetailRow label="Closed"   value={format(new Date(wi.closed_at),   'MMM d, yyyy HH:mm:ss')} />}
              {wi.mttr_seconds != null && <DetailRow label="MTTR" value={`${Math.round(wi.mttr_seconds / 60)} minutes`} />}
              {wi.description && (
                <div className={styles.descRow}>
                  <span className={styles.detailLabel}>Description</span>
                  <p className={styles.detailDesc}>{wi.description}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

function StatChip({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className={styles.statChip}>
      {icon}
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
    </div>
  )
}

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className={styles.detailRow}>
      <span className={styles.detailLabel}>{label}</span>
      <span className={`${styles.detailValue} ${mono ? styles.mono : ''}`}>{value}</span>
    </div>
  )
}
