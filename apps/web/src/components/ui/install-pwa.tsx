import { useState, useEffect, useCallback } from 'react'
import { cn } from '../../lib/utils'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

declare global {
  interface WindowEventMap {
    'beforeinstallprompt': BeforeInstallPromptEvent
    'appinstalled': Event
  }
}

export function InstallPWA() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    const handler = (e: BeforeInstallPromptEvent) => {
      e.preventDefault()
      setDeferredPrompt(e)
    }

    const installedHandler = () => {
      setInstalled(true)
      setDeferredPrompt(null)
    }

    // Check if already in standalone mode (already installed)
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setInstalled(true)
      return
    }

    window.addEventListener('beforeinstallprompt', handler)
    window.addEventListener('appinstalled', installedHandler)

    return () => {
      window.removeEventListener('beforeinstallprompt', handler)
      window.removeEventListener('appinstalled', installedHandler)
    }
  }, [])

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    if (choice.outcome === 'accepted') {
      setInstalled(true)
    }
    setDeferredPrompt(null)
  }, [deferredPrompt])

  const handleDismiss = useCallback(() => {
    setClosing(true)
    setTimeout(() => {
      setClosing(false)
      setDismissed(true)
    }, 200)
  }, [])

  if (installed || dismissed || !deferredPrompt) return null

  const show = !closing

  return (
    <div
      className={cn(
        'fixed bottom-20 sm:bottom-6 left-1/2 -translate-x-1/2 sm:left-24 sm:translate-x-0 z-[var(--z-overlay)]',
        show ? 'animate-fade-in-up' : 'animate-fade-out-down'
      )}
      style={{ animationDuration: 'var(--motion-fast)' }}
    >
      <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-xl backdrop-blur-sm">
        <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-[var(--color-brand-accent)] text-white font-bold text-xs flex-shrink-0 shadow-sm">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v3m0 0l-3-3m3 3l3-3M5 12a7 7 0 1114 0" />
          </svg>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">Install SDMAS</p>
          <p className="text-xs text-[var(--color-text-tertiary)]">Add to home screen for quick access</p>
        </div>
        <button
          onClick={handleInstall}
          className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--color-brand-accent)] text-white hover:bg-[var(--color-brand-accent-hover)] transition-colors"
        >
          Install
        </button>
        <button
          onClick={handleDismiss}
          className="flex-shrink-0 flex items-center justify-center h-7 w-7 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors"
          aria-label="Dismiss"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  )
}
