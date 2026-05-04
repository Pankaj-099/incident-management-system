import { WsStatus } from '../hooks/useSignalWebSocket'
import { Wifi, WifiOff, Loader, AlertTriangle } from 'lucide-react'
import styles from './ConnectionBar.module.css'

interface Props {
  status: WsStatus
  attempts: number
  clientId: string | null
}

export function ConnectionBar({ status, attempts, clientId }: Props) {
  const isConnected    = status === 'connected'
  const isConnecting   = status === 'connecting'
  const isError        = status === 'error'
  const isDisconnected = status === 'disconnected'

  return (
    <div className={`${styles.bar}
      ${isConnected    ? styles.barConnected    : ''}
      ${isConnecting   ? styles.barConnecting   : ''}
      ${isError || isDisconnected ? styles.barDisconnected : ''}`}
    >
      <span className={styles.iconWrap}>
        {isConnected  && <Wifi size={11} />}
        {isConnecting && <Loader size={11} className={styles.spin} />}
        {(isError || isDisconnected) && (attempts > 0 ? <AlertTriangle size={11} /> : <WifiOff size={11} />)}
      </span>

      <span className={styles.label}>
        {isConnected    && 'Live'}
        {isConnecting   && 'Connecting…'}
        {isDisconnected && attempts > 0 && `Reconnecting (${attempts})…`}
        {isDisconnected && attempts === 0 && 'Disconnected'}
        {isError        && 'Connection error'}
      </span>

      {isConnected && clientId && (
        <span className={styles.clientId}>{clientId}</span>
      )}

      {/* Blinking dot for connected */}
      {isConnected && <span className={styles.liveDot} />}
    </div>
  )
}
