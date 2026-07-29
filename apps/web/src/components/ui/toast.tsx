import { useState, createContext, useContext, useCallback, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: number
  message: string
  type: ToastType
  title?: string
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, title?: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

let toastId = 0

const iconPaths: Record<ToastType, string> = {
  success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  error: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
}

const toastStyles: Record<ToastType, string> = {
  success: 'bg-[var(--color-success)]',
  error: 'bg-[var(--color-danger)]',
  info: 'bg-[var(--color-primary)]',
  warning: 'bg-[var(--color-warning)]',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [leavingIds, setLeavingIds] = useState<Set<number>>(new Set())

  const showToast = useCallback((message: string, type: ToastType = 'info', title?: string) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type, title }])
    setTimeout(() => {
      removeToastWithAnimation(id)
    }, 4000)
  }, [])

  const removeToastWithAnimation = useCallback((id: number) => {
    setLeavingIds((prev) => new Set(prev).add(id))
    setTimeout(() => {
      setLeavingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 200)
  }, [])

  const removeToast = useCallback((id: number) => {
    removeToastWithAnimation(id)
  }, [removeToastWithAnimation])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none"
        aria-live="polite"
        aria-label="Notifications"
      >
        {toasts.map((toast, index) => (
          <div
            key={toast.id}
            className={cn(
              'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg text-sm text-white',
              leavingIds.has(toast.id) ? 'animate-slide-out-right' : 'animate-slide-in-right',
              toastStyles[toast.type]
            )}
            style={{ animationDelay: leavingIds.has(toast.id) ? '0ms' : `${index * 50}ms` }}
            role="alert"
          >
            <svg className="h-5 w-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={iconPaths[toast.type]} />
            </svg>
            <div className="flex-1 min-w-0">
              {toast.title && <p className="font-medium text-sm">{toast.title}</p>}
              <p className="text-sm opacity-90">{toast.message}</p>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 flex items-center justify-center h-5 w-5 rounded hover:bg-white/20 transition-colors"
              aria-label="Dismiss"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
