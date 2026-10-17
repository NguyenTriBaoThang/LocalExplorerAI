import { useEffect, useRef, useState } from 'react'
import {
  ApiError, applyGroupReview, applyProposal, cancelGroupReview, clarifyAfter, confirmAfter, getMessages, getTrip,
  listTrips, optionPlaces, reportDisruption, restoreVersion, searchLine, setPin, streamGroupReview, streamPlan,
  streamReplan, streamTrip, tripLabel, viewingOld, vnd,
  type AgentEvent, type Answers, type Clarify, type ConfirmReplan, type DisruptionReq, type GroupReview, type Itinerary,
  type ItineraryEvent, type Place, type Proposal, type TripSummary,
} from './api'
import ChatPanel, { type ChatItem, type GroupReviewRetry } from './components/ChatPanel'
import ClarifyCard from './components/ClarifyCard'
import ConfirmCard from './components/ConfirmCard'
import FloatingPanel from './components/FloatingPanel'
import GroupReviewPanel from './components/GroupReviewPanel'
import Login from './components/Login'
import MapView from './components/MapView'
import ProposalPanel from './components/ProposalPanel'
import Rail from './components/Rail'
import SystemPage from './components/SystemPage'
import Timeline from './components/Timeline'
import TripPrintView from './components/TripPrintView'
import { NARROW, setPanel, type Panels } from './layout'
import { type Selected } from './place'
import { buildTripPrintModel, type TripPrintModel } from './tripPrint'

function loadToken() {
  try { return localStorage.getItem('token') } catch { return null }
}
function saveToken(t: string | null) {
  try {
    if (t) localStorage.setItem('token', t)
    else localStorage.removeItem('token')
  } catch { /* chỉ là tiện ích nhớ đăng nhập */ }
}

export default function App() {
  const [token, setToken] = useState<string | null>(loadToken)
  const [chat, setChat] = useState<ChatItem[]>([])
  const [busy, setBusy] = useState(false)
  const [center, setCenter] = useState<[number, number]>([108.4583, 11.9404])
  const [searchPins, setSearchPins] = useState<Place[]>([])
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [places, setPlaces] = useState<Record<string, Place>>({})
  const [budget, setBudget] = useState<number | null>(null)
  const [clarify, setClarify] = useState<Clarify | null>(null)
  const [confirm, setConfirm] = useState<ConfirmReplan | null>(null)  // đổi Trip chờ người dùng đồng ý lập lại
  const [tripId, setTripId] = useState<number | null>(null)  // Trip đang mở: tin nhắn sau thuộc Trip này
  const [version, setVersion] = useState<number | null>(null)  // version Itinerary đang xem, gửi kèm Disruption
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [groupReview, setGroupReview] = useState<GroupReview | null>(null)
  const [groupReviewStale, setGroupReviewStale] = useState(false)
  const [groupReviewRetry, setGroupReviewRetry] = useState<GroupReviewRetry | null>(null)
  const [changed, setChanged] = useState<[number, number][]>([])  // Stop vừa đổi, tô viền trên Timeline
  const [versions, setVersions] = useState<number[]>([])
  const [latest, setLatest] = useState<number | null>(null)  // bản mới nhất; `version` là bản đang xem
  const [pins, setPins] = useState<number[]>([])
  const [trips, setTrips] = useState<TripSummary[]>([])
  const [selected, setSelected] = useState<Selected>(null)
  const [narrow, setNarrow] = useState(() => matchMedia(NARROW).matches)
  const [panels, setPanels] = useState<Panels>(() => ({ chat: true, timeline: !matchMedia(NARROW).matches }))
  const [unread, setUnread] = useState(0)  // tin mới đến lúc Chat đang thu gọn (badge)
  const [system, setSystem] = useState(false)  // trang "Hệ thống" đang mở
  const [printModel, setPrintModel] = useState<TripPrintModel | null>(null)
  const chatOpen = useRef(true)  // ref: `add` trong closure của stream cũ vẫn đọc được trạng thái mới
  chatOpen.current = panels.chat

  useEffect(() => {
    if (!printModel) return
    const clearPrintModel = () => setPrintModel(null)
    window.addEventListener('afterprint', clearPrintModel)
    window.print()
    return () => window.removeEventListener('afterprint', clearPrintModel)
  }, [printModel])

  useEffect(() => {
    const m = matchMedia(NARROW)
    const on = () => { setNarrow(m.matches); if (m.matches) setPanels((p) => (p.chat && p.timeline ? { ...p, chat: false } : p)) }
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])

  useEffect(() => {  // mở app: tải danh sách + mở Trip gần nhất
    if (!token) return
    listTrips(token).then((ts) => {
      setTrips(ts)
      if (ts.length > 0) openTrip(ts[0].id)
    }).catch(() => { /* server chưa chạy → giữ empty state, lỗi sẽ hiện khi gửi tin */ })
  }, [token])

  if (!token) return <Login onToken={(t) => { saveToken(t); setToken(t) }} />

  const add = (item: ChatItem) => {
    setChat((c) => [...c, item])
    if (!chatOpen.current) setUnread((u) => u + 1)
  }
  const openPanel = (side: keyof Panels, open: boolean) => {
    if (side === 'chat' && open) setUnread(0)
    setPanels((p) => setPanel(p, side, open, narrow))
  }

  function handle(e: AgentEvent) {
    setClarify((c) => clarifyAfter(c, e))
    setConfirm((c) => confirmAfter(c, e))
    switch (e.type) {
      case 'thinking': add({ role: 'ai', text: e.text }); break
      case 'trip':
        if (e.trip_id !== tripId) {
          setVersions([]); setPins([]); setLatest(null)
          setGroupReview(null); setGroupReviewStale(false); setGroupReviewRetry(null)
        }
        setTripId(e.trip_id); setVersion(null); setProposal(null)
        setCenter(e.center); setBudget(e.trip.budget); setItinerary(null)
        break
      case 'tool_call':
        add({ role: 'tool', text: searchLine(e) })
        setSearchPins((p) => [...p, ...e.places.filter((x) => !p.some((y) => y.id === x.id))])
        break
      case 'itinerary':
        setPlaces(e.places); setItinerary(e.itinerary); setVersion(e.version); setChanged(e.changed ?? []); setSearchPins([])
        setSelected(null); openPanel('timeline', true)
        setLatest(e.version); setVersions((vs) => vs.includes(e.version) ? vs : [...vs, e.version])
        add({ role: 'ai', text: e.itinerary.summary })
        break
      case 'group_review_preview':
        setGroupReview(e.review); setGroupReviewStale(false); setGroupReviewRetry(null)
        break
      case 'answer': add({ role: 'ai', text: e.text }); break
      case 'confirm_replan': add({ role: 'ai', text: e.text }); break
      case 'error': add({ role: 'error', text: e.message }); break
    }
  }

  async function run(stream: (onEvent: (e: AgentEvent) => void) => Promise<void>) {
    setBusy(true)
    setSearchPins([])
    try {
      await stream(handle)
    } catch (err) {
      if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
      else add({ role: 'error', text: 'Mất kết nối tới máy chủ. Kiểm tra server đã chạy chưa.' })
    } finally {
      setBusy(false)
    }
  }

  async function call<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true)
    try {
      return await fn()
    } catch (err) {
      if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
      else if (err instanceof Error && !(err instanceof TypeError)) add({ role: 'error', text: err.message })
      else add({ role: 'error', text: 'Mất kết nối tới máy chủ. Kiểm tra server đã chạy chưa.' })
    } finally {
      setBusy(false)
    }
  }

  function showView(v: { itinerary: Itinerary | null; places: Record<string, Place>; version: number | null }) {
    setItinerary(v.itinerary); setPlaces(v.places); setVersion(v.version); setChanged([])
    setProposal(null); setSearchPins([]); setSelected(null)
    if (v.itinerary) openPanel('timeline', true)
  }

  function syncLatestTrip(t: Awaited<ReturnType<typeof getTrip>>) {
    setCenter(t.center); setBudget(t.trip.budget); setVersions(t.versions); setLatest(t.version); setPins(t.pinned_place_ids)
    showView(t)
  }

  async function refreshLatestTrip() {
    const id = tripId
    if (id == null) return
    setBusy(true)
    try {
      const t = await getTrip(token!, id)
      if (id === tripId) syncLatestTrip(t)
    } catch (err) {
      if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
      else add({ role: 'error', text: err instanceof Error ? err.message : 'Không tải được bản mới nhất.' })
    } finally {
      setBusy(false)
    }
  }

  async function openTrip(id: number, withChat = true) {
    const t = await call(() => getTrip(token!, id))
    if (!t) return
    if (id !== tripId) {
      setGroupReview(null); setGroupReviewStale(false); setGroupReviewRetry(null)
    }
    setTripId(id); setCenter(t.center); setBudget(t.trip.budget); setClarify(null); setConfirm(null)
    setVersions(t.versions); setLatest(t.version); setPins(t.pinned_place_ids)
    showView(t)
    if (withChat) {
      const ms = await call(() => getMessages(token!, id))
      setChat((ms ?? []).map(({ role, text, version }) => ({ role, text, version })))
    }
  }

  const viewVersion = async (v: number) => {
    const t = await call(() => getTrip(token!, tripId!, v))
    if (t) showView(t)
  }

  const restore = async () => {
    const ev = await call(() => restoreVersion(token!, tripId!, version!))
    if (!ev) return
    setVersions((vs) => [...vs, ev.version]); setLatest(ev.version); setPins(ev.pinned_place_ids)
    showView(ev)
    add({ role: 'ai', text: `Đã quay lại bản ${version} (thành bản ${ev.version}).` })
  }

  const pin = async (placeId: number, pinned: boolean) => {
    const r = await call(() => setPin(token!, tripId!, placeId, pinned))
    if (r) setPins(r.pinned_place_ids)
  }

  const logout = () => { saveToken(null); setToken(null); newTrip(); setTrips([]); setSystem(false) }

  const disrupt = async (d: DisruptionReq) => {
    const p = await call(() => reportDisruption(token!, tripId!, version!, d))
    if (!p) return
    setProposal(p)
    setSearchPins((p.options ?? []).flatMap(optionPlaces))
  }

  async function submitGroupReview(feedback: string, sourceVersion: number, isRetry = false): Promise<boolean> {
    if (tripId == null) return false
    if (!isRetry) {
      add({ role: 'user', text: feedback, version: sourceVersion })
      setGroupReviewRetry(null)
    }
    let previewCreated = false
    let becameStale = false
    await run((on) => streamGroupReview(token!, tripId, sourceVersion, feedback, (event) => {
      if (event.type === 'group_review_preview') previewCreated = true
      if (event.type === 'error' && (event.code === 'stale_base' || event.status === 409)) {
        becameStale = true
        setGroupReview(null)
        setGroupReviewStale(false)
        setGroupReviewRetry({
          feedback, sourceVersion,
          message: `Lịch trình đã có bản mới hơn. Góp ý trên v${sourceVersion} vẫn được giữ lại để bạn tạo preview mới.`,
        })
      }
      on(event)
    }))
    if (previewCreated) setGroupReviewRetry(null)
    if (becameStale) await refreshLatestTrip()
    return previewCreated
  }

  const onGroupReview = (feedback: string, sourceVersion: number) => submitGroupReview(feedback, sourceVersion)

  async function retryGroupReview(feedback: string, sourceVersion: number): Promise<boolean> {
    if (groupReview && groupReviewStale && tripId != null) {
      const cancelled = await call(() => cancelGroupReview(token!, tripId, groupReview.review_id))
      if (!cancelled) return false
      setGroupReview(null); setGroupReviewStale(false)
    }
    return submitGroupReview(feedback, sourceVersion, true)
  }

  const applyGroup = async () => {
    if (!groupReview || tripId == null) return
    const review = groupReview
    const appliedTripId = tripId
    setBusy(true)
    try {
      const event = await applyGroupReview(token!, appliedTripId, review.review_id)
      setGroupReview(null); setGroupReviewStale(false); setGroupReviewRetry(null)
      setPlaces(event.places); setItinerary(event.itinerary); setVersion(event.version); setLatest(event.version)
      setChanged(review.changed)
      setVersions((currentVersions) => currentVersions.includes(event.version)
        ? currentVersions : [...currentVersions, event.version])
      add({ role: 'ai', text: `Đã áp dụng preview góp ý nhóm — lịch trình bản ${event.version}.`, version: event.version })
      try {
        const refreshed = await getTrip(token!, appliedTripId)
        if (appliedTripId === tripId) syncLatestTrip(refreshed)
      } catch (err) {
        if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
        else add({ role: 'error', text: err instanceof Error ? err.message : 'Không đồng bộ được phiên bản mới nhất.' })
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setGroupReviewStale(true)
        setGroupReviewRetry({
          feedback: review.feedback, sourceVersion: review.source_version,
          message: `Lịch trình đã có bản mới hơn. Preview nền v${review.base_version} không thể áp dụng; hãy tạo lại từ góp ý này.`,
        })
        await refreshLatestTrip()
      } else if (err instanceof Error && err.message === 'unauthorized') {
        saveToken(null); setToken(null)
      } else if (err instanceof Error && !(err instanceof TypeError)) {
        add({ role: 'error', text: err.message })
      } else {
        add({ role: 'error', text: 'Mất kết nối tới máy chủ. Kiểm tra server đã chạy chưa.' })
      }
    } finally {
      setBusy(false)
    }
  }

  const cancelGroup = async () => {
    if (!groupReview || tripId == null) return
    const reviewWasStale = groupReviewStale
    const result = await call(() => cancelGroupReview(token!, tripId, groupReview.review_id))
    if (!result) return
    setGroupReview(null); setGroupReviewStale(false)
    if (!reviewWasStale) setGroupReviewRetry(null)
  }

  const apply = async (option: number) => {
    const ev: ItineraryEvent | undefined = await call(() => applyProposal(token!, tripId!, proposal!.proposal_id, option))
    if (!ev) return
    setChanged(proposal!.options?.[option]?.changed ?? [])
    setProposal(null); setSearchPins([]); setSelected(null)
    setPlaces(ev.places); setItinerary(ev.itinerary); setVersion(ev.version)
    setLatest(ev.version); setVersions((vs) => [...vs, ev.version])
    add({ role: 'ai', text: `Đã áp dụng phương án — lịch trình bản ${ev.version}.` })
  }

  const send = async (message: string) => {
    if (viewingOld(version, latest)) await viewVersion(latest!)
    add({ role: 'user', text: message })
    await run((on) => streamTrip(token!, message, tripId, on))
    listTrips(token!).then(setTrips).catch(() => {})
  }
  const newTrip = () => {
    setTripId(null); setVersion(null); setProposal(null); setChat([]); setClarify(null); setConfirm(null)
    setItinerary(null); setSearchPins([]); setBudget(null); setVersions([]); setLatest(null); setPins([]); setSelected(null)
    setGroupReview(null); setGroupReviewStale(false); setGroupReviewRetry(null)
  }
  const answer = (tripId: number, a: Answers) => run((on) => streamPlan(token!, tripId, a, on))

  const current = trips.find((t) => t.id === tripId)
  const exportPdf = () => {
    if (!current || !itinerary || version == null) return
    setPrintModel(buildTripPrintModel(current, version, itinerary, places, new Date().toISOString()))
  }
  const left = panels.chat ? 80 + 340 + 16 : 80
  const right = itinerary && panels.timeline ? 384 + 32 : 16
  return (
    <>
      <div className="app-shell relative h-screen overflow-hidden bg-stone-200 font-sans text-stone-900">
        <MapView center={center} searchPins={searchPins} itinerary={itinerary} places={places}
          selected={selected} onSelect={setSelected} padding={{ left, right }} pins={pins}
          onPin={tripId != null && version != null && !proposal && !busy && !viewingOld(version, latest) ? pin : undefined} />
        <Rail busy={busy} trips={trips} currentId={tripId} onNewTrip={tripId != null ? newTrip : undefined}
          onOpenTrip={(id) => openTrip(id)} onLogout={logout}
          systemOpen={system} onSystem={() => setSystem((v) => !v)} />
        <FloatingPanel side="left" title={current ? tripLabel(current) : 'Chuyến mới'}
          subtitle={budget != null ? `Ngân sách ${vnd(budget)}` : 'Trợ lý lập lịch trình'}
          open={panels.chat} onToggle={() => openPanel('chat', !panels.chat)}
          badge={panels.chat ? 0 : unread}>
          <ChatPanel key={tripId ?? 'new'} items={chat} busy={busy} onSend={send}
            versions={versions} version={version} latest={latest} reviewPending={groupReview != null}
            onGroupReview={onGroupReview} onRetryGroupReview={retryGroupReview} retry={groupReviewRetry}>
            {groupReview && <GroupReviewPanel review={groupReview} stale={groupReviewStale} busy={busy}
              onApply={applyGroup} onCancel={cancelGroup} />}
            {clarify && <ClarifyCard questions={clarify.questions} busy={busy}
              onSubmit={(a) => answer(clarify.tripId, a)} />}
            {confirm && <ConfirmCard text={confirm.text} busy={busy}
              onYes={() => run((on) => streamReplan(token!, confirm, on))}
              onNo={() => { setConfirm(null); add({ role: 'ai', text: 'Đã giữ nguyên lịch trình.' }) }} />}
          </ChatPanel>
        </FloatingPanel>
        {itinerary && (
          <FloatingPanel side="right" title="Lịch trình" open={panels.timeline} onToggle={() => openPanel('timeline', !panels.timeline)}>
            <Timeline itinerary={itinerary} places={places} budget={budget} busy={busy} changed={changed}
              onDisrupt={tripId != null && version != null ? disrupt : undefined}
              versions={versions} version={version} latest={latest} pins={pins}
              onView={viewVersion} onRestore={restore} onPin={tripId != null && version != null && !proposal ? pin : undefined}
              onExportPdf={current && version != null ? exportPdf : undefined}
              selected={selected} onSelect={setSelected}>
              {proposal && <ProposalPanel proposal={proposal} busy={busy} onApply={apply}
                onClose={() => { setProposal(null); setSearchPins([]) }} />}
            </Timeline>
          </FloatingPanel>
        )}
        {system && <SystemPage token={token} onClose={() => setSystem(false)} />}
      </div>
      {printModel && <TripPrintView model={printModel} />}
    </>
  )
}
