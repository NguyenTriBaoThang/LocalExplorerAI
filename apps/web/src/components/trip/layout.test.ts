import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { setPanel } from './layout.ts'

describe('setPanel', () => {
  it('cửa sổ rộng: mở một panel không đụng panel kia', () => {
    assert.deepEqual(setPanel({ chat: true, timeline: false }, 'timeline', true, false), { chat: true, timeline: true })
  })
  it('cửa sổ hẹp: mở panel này thì đóng panel kia', () => {
    assert.deepEqual(setPanel({ chat: true, timeline: false }, 'timeline', true, true), { chat: false, timeline: true })
  })
  it('đóng panel không mở panel kia', () => {
    assert.deepEqual(setPanel({ chat: true, timeline: true }, 'chat', false, true), { chat: false, timeline: true })
  })
})
