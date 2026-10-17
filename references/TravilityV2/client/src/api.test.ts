import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  applyGroupReview, cancelGroupReview, clarifyAfter, confirmAfter, intentChips, isFinal, mealOf, noFeasibleText, optionPlaces, rainable, searchLine, signed, streamGroupReview, streamTrip, tiers,
  toAnswers, tripLabel, viewingOld, vnd,
  ApiError, type AgentEvent, type Day, type Itinerary, type Place, type ProposalOption, type SystemNode,
} from './api'

describe('group review API', () => {
  afterEach(() => vi.unstubAllGlobals())

  const review = {
    review_id: 4, source_version: 2, base_version: 3, source_is_old: true,
    feedback: 'Giữ quán cũ', summary: 'Giữ quán', unresolved_feedback: [], changed: [],
    itinerary: {}, places: {},
  }

  it('gửi feedback theo source version và nhận preview từ SSE', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      `data: ${JSON.stringify({ type: 'group_review_preview', review })}\n\n`,
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    const received: AgentEvent[] = []

    await streamGroupReview('token', 7, 2, 'Giữ quán cũ', (event) => received.push(event))

    expect(received).toEqual([{ type: 'group_review_preview', review }])
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/trips/7/group-reviews'),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ source_version: 2, feedback: 'Giữ quán cũ' }) }))
  })

  it('apply và cancel dùng đúng Trip-scoped endpoint', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ type: 'itinerary', trip_id: 7, version: 4 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ review_id: 4, status: 'cancelled' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await applyGroupReview('token', 7, 4)
    await cancelGroupReview('token', 7, 4)

    expect(fetchMock.mock.calls.map(([url, init]) => [String(url), init?.method, init?.body])).toEqual([
      [expect.stringContaining('/trips/7/group-reviews/4/apply'), 'POST', '{}'],
      [expect.stringContaining('/trips/7/group-reviews/4/cancel'), 'POST', '{}'],
    ])
  })

  it('apply giữ status và detail của lỗi stale 409', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Lịch trình đã có bản mới hơn' }), { status: 409 },
    )))

    const error = await applyGroupReview('token', 7, 4).catch((err: unknown) => err)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 409, message: 'Lịch trình đã có bản mới hơn' })
  })

  it('SSE HTTP errors giữ status để luồng group review có thể xử lý stale response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Lịch trình đã có bản mới hơn' }), { status: 409 },
    )))
    const received: AgentEvent[] = []

    await streamGroupReview('token', 7, 2, 'Giữ quán cũ', (event) => received.push(event))

    expect(received).toEqual([{
      type: 'error', code: 'http_error', status: 409, message: 'Lịch trình đã có bản mới hơn',
    }])
  })
})

describe('toAnswers', () => {
  it('bỏ ô giờ chưa nhập và chip chưa chọn để server không trả 422', () => {
    expect(toAnswers({ travel_mode: 'grab', arrival_mode: '', arrival_time: '', departure_time: '16:00' }))
      .toEqual({ travel_mode: 'grab', departure_time: '16:00' })
  })
})

describe('clarifyAfter', () => {
  const pending = { tripId: 1, questions: [] }
  it('giữ thẻ hỏi lại khi /plan lỗi để người dùng sửa hoặc thử lại', () => {
    expect(clarifyAfter(pending, { type: 'error', message: 'Giờ về phải sau giờ đến' })).toBe(pending)
  })
  it('bỏ thẻ khi đã có lịch trình', () => {
    const itin = { type: 'itinerary', itinerary: {}, places: {}, trip_id: 1, version: 1 } as unknown as AgentEvent
    expect(clarifyAfter(pending, itin)).toBeNull()
  })
  it('thay bằng câu hỏi mới khi có event clarify', () => {
    expect(clarifyAfter(null, { type: 'clarify', trip_id: 2, questions: [] })).toEqual({ tripId: 2, questions: [] })
  })
})

describe('mealOf', () => {
  it('quán ăn trong khung giờ bữa → tên bữa (khớp MEALS ở server/app/rules.py)', () => {
    expect(mealOf('an-uong', '07:30')).toBe('Bữa sáng')
    expect(mealOf('an-uong', '12:00')).toBe('Bữa trưa')
    expect(mealOf('an-uong', '17:00')).toBe('Bữa tối')
  })
  it('ngoài khung giờ hoặc không phải quán ăn → không có nhãn', () => {
    expect(mealOf('an-uong', '15:00')).toBeNull()
    expect(mealOf('an-uong', '21:00')).toBeNull()
    expect(mealOf('tham-quan', '12:00')).toBeNull()
  })
})

describe('intentChips', () => {
  const base = { stay_place_id: null, days: [], total_cost: 0, conflicts: [], summary: '' }
  it('mỗi Intent của Trip thành một chip có nhãn tiếng Việt', () => {
    const it = { ...base, intents: { 'thu-gian': true, 'van-hoa': false }, retention: 0.67 } as Itinerary
    expect(intentChips(it)).toEqual([{ label: 'Thư giãn', ok: true }, { label: 'Văn hoá', ok: false }])
  })
  it('Itinerary lưu trước khi có Intent → không có chip', () => {
    expect(intentChips(base as Itinerary)).toEqual([])
  })
})

describe('noFeasibleText', () => {
  it('đổi mã lý do thành câu tiếng Việt, mã lạ giữ nguyên', () => {
    expect(noFeasibleText(['NO_CANDIDATE', 'XYZ'])).toEqual(['Chưa có Place nào cùng loại để thay.', 'XYZ'])
  })
})

describe('optionPlaces', () => {
  it('lấy các Place mới theo added', () => {
    const o = { added: [7], places: { '1': { id: 1, name: 'Cũ' }, '7': { id: 7, name: 'Mới' } } } as unknown as ProposalOption
    expect(optionPlaces(o).map((p) => p.name)).toEqual(['Mới'])
  })
})

describe('rainable', () => {
  const places = { '1': { outdoor: true }, '2': { outdoor: false } } as unknown as Record<string, Place>
  const day = { stops: [{ place_id: 1 }, { place_id: 2 }] } as unknown as Day
  it('có Stop ngoài trời chưa ghim', () => expect(rainable(day, places, [])).toBe(true))
  it('Stop ngoài trời đã ghim hết', () => expect(rainable(day, places, [1])).toBe(false))
})

it('noFeasibleText có mã mưa', () => {
  expect(noFeasibleText(['NOTHING_OUTDOOR'])).toEqual(['Ngày này không có Stop ngoài trời nào cần đổi.'])
})

describe('signed', () => {
  it('thêm dấu và đơn vị; 0 là "như cũ"', () => {
    expect(signed(30000, vnd)).toBe('+' + vnd(30000))
    expect(signed(-12, (x) => `${x} phút`)).toBe('−12 phút')
    expect(signed(0, vnd)).toBe('như cũ')
  })
})

describe('confirmAfter', () => {
  const ask = { type: 'confirm_replan', trip_id: 3, text: 'Đổi 3 ngày?', changes: { days: 3 }, message: '3 ngày' } as const
  it('hiện thẻ khi server xin xác nhận, giữ khi đang nghĩ, ẩn khi có lịch hoặc câu trả lời mới', () => {
    const c = confirmAfter(null, ask)
    expect(c).toEqual({ tripId: 3, text: 'Đổi 3 ngày?', changes: { days: 3 }, message: '3 ngày' })
    expect(confirmAfter(c, { type: 'thinking', text: '…' })).toBe(c)
    expect(confirmAfter(c, { type: 'answer', text: 'ok' })).toBeNull()
    expect(confirmAfter(c, { type: 'trip', trip_id: 3, trip: { budget: 1 }, center: [0, 0] })).toBeNull()
  })
})

describe('isFinal', () => {
  it('mọi event kết thúc một lượt đều được tính, để không báo "ngắt kết nối" nhầm', () => {
    expect(isFinal({ type: 'answer', text: 'ok' })).toBe(true)
    expect(isFinal({ type: 'confirm_replan', trip_id: 1, text: '?', changes: {}, message: 'x' })).toBe(true)
    expect(isFinal({ type: 'error', message: 'x' })).toBe(true)
    expect(isFinal({ type: 'thinking', text: '…' })).toBe(false)
    expect(isFinal({ type: 'tool_call', name: 's', query: 'q', places: [] })).toBe(false)
  })
})

describe('viewingOld', () => {
  it('chỉ đúng khi đang xem bản khác bản mới nhất', () => {
    expect(viewingOld(1, 3)).toBe(true)
    expect(viewingOld(3, 3)).toBe(false)
    expect(viewingOld(null, 3)).toBe(false)
    expect(viewingOld(1, null)).toBe(false)
  })
})

describe('tripLabel', () => {
  it('tên Destination · số ngày · ngày tạo', () => {
    expect(tripLabel({ id: 1, spec: { destination: 'da-lat', days: 2 }, created_at: '2026-09-30T12:00:00+07:00',
      destination_name: 'Đà Lạt' })).toBe('Đà Lạt · 2 ngày · 30/09')
  })
  it('thiếu tên thì dùng slug', () => {
    expect(tripLabel({ id: 1, spec: { destination: 'da-lat', days: 1 }, created_at: '2026-01-05T00:00:00Z',
      destination_name: null }).startsWith('da-lat · 1 ngày')).toBe(true)
  })
})

describe('searchLine', () => {
  it('ghép nhãn agent chuyên gia vào dòng tìm kiếm', () => {
    expect(searchLine({ query: 'quán lẩu', places: [1, 2], agent: 'an-uong' }))
      .toBe('Ăn uống · Đang tìm: quán lẩu (2 kết quả)')
    expect(searchLine({ query: 'homestay', places: [], agent: 'cho-o' })).toBe('Chỗ ở · Đang tìm: homestay (0 kết quả)')
  })
  it('agent đơn hoặc agent lạ thì giữ dòng cũ', () => {
    expect(searchLine({ query: 'cafe', places: [1] })).toBe('Đang tìm: cafe (1 kết quả)')
    expect(searchLine({ query: 'cafe', places: [1], agent: 'la' })).toBe('Đang tìm: cafe (1 kết quả)')
  })
})

describe('tiers', () => {
  const node = (name: string, role: string): SystemNode => ({ name, role, state: 'up' })
  it('xếp node theo tầng từ cổng vào xuống dữ liệu, bỏ tầng trống', () => {
    const got = tiers([node('pg-shard-1', 'pg-shard'), node('api a', 'api'), node('pg-catalog', 'pg-catalog'),
      node('planner-agent x', 'planner-agent'), node('planner p', 'planner'), node('pg-shard-0', 'pg-shard')])
    expect(got.map((t) => [t.label, t.nodes.map((n) => n.name)])).toEqual([
      ['API', ['api a']],
      ['Lập lịch', ['planner p', 'planner-agent x']],
      ['Dữ liệu', ['pg-catalog', 'pg-shard-1', 'pg-shard-0']],
    ])
  })
  it('role lạ không làm mất node', () => {
    expect(tiers([node('la', 'moi')])).toEqual([{ label: 'Khác', nodes: [node('la', 'moi')] }])
  })
})

describe('streamSSE nối lại bằng job_id', () => {
  const A = { type: 'thinking', text: 'Đang đọc yêu cầu…' }
  const B = { type: 'tool_call', name: 'search_places', query: 'cafe', places: [] }
  const END = { type: 'answer', text: 'xong' }

  /** Phản hồi SSE giả: phát `events` rồi đóng (cut = đứt mạng: lần đọc sau ném lỗi). */
  function sse(events: object[], opts: { jobId?: string; cut?: boolean } = {}) {
    const chunk = new TextEncoder().encode(events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(''))
    let sent = false
    const body = new ReadableStream<Uint8Array>({
      pull(c) {
        if (!sent) { sent = true; c.enqueue(chunk); return }
        if (opts.cut) c.error(new Error('đứt mạng')); else c.close()
      },
    })
    return new Response(body, { headers: opts.jobId ? { 'X-Job-Id': opts.jobId } : {} })
  }

  async function run(responses: (Response | Error)[]) {
    vi.useFakeTimers()
    const fetchMock = vi.fn(async (_url: string) => {
      const r = responses.shift()!
      if (r instanceof Error) throw r
      return r
    })
    vi.stubGlobal('fetch', fetchMock)
    const got: AgentEvent[] = []
    const done = streamTrip('tok', 'Đà Lạt 1 ngày', null, (e) => got.push(e))
    await vi.runAllTimersAsync()
    await done
    return { got, urls: fetchMock.mock.calls.map((c) => String(c[0])) }
  }

  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

  it('luồng đứt giữa chừng → đọc tiếp từ /jobs/{id}/events, không phát trùng event đã nhận', async () => {
    const { got, urls } = await run([sse([A, B], { jobId: 'j1', cut: true }), sse([A, B, END])])
    expect(got).toEqual([A, B, END])
    expect(urls[1]).toMatch(/\/jobs\/j1\/events$/)
  })

  it('luồng đóng sớm không báo lỗi cũng được nối lại; lần nối hỏng thì thử lần nữa', async () => {
    const { got, urls } = await run([sse([A], { jobId: 'j1' }), new TypeError('fetch failed'), sse([A, END])])
    expect(got).toEqual([A, END])
    expect(urls).toHaveLength(3)
  })

  it('hết 2 lần nối lại vẫn chưa xong → một bong bóng lỗi', async () => {
    const { got, urls } = await run([sse([A], { jobId: 'j1' }), sse([A]), sse([A])])
    expect(got).toEqual([A, { type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' }])
    expect(urls).toHaveLength(3)
  })

  it('lỗi trong lúc xử lý event không bị nuốt như lỗi mạng: ném ra để App báo, không nối lại', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => sse([A, END], { jobId: 'j1' })))
    const boom = () => { throw new Error('vẽ lịch hỏng') }
    await expect(streamTrip('tok', 'Đà Lạt 1 ngày', null, boom)).rejects.toThrow('vẽ lịch hỏng')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('không có X-Job-Id (chế độ một tiến trình) → báo lỗi như cũ, không gọi thêm', async () => {
    const { got, urls } = await run([sse([A])])
    expect(got).toEqual([A, { type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' }])
    expect(urls).toHaveLength(1)
  })
})
