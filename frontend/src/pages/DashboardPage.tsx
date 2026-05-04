import { useState, useCallback } from 'react'
import { LayoutDashboard } from 'lucide-react'
import { StatsStrip } from '../components/StatsStrip'
import { SignalFeed } from '../components/SignalFeed'
import { SignalTester } from '../components/SignalTester'
import { WorkItemList } from '../components/WorkItemList'
import { ConnectionBar } from '../components/ConnectionBar'
import { ThroughputChart } from '../components/ThroughputChart'
import { useRealtimeEvents } from '../hooks/useRealtimeEvents'
import { Signal, WorkItem } from '../types'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const [liveSignals, setLiveSignals]             = useState<Signal[]>([])
  const [newWorkItems, setNewWorkItems]           = useState<WorkItem[]>([])
  const [updatedWorkItems, setUpdatedWorkItems]   = useState<WorkItem[]>([])

  const { status, attempts, clientId } = useRealtimeEvents({
    onSignal: useCallback((sig: Signal) => {
      setLiveSignals(prev => [sig, ...prev].slice(0, 200))
    }, []),
    onWorkItemCreated: useCallback((wi: WorkItem) => {
      setNewWorkItems(prev => [wi, ...prev])
    }, []),
    onWorkItemUpdated: useCallback((wi: WorkItem) => {
      setUpdatedWorkItems(prev => [wi, ...prev])
    }, []),
  })

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <LayoutDashboard size={16} className={styles.titleIcon} />
          <h1 className={styles.title}>Dashboard</h1>
        </div>
        <ConnectionBar status={status} attempts={attempts} clientId={clientId} />
      </header>

      <StatsStrip />

      <div className={styles.workItemSection}>
        <WorkItemList
          externalNewItems={newWorkItems}
          externalUpdatedItems={updatedWorkItems}
        />
      </div>

      <div className={styles.bottomGrid}>
        <div className={styles.chartAndFeed}>
          <ThroughputChart />
          <div className={styles.feedWrap}>
            <SignalFeed externalSignals={liveSignals} />
          </div>
        </div>
        <div className={styles.testerCol}>
          <SignalTester />
        </div>
      </div>
    </div>
  )
}
