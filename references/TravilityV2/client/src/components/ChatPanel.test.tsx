// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ChatPanel from './ChatPanel'

afterEach(cleanup)

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('ChatPanel group feedback draft', () => {
  it('keeps newer text typed while an earlier preview request succeeds', async () => {
    const pending = deferred<boolean>()
    const onGroupReview = vi.fn(() => pending.promise)
    render(<ChatPanel items={[{ role: 'user', text: 'Lịch trình hiện tại' }]} busy={false} onSend={vi.fn()}
      versions={[1, 2]} version={1} latest={2} onGroupReview={onGroupReview} />)

    fireEvent.click(screen.getByRole('button', { name: 'Góp ý nhóm' }))
    const input = screen.getByRole('textbox', { name: 'Góp ý nhóm' }) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Feedback A' } })
    fireEvent.submit(input.closest('form')!)
    expect(onGroupReview).toHaveBeenCalledWith('Feedback A', 1)

    fireEvent.change(input, { target: { value: 'Feedback B' } })
    await act(async () => {
      pending.resolve(true)
      await pending.promise
    })

    expect(input.value).toBe('Feedback B')
  })
})
