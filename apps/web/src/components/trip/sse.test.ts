import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { parseSSE } from './sse.ts'

describe('parseSSE', () => {
  it('tách sự kiện hoàn chỉnh và giữ phần dở dang', () => {
    const { events, rest } = parseSSE('data: {"type":"thinking","text":"a"}\n\ndata: {"type":"er')
    assert.deepEqual(events, [{ type: 'thinking', text: 'a' }])
    assert.deepEqual(rest, 'data: {"type":"er')
  })

  it('ghép tiếp phần còn lại ở lần đọc sau', () => {
    const first = parseSSE('data: {"a":')
    const second = parseSSE(first.rest + '1}\n\n')
    assert.deepEqual(second.events, [{ a: 1 }])
    assert.deepEqual(second.rest, '')
  })
})
