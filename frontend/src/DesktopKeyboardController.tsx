import { useEffect, useState } from 'react'
import { isDesktopShortcutCode, resolveDesktopShortcut } from './keyboard-shortcuts'

function isTextEntryTarget(target: EventTarget | null): boolean {
  const element = target instanceof HTMLElement ? target : null
  return Boolean(element?.isContentEditable || element?.closest('input, textarea, select, [contenteditable="true"]'))
}

function announce(setAnnouncement: (message: string) => void, message: string) {
  setAnnouncement('')
  window.requestAnimationFrame(() => setAnnouncement(message))
}

function pulsePreviewRoute(button: HTMLButtonElement) {
  button.classList.remove('routing-slot-preview-pulse')
  void button.offsetWidth
  button.classList.add('routing-slot-preview-pulse')
  window.setTimeout(() => button.classList.remove('routing-slot-preview-pulse'), 650)
}

export function DesktopKeyboardController() {
  const [announcement, setAnnouncement] = useState('')

  useEffect(() => {
    function handleKeyboard(event: KeyboardEvent) {
      if (!isDesktopShortcutCode(event.code)) return
      if (isTextEntryTarget(event.target)) return

      // Keep the legacy bubble listener from firing behind modals, during IME input,
      // or for OS/application shortcuts such as Ctrl+W. Default browser behavior is
      // preserved in these guarded cases.
      if (event.isComposing || document.querySelector('[aria-modal="true"]') || event.altKey || event.ctrlKey || event.metaKey) {
        event.stopImmediatePropagation()
        return
      }

      const intent = resolveDesktopShortcut(event)
      const shell = document.querySelector<HTMLElement>('.app-shell')
      if (!intent || !shell) return

      // This controller is the single runtime keyboard path. It drives the same
      // visible controls as mouse input and suppresses the older bubble listener.
      event.preventDefault()
      event.stopImmediatePropagation()

      if (intent.type === 'select-track') {
        const rows = Array.from(document.querySelectorAll<HTMLElement>('.track-list .track-row'))
        if (!rows.length) return
        const selectedPosition = rows.findIndex((row) => row.classList.contains('track-row-selected'))
        const nextPosition = selectedPosition === -1
          ? intent.delta > 0 ? 0 : rows.length - 1
          : Math.max(0, Math.min(rows.length - 1, selectedPosition + intent.delta))
        const nextRow = rows[nextPosition]
        nextRow.click()
        nextRow.focus({ preventScroll: true })
        nextRow.scrollIntoView({ block: 'nearest' })
        announce(setAnnouncement, `${intent.delta > 0 ? 'Next' : 'Previous'} track selected`)
        return
      }

      if (intent.type === 'seek') {
        const label = intent.seconds < 0 ? 'Rewind five seconds' : 'Fast forward five seconds'
        const button = document.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)
        if (!button || button.disabled) return
        button.click()
        announce(setAnnouncement, intent.seconds < 0 ? 'Rewound five seconds' : 'Forwarded five seconds')
        return
      }

      if (intent.type === 'current-crate') {
        announce(setAnnouncement, 'Current Crate is a holding area and does not move files')
        return
      }

      if (intent.repeated) return

      const routeButton = document.querySelector<HTMLButtonElement>(`.routing-slot[data-route-id="${intent.routeId}"]`)
      if (!routeButton) return

      if (shell.dataset.previewMode === 'true') {
        pulsePreviewRoute(routeButton)
        announce(setAnnouncement, `Preview route ${intent.routeId}. No file moved`)
        return
      }
      if (routeButton.disabled) {
        announce(setAnnouncement, `Route ${intent.routeId} is unavailable`)
        return
      }

      routeButton.click()
      announce(setAnnouncement, `Routing selected track to route ${intent.routeId}`)
    }

    window.addEventListener('keydown', handleKeyboard, true)
    return () => window.removeEventListener('keydown', handleKeyboard, true)
  }, [])

  return <span className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</span>
}
