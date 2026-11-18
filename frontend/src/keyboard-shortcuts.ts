export type DesktopShortcutIntent =
  | { type: 'select-track'; delta: -1 | 1 }
  | { type: 'seek'; seconds: -5 | 5 }
  | { type: 'route'; routeId: string; repeated: boolean }
  | { type: 'current-crate' }

type KeyboardLike = Pick<KeyboardEvent, 'altKey' | 'code' | 'ctrlKey' | 'metaKey' | 'repeat'>

export function isDesktopShortcutCode(code: string): boolean {
  return /^(Key[WASD]|Numpad[0-9])$/.test(code)
}

export function resolveDesktopShortcut(event: KeyboardLike): DesktopShortcutIntent | null {
  if (event.altKey || event.ctrlKey || event.metaKey) return null

  if (event.code === 'KeyW') return { type: 'select-track', delta: -1 }
  if (event.code === 'KeyS') return { type: 'select-track', delta: 1 }
  if (event.code === 'KeyA') return { type: 'seek', seconds: -5 }
  if (event.code === 'KeyD') return { type: 'seek', seconds: 5 }
  if (event.code === 'Numpad0') return { type: 'current-crate' }

  const routeMatch = event.code.match(/^Numpad([1-9])$/)
  return routeMatch
    ? { type: 'route', routeId: routeMatch[1], repeated: event.repeat }
    : null
}
