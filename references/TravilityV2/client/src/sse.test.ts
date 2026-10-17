import { describe, expect, it } from 'vitest'
import { parseSSE } from './sse'

describe('parseSSE', () => {
  it('tách sự kiện hoàn chỉnh và giữ phần dở dang', () => {
    const { events, rest } = parseSSE('data: {"type":"thinking","text":"a"}\n\ndata: {"type":"er')
    expect(events).toEqual([{ type: 'thinking', text: 'a' }])
    expect(rest).toBe('data: {"type":"er')
  })

  it('ghép tiếp phần còn lại ở lần đọc sau', () => {
    const first = parseSSE('data: {"a":')
    const second = parseSSE(first.rest + '1}\n\n')
    expect(second.events).toEqual([{ a: 1 }])
    expect(second.rest).toBe('')
  })
})
