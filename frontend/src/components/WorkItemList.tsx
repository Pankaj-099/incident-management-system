import { useState, useEffect, useCallback } from 'react'
import { WorkItem } from '../types'
import { workItemApi } from '../services/workItemApi'
import { StatusBadge, PriorityTag } from './StatusBadge'
import { WorkItemDrawer } from './WorkItemDrawer'
import { formatDistanceToNow } from 'date-fns'
import { Layers, RefreshCw, ChevronRight, AlertTriangle } from 'lucide-react'
import styles from './WorkItemList.module.css'

const PRIORITY_ORDER: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3 }

function sortByPriority(items: WorkItem[]): WorkItem[] {
  return [...items].sort((a, b) => {
    const pd = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
    if (pd !== 0) return pd
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
}

const STATUS_FILTERS = ['ALL', 'OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED'] as const
type FilterStatus = typeof STATUS_FILTERS[number]

interface Props {
  externalNewItems?: WorkItem[]
  externalUpdatedItems?: WorkItem[]
}

export function WorkItemList({ externalNewItems = [], externalUpdatedItems = [] }: Props) {
  const [items, setItems]       = useState<WorkItem[]>([])
  const [loading, setLoading]   = useState(true)
  const [filter, setFilter]     = useState<FilterStatus>('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [newIds, setNewIds]     = useState<Set<string>>(new Set())

  const fetchItems = useCallback(() => {
    setLoading(true)
    const params = filter !== 'ALL' ? { status: filter } : undefined
    workItemApi.list(params)
      .then(r => setItems(sortByPriority(r.items)))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filter])

  useEffect(() => { fetchItems() }, [fetchItems])

  // Auto-refresh every 15s
  useEffect(() => {
    const t = setInterval(fetchItems, 15_000)
    return () => clearInterval(t)
  }, [fetchItems])

  // Handle external new work items from WebSocket
  useEffect(() => {
    if (!externalNewItems.length) return
    externalNewItems.forEach(wi => {
      setItems(prev => {
        if (prev.find(p => p.id === wi.id)) return prev
        return sortByPriority([wi, ...prev])
      })
      setNewIds(prev => new Set([...prev, wi.id]))
      setTimeout(() => setNewIds(prev => { const s = new Set(prev); s.delete(wi.id); return s }), 3000)
    })
  }, [externalNewItems])

  // Handle external updated work items from WebSocket
  useEffect(() => {
    if (!externalUpdatedItems.length) return
    externalUpdatedItems.forEach(wi => {
      setItems(prev => sortByPriority(prev.map(p => p.id === wi.id ? wi : p)))
    })
  }, [externalUpdatedItems])

  const displayed = filter === 'ALL' ? items : items.filter(w => w.status === filter)
  const p0Count   = items.filter(w => w.priority === 'P0' && w.status !== 'CLOSED').length

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <Layers size={14} />
          <span className={styles.title}>Work Items</span>
          {p0Count > 0 && (
            <span className={styles.critAlert}>
              <AlertTriangle size={11} />
              {p0Count} P0
            </span>
          )}
        </div>
        <div className={styles.controls}>
          <div className={styles.filterTabs}>
            {STATUS_FILTERS.map(s => (
              <button
                key={s}
                className={`${styles.filterTab} ${filter === s ? styles.filterActive : ''}`}
                onClick={() => setFilter(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <button className={styles.refreshBtn} onClick={fetchItems} disabled={loading}>
            <RefreshCw size={12} className={loading ? styles.spin : ''} />
          </button>
        </div>
      </div>

      <div className={styles.tableWrap}>
        {loading && items.length === 0 ? (
          <div className={styles.skeletons}>
            {Array.from({ length: 5 }).map((_, i) => <div key={i} className={styles.skeleton} />)}
          </div>
        ) : displayed.length === 0 ? (
          <div className={styles.empty}>
            <Layers size={24} strokeWidth={1.5} />
            <p>No {filter !== 'ALL' ? filter.toLowerCase() : ''} work items</p>
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Priority</th><th>Component</th><th>Title</th>
                <th>Status</th><th>Signals</th><th>Age</th><th></th>
              </tr>
            </thead>
            <tbody>
              {displayed.map(wi => (
                <WorkItemRow
                  key={wi.id}
                  wi={wi}
                  isNew={newIds.has(wi.id)}
                  isSelected={selectedId === wi.id}
                  onClick={() => setSelectedId(wi.id === selectedId ? null : wi.id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <WorkItemDrawer workItemId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  )
}

function WorkItemRow({ wi, isNew, isSelected, onClick }: {
  wi: WorkItem; isNew: boolean; isSelected: boolean; onClick: () => void
}) {
  const age = (() => {
    try { return formatDistanceToNow(new Date(wi.created_at), { addSuffix: false }) }
    catch { return '—' }
  })()

  return (
    <tr
      className={`${styles.row}
        ${isNew      ? styles.rowNew      : ''}
        ${isSelected ? styles.rowSelected : ''}
        ${wi.priority === 'P0' && wi.status !== 'CLOSED' ? styles.rowP0 : ''}`}
      onClick={onClick}
    >
      <td><PriorityTag priority={wi.priority} /></td>
      <td>
        <span className={styles.componentCell}>
          <span className={styles.componentId}>{wi.component_id}</span>
          <span className={styles.componentType}>{wi.component_type}</span>
        </span>
      </td>
      <td className={styles.titleCell} title={wi.title}>{wi.title}</td>
      <td><StatusBadge status={wi.status} /></td>
      <td><span className={styles.signalCount}>{wi.signal_count}</span></td>
      <td><span className={styles.age}>{age}</span></td>
      <td><ChevronRight size={14} className={styles.chevron} /></td>
    </tr>
  )
}
