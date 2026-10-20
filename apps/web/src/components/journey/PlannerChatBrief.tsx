import { ArrowRight, CalendarDays, CheckCircle2, Clock3, MapPin, Navigation, Plane, Sparkles, Users, Wallet } from 'lucide-react'
import type { Locale } from '../../i18n'
import type { ChatTripContext } from '../../journey'

type Requirement = { id: string; label: string; complete: boolean; anchor: string }

const tagLabels: Record<string, { vi: string; en: string }> = {
  'cafe-chill': { vi: 'Cafe', en: 'Cafe' }, 'an-chay': { vi: 'Ăn chay', en: 'Vegetarian food' },
  'an-dia-phuong': { vi: 'Ẩm thực địa phương', en: 'Local food' }, 'hai-san': { vi: 'Hải sản', en: 'Seafood' },
  'thien-nhien': { vi: 'Thiên nhiên', en: 'Nature' }, 'check-in': { vi: 'Check-in', en: 'Photo stops' },
  'lich-su': { vi: 'Lịch sử', en: 'History' }, 'van-hoa': { vi: 'Văn hoá', en: 'Culture' },
  dem: { vi: 'Đời sống về đêm', en: 'Nightlife' }, 'yen-tinh': { vi: 'Yên tĩnh', en: 'Quiet places' },
  'soi-dong': { vi: 'Sôi động', en: 'Lively places' }, 'gia-dinh': { vi: 'Gia đình', en: 'Family friendly' },
  'lang-man': { vi: 'Lãng mạn', en: 'Romantic' }, 'mua-sam': { vi: 'Mua sắm', en: 'Shopping' },
  'view-dep': { vi: 'View đẹp', en: 'Scenic views' }, 'gia-re': { vi: 'Giá rẻ', en: 'Affordable' },
  'sang-trong': { vi: 'Sang trọng', en: 'Upscale' },
}

const paceLabels: Record<string, { vi: string; en: string }> = {
  'thong-tha': { vi: 'Thư thả', en: 'Relaxed' }, vua: { vi: 'Vừa phải', en: 'Balanced' }, day: { vi: 'Đi nhiều', en: 'Packed' },
}

const arrivalLabels: Record<string, { vi: string; en: string }> = {
  'may-bay': { vi: 'Máy bay', en: 'Plane' }, 'xe-khach': { vi: 'Xe khách', en: 'Coach' },
  tau: { vi: 'Tàu hoả', en: 'Train' }, 'tu-lai': { vi: 'Tự lái', en: 'Self-drive' },
}

export function PlannerChatBrief({ context, locale, date, endDate, durationDays, startTime, endTime, durationLabel,
  groupSize, budget, travelModeLabel, requirements, onReturnChat, onGoTo }: {
  context: ChatTripContext; locale: Locale; date: string; endDate: string; durationDays: number
  startTime: string; endTime: string; durationLabel: string; groupSize: number; budget: number
  travelModeLabel: string; requirements: Requirement[]; onReturnChat: () => void
  onGoTo: (requirement: Requirement) => void
}) {
  const en = locale === 'en'
  const complete = requirements.filter((item) => item.complete).length
  const next = requirements.find((item) => !item.complete)
  const formatDate = (value: string) => value
    ? new Intl.DateTimeFormat(en ? 'en-GB' : 'vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', day: 'numeric', month: 'short', year: 'numeric' })
      .format(new Date(`${value}T12:00:00+07:00`))
    : (en ? 'Choose a date' : 'Chọn ngày đi')
  const label = (tag: string) => tagLabels[tag]?.[locale] ?? tag
  const groups = [
    { title: en ? 'Must include' : 'Bắt buộc', tags: context.requiredTags, tone: 'required' },
    { title: en ? 'Also interested in' : 'Sở thích thêm', tags: context.preferredTags, tone: 'preferred' },
    { title: en ? 'Avoid' : 'Muốn tránh', tags: context.avoidedTags, tone: 'avoided' },
  ]
  const pace = paceLabels[context.pace]?.[locale] ?? context.pace
  const arrival = context.arrivalMode ? arrivalLabels[context.arrivalMode]?.[locale] ?? context.arrivalMode : null

  return <section className="planner-chat-board" aria-labelledby="planner-chat-title">
    <div className="planner-chat-board-main">
      <div className="planner-chat-board-topline">
        <span className="planner-chat-source"><Sparkles size={14} /> {en ? 'Synced from AI Chat' : 'Đã đồng bộ từ AI Chat'}</span>
        <button type="button" className="planner-chat-return" onClick={onReturnChat}>{en ? 'Edit in chat' : 'Sửa trong Chat'} <ArrowRight size={14} /></button>
      </div>
      <div className="planner-chat-heading">
        <div>
          <span className="planner-chat-eyebrow">{en ? 'YOUR TRIP BRIEF' : 'THÔNG TIN CHUYẾN ĐI'}</span>
          <h2 id="planner-chat-title">{context.destinationName}</h2>
          <p>{en ? 'Review the details AI understood. Add only what is needed to check a route.' : 'Thông tin AI đã hiểu được điền sẵn. Bạn chỉ cần bổ sung dữ liệu để kiểm tra tuyến.'}</p>
        </div>
        <span className="planner-chat-source-id">{en ? `Chat trip #${context.tripId}` : `Chuyến Chat #${context.tripId}`}</span>
      </div>

      <div className="planner-chat-stats">
        <article className="planner-chat-stat"><CalendarDays size={16} /><span>{en ? 'Travel dates' : 'Ngày đi'}</span>
          <strong>{formatDate(date)}</strong><small>{date ? `${durationDays} ${en ? 'days' : 'ngày'} · ${formatDate(endDate)}` : (en ? 'Choose a date below' : 'Chọn ngày ở bên dưới')}</small></article>
        <article className="planner-chat-stat"><Users size={16} /><span>{en ? 'Travelers' : 'Số người'}</span>
          <strong>{groupSize} {en ? (groupSize === 1 ? 'person' : 'people') : 'người'}</strong><small>{(en ? 'Pace: ' : 'Nhịp đi: ') + pace}</small></article>
        <article className="planner-chat-stat"><Wallet size={16} /><span>{en ? 'Group budget' : 'Ngân sách nhóm'}</span>
          <strong>{budget.toLocaleString('vi-VN')} ₫</strong><small>~{Math.floor(budget / Math.max(groupSize, 1)).toLocaleString('vi-VN')} ₫ / {en ? 'person' : 'người'}</small></article>
        <article className="planner-chat-stat"><Navigation size={16} /><span>{en ? 'Travel mode' : 'Phương tiện'}</span>
          <strong>{travelModeLabel || (en ? 'Choose below' : 'Chọn bên dưới')}</strong>
          <small>{arrival && <><Plane size={12} /> {en ? 'Arriving by ' : 'Đến bằng '}{arrival}</>}
            {arrival && context.originCity && ' · '}
            {context.originCity ? `${en ? 'From ' : 'Đi từ '}${context.originCity}` : !arrival ? (en ? 'Within the destination' : 'Di chuyển trong thành phố') : null}
          </small></article>
      </div>

      <div className="planner-chat-time-window">
        <div className="planner-chat-time-icon"><Clock3 size={17} /></div>
        <div className="planner-chat-time-copy"><strong>{en ? 'Planning time window' : 'Khung giờ lập lịch'}</strong>
          <span>{startTime}–{endTime} · {durationLabel}</span>
          <small>{[
            context.arrivalTime && `${en ? 'Arrival' : 'Đến nơi'} ${context.arrivalTime}`,
            context.lastDayEnd && `${en ? 'Activities finish' : 'Xong hoạt động'} ${context.lastDayEnd}`,
            context.departureTime && `${en ? 'Leaving city' : 'Rời thành phố'} ${context.departureTime}`,
          ].filter(Boolean).join(' · ') || (en ? 'Based on your chat pace. You can adjust the times below.' : 'Theo nhịp đi trong Chat; bạn có thể chỉnh giờ bên dưới.')}</small>
        </div>
        <span className="planner-chat-window-note">{en ? 'Editable below' : 'Có thể chỉnh bên dưới'}</span>
      </div>

      <div className="planner-chat-preferences">
        {groups.map((group) => <div key={group.tone} className="planner-chat-tag-group">
          <span className={`planner-chat-tag-title planner-chat-tag-title-${group.tone}`}>{group.title}</span>
          <div className="planner-chat-tag-list">{group.tags.length
            ? group.tags.map((tag) => <span key={tag} className={`planner-chat-tag planner-chat-tag-${group.tone}`}>{label(tag)}</span>)
            : <span className="planner-chat-empty">{en ? 'None specified' : 'Chưa nêu'}</span>}</div>
        </div>)}
      </div>
    </div>

    <aside className="planner-chat-board-side">
      <div className="planner-readiness-heading"><div><span className="planner-chat-eyebrow">{en ? 'ROUTE READINESS' : 'SẴN SÀNG LẬP TUYẾN'}</span>
        <h3>{complete}/{requirements.length} {en ? 'details complete' : 'thông tin đã có'}</h3></div>
        <span className={`planner-readiness-count ${next ? 'is-pending' : 'is-ready'}`}>{next ? (en ? `${requirements.length - complete} left` : `Còn ${requirements.length - complete}`) : (en ? 'Ready' : 'Sẵn sàng')}</span></div>
      <div className="planner-readiness-track"><span style={{ width: `${complete / requirements.length * 100}%` }} /></div>
      <div className="planner-readiness-list">{requirements.map((item) => <button key={item.id} type="button"
        className={`planner-readiness-item ${item.complete ? 'is-complete' : 'is-pending'}`} onClick={() => onGoTo(item)}>
        <CheckCircle2 size={16} /><span>{item.label}</span><small>{item.complete ? (en ? 'Done' : 'Đã có') : (en ? 'Add' : 'Bổ sung')}</small>
      </button>)}</div>
      <div className="planner-chat-area-note"><MapPin size={15} /><span>{en
        ? 'Suggestions use the District 1 pilot catalog and selected interest categories. Required and avoided tags are carried over, but the planner does not yet enforce each tag as a hard filter. Exact start and return points are needed for route checks.'
        : 'Gợi ý dùng danh mục pilot Quận 1 và nhóm sở thích đã chọn. Tag bắt buộc/tránh được giữ từ Chat; bộ máy hiện chưa lọc cứng theo từng tag. Cần điểm xuất phát và điểm quay về để kiểm tra tuyến.'}</span></div>
      {next ? <button type="button" className="planner-chat-primary" onClick={() => onGoTo(next)}>
        {en ? `Add ${next.label.toLowerCase()}` : `Bổ sung ${next.label.toLowerCase()}`} <ArrowRight size={16} />
      </button> : <p className="planner-chat-ready-note" role="status">{en
        ? 'Your details are ready. Use the single route button below the form to search.'
        : 'Thông tin đã sẵn sàng. Dùng nút tìm tuyến duy nhất bên dưới biểu mẫu để tiếp tục.'}</p>}
    </aside>
  </section>
}
