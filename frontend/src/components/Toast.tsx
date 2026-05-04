import { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react'
import { CheckCircle, AlertTriangle, Info, X, AlertOctagon } from 'lucide-react'
import styles from './Toast.module.css'

// ── Types ──────────────────────────────────────────────────────────────────────
export type ToastKind = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  kind: ToastKind
  title: string
  message?: string
  duration?: number  // ms, 0 = sticky
}

interface ToastContextValue {
  add: (toast: Omit<Toast, 'id'>) => void
  remove: (id: string) => void
}

// ── Context ────────────────────────────────────────────────────────────────────
const ToastContext = createContext<ToastContextValue>({
  add: () => {},
  remove: () => {},
})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
    clearTimeout(timers.current[id])
    delete timers.current[id]
  }, [])

  const add = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    const duration = toast.duration ?? 4000
    setToasts(prev => [{ ...toast, id }, ...prev].slice(0, 6))
    if (duration > 0) {
      timers.current[id] = setTimeout(() => remove(id), duration)
    }
  }, [remove])

  return (
    <ToastContext.Provider value={{ add, remove }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={remove} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}

// ── Container ──────────────────────────────────────────────────────────────────
function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: string) => void }) {
  if (toasts.length === 0) return null
  return (
    <div className={styles.container} role="region" aria-label="Notifications">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onRemove={onRemove} />
      ))}
    </div>
  )
}

const KIND_CONFIG: Record<ToastKind, { icon: ReactNode; cls: string }> = {
  success: { icon: <CheckCircle size={15} />,   cls: styles.success  },
  error:   { icon: <AlertOctagon size={15} />,  cls: styles.error    },
  warning: { icon: <AlertTriangle size={15} />, cls: styles.warning  },
  info:    { icon: <Info size={15} />,          cls: styles.info     },
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
  const cfg = KIND_CONFIG[toast.kind]
  return (
    <div className={`${styles.toast} ${cfg.cls}`} role="alert">
      <span className={styles.icon}>{cfg.icon}</span>
      <div className={styles.body}>
        <p className={styles.title}>{toast.title}</p>
        {toast.message && <p className={styles.message}>{toast.message}</p>}
      </div>
      <button className={styles.close} onClick={() => onRemove(toast.id)}>
        <X size={13} />
      </button>
    </div>
  )
}
