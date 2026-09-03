import assert from 'node:assert/strict'
import test from 'node:test'
import { isDesktopShortcutCode, resolveDesktopShortcut } from '../src/keyboard-shortcuts.ts'

function key(code: string, repeat = false, modifiers: Partial<{ altKey: boolean; ctrlKey: boolean; metaKey: boolean }> = {}) {
  return {
    code,
    repeat,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    ...modifiers,
  }
}

test('W and S navigate the queue while A and D seek five seconds', () => {
  assert.deepEqual(resolveDesktopShortcut(key('KeyW')), { type: 'select-track', delta: -1 })
  assert.deepEqual(resolveDesktopShortcut(key('KeyS')), { type: 'select-track', delta: 1 })
  assert.deepEqual(resolveDesktopShortcut(key('KeyA')), { type: 'seek', seconds: -5 })
  assert.deepEqual(resolveDesktopShortcut(key('KeyD')), { type: 'seek', seconds: 5 })
})

test('physical numpad keys preserve route identity and expose repeat state', () => {
  assert.deepEqual(resolveDesktopShortcut(key('Numpad7')), { type: 'route', routeId: '7', repeated: false })
  assert.deepEqual(resolveDesktopShortcut(key('Numpad7', true)), { type: 'route', routeId: '7', repeated: true })
  assert.deepEqual(resolveDesktopShortcut(key('Numpad0')), { type: 'current-crate' })
  assert.equal(resolveDesktopShortcut(key('Digit7')), null)
})

test('owned codes stay identifiable even when modifiers reserve them for the OS', () => {
  assert.equal(isDesktopShortcutCode('KeyW'), true)
  assert.equal(isDesktopShortcutCode('Numpad1'), true)
  assert.equal(isDesktopShortcutCode('Digit1'), false)
  assert.equal(resolveDesktopShortcut(key('KeyW', false, { ctrlKey: true })), null)
  assert.equal(resolveDesktopShortcut(key('KeyD', false, { altKey: true })), null)
  assert.equal(resolveDesktopShortcut(key('Numpad1', false, { metaKey: true })), null)
})
