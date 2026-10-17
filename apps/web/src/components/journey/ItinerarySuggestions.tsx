import type { ItinerarySuggestion, ItinerarySuggestions as Suggestions } from '../../api/client'

const styles: Record<string, [string, string, string, string]> = {
  balanced: ['Cân bằng', 'Balanced', 'Ưu tiên khung giờ sớm và độ phù hợp sở thích.', 'Prioritizes earlier slots and interest fit.'],
  budget: ['Ưu tiên tiết kiệm', 'Budget focused', 'Ưu tiên trải nghiệm có chi phí thấp trong các lựa chọn khả thi.', 'Prioritizes lower-cost feasible experiences.'],
  nearby: ['Ưu tiên ít di chuyển', 'Less travel', 'Ưu tiên chặng đi và chặng về ngắn theo API chỉ đường.', 'Prioritizes shorter outward and return travel from the routing API.'],
  relaxed: ['Ưu tiên hoạt động ngắn', 'Shorter activities', 'Ưu tiên hoạt động và chặng di chuyển ngắn.', 'Prioritizes shorter activities and travel legs.'],
  interests: ['Ưu tiên sở thích', 'Interest focused', 'Ưu tiên mức độ phù hợp với sở thích bạn đã chọn.', 'Prioritizes your selected interests.'],
}

export function ItinerarySuggestions({ data, locale, busy, onChoose, onCustomize }: {
  data: Suggestions; locale: 'vi' | 'en'; busy: boolean
  onChoose: (option: ItinerarySuggestion) => void
  onCustomize: (option: ItinerarySuggestion) => void
}) {
  const en = locale === 'en'
  const time = (value: string) => new Date(value).toLocaleTimeString(en ? 'en-GB' : 'vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit' })
  return <>
    <div className="mb-5">
      <span className="eyebrow-3d">{en ? 'A starting point for your trip' : 'Bắt đầu từ một lịch trình phù hợp'}</span>
      <h2 className="mt-2 text-2xl font-bold">{en ? `${data.returned_count} itineraries based on your choices` : `${data.returned_count} lịch trình theo lựa chọn của bạn`}</h2>
      <p className="mt-2 text-sm">{en ? 'Compare stops, experience costs and travel time. Choose an option to recheck availability and open its route, or customize it first.' : 'So sánh điểm dừng, chi phí trải nghiệm và thời gian di chuyển. Chọn một phương án để kiểm tra lại chỗ và xem tuyến đường, hoặc tùy chỉnh trước.'}</p>
      <p className="mt-2 text-sm">{en ? 'Experience prices exclude transport and personal spending. Travel times are estimates; availability is not reserved.' : 'Chi phí dưới đây là chi phí trải nghiệm, chưa gồm đi lại và chi tiêu cá nhân. Thời gian di chuyển là ước tính; chỗ chưa được giữ.'}</p>
      <p className="mt-2 inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700" role="status">
        {data.ranking_source === 'gemini'
          ? (en ? 'Gemini ranked feasible options' : 'Gemini xếp hạng các phương án khả thi')
          : (en ? 'Rule-based feasibility ranking' : 'Xếp hạng theo logic và điều kiện khả thi')}
      </p>
      {data.returned_count < 5 && <p role="status" className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{en ? `Found ${data.returned_count} distinct feasible options within your constraints. To find more, widen the time window or remove optional pinned stops.` : `Hiện tìm được ${data.returned_count} phương án khác nhau đáp ứng điều kiện. Để có thêm lựa chọn, bạn có thể mở rộng khung giờ hoặc bỏ bớt điểm đã ghim.`}</p>}
    </div>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.options.map((option, index) => {
        const plan = option.preview
        const copy = styles[option.style] || styles.balanced
        return <article key={plan.itinerary_id} className="flex flex-col rounded-2xl border border-emerald-200 bg-white p-5 text-slate-800 shadow-sm">
          <small className="font-semibold text-emerald-700">{en ? 'Option' : 'Phương án'} {index + 1}</small>
          <h3 className="mt-1 text-xl font-bold">{copy[en ? 1 : 0]}</h3>
          <p className="mt-2 text-sm text-slate-600">{copy[en ? 3 : 2]}</p>
          {option.recommendation_reason && <p className="mt-2 rounded-lg bg-emerald-50 p-2 text-sm text-emerald-950">{en ? 'Why it fits: ' : 'Vì sao phù hợp: '}{option.recommendation_reason}</p>}
          {option.relaxed_experience_names?.length ? <p className="mt-2 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{en ? `Could not fit these selected experiences: ${option.relaxed_experience_names.join(', ')}.` : `Không thể xếp các trải nghiệm đã chọn này: ${option.relaxed_experience_names.join(', ')}.`}</p> : null}
          {option.relaxed_poi_names?.length ? <p className="mt-2 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{en ? `Could not keep these pinned places: ${option.relaxed_poi_names.join(', ')}.` : `Không thể giữ các địa điểm đã ghim này trong phương án: ${option.relaxed_poi_names.join(', ')}.`}</p> : null}
          <div className="my-4 flex flex-wrap gap-2 text-sm font-semibold">
            <span className="rounded-lg bg-emerald-50 px-2 py-1">{plan.estimated_cost_vnd.toLocaleString('vi-VN')} ₫ / {en ? 'group' : 'nhóm'}</span>
            <span className="rounded-lg bg-slate-100 px-2 py-1">{plan.total_travel_min} {en ? 'min travel' : 'phút di chuyển'}</span>
            <span className="rounded-lg bg-slate-100 px-2 py-1">{plan.stops.length} {en ? 'stops' : 'điểm dừng'}</span>
          </div>
          <p className="text-xs text-slate-500">{en ? 'From' : 'Xuất phát'}: {plan.origin_label}</p>
          <ol className="my-3 flex-1 space-y-3">
            {plan.stops.map((stop, i) => <li key={stop.id} className="border-l-2 border-emerald-200 pl-3">
              <small className="text-emerald-700">{time(stop.start_at)}–{time(stop.end_at)}</small>
              <p className="text-sm font-semibold">{i + 1}. {stop.name}</p>
              <p className="text-xs text-slate-500">{stop.poi.name}</p>
            </li>)}
          </ol>
          <p className="text-sm">{en ? 'Return' : 'Về'}: {plan.destination_label}{plan.estimated_return_at ? ` · ${time(plan.estimated_return_at)}` : ''}</p>
          {plan.data_mode !== 'real' && <p className="mt-2 text-xs text-amber-800">{en ? 'Includes demo or unverified experience data.' : 'Có dữ liệu trải nghiệm mô phỏng hoặc chưa xác minh.'}</p>}
          {plan.stops.some(stop => !stop.availability_known) && <p className="mt-2 text-xs text-amber-800">{en ? 'Some availability needs confirmation.' : 'Một số điểm cần xác nhận lại tình trạng chỗ.'}</p>}
          <button type="button" disabled={busy} onClick={() => onChoose(option)} className="mt-4 rounded-xl bg-emerald-700 px-4 py-3 font-semibold text-white disabled:opacity-50">{en ? 'Choose and view route' : 'Chọn và xem tuyến đường'}</button>
          <button type="button" disabled={busy} onClick={() => onCustomize(option)} className="mt-2 rounded-xl border border-emerald-700 px-4 py-2 text-emerald-800 disabled:opacity-50">{en ? 'Customize this option' : 'Tùy chỉnh phương án này'}</button>
        </article>
      })}
    </div>
  </>
}
