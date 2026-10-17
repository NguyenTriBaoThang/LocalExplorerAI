import { describe, expect, it } from 'vitest'
import { setPanel } from './layout'

describe('setPanel', () => {
  it('cửa sổ rộng: mở một panel không đụng panel kia', () => {
    expect(setPanel({ chat: true, timeline: false }, 'timeline', true, false)).toEqual({ chat: true, timeline: true })
  })
  it('cửa sổ hẹp: mở panel này thì đóng panel kia', () => {
    expect(setPanel({ chat: true, timeline: false }, 'timeline', true, true)).toEqual({ chat: false, timeline: true })
  })
  it('đóng panel không mở panel kia', () => {
    expect(setPanel({ chat: true, timeline: true }, 'chat', false, true)).toEqual({ chat: false, timeline: true })
  })
})
