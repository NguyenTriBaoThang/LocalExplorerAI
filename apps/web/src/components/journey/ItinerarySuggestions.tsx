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
  const date = (value: string) => new Date(value).toLocaleDateString(en ? 'en-GB' : 'vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit' })
  return <div className="planner-route-results">
    <div className="planner-route-results-heading mb-5">
      <span className="planner-route-kicker">{en ? 'RANKED ROUTE OPTIONS' : 'CÁC TUYẾN ĐƯỢC XẾP HẠNG'}</span>
      <h2 id="planner-routes-title" className="mt-2 text-2xl font-bold">{en ? `${data.returned_count} routes based on your choices` : `${data.returned_count} tuyến theo lựa chọn của bạn`}</h2>
      <p className="mt-2 text-sm">{en ? 'Compare stops, experience costs and travel time. Choose an option to recheck availability and open its route, or customize it first.' : 'So sánh điểm ghé, chi phí và thời gian di chuyển. Chọn một phương án để kiểm tra lại chỗ và mở tuyến, hoặc tùy chỉnh trước.'}</p>
      <p className="mt-2 text-sm">{en ? 'Experience prices exclude transport and personal spending. Travel times are estimates; availability is not reserved.' : 'Chi phí chưa gồm đi lại và chi tiêu cá nhân. Thời gian di chuyển là ước tính; chỗ chưa được giữ.'}</p>
      <p className="planner-rank-source mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold" role="status">
        {data.ranking_source === 'ranker+gemini'
          ? (en ? 'Ranker ordering · Gemini explanations' : 'Ranker xếp thứ tự · Gemini giải thích')
          : data.ranking_source === 'ranker'
            ? (en ? 'Ranker ordered feasible itineraries' : 'Ranker xếp hạng lịch trình khả thi')
            : data.ranking_source === 'gemini'
              ? (en ? 'Gemini ranked feasible options' : 'Gemini xếp hạng các phương án khả thi')
              : (en ? 'Rule-based feasibility ranking' : 'Xếp hạng theo logic và điều kiện khả thi')}
      </p>
      {data.returned_count < 5 && <p role="status" className="planner-routes-count-note mt-3 rounded-xl p-3 text-sm">{en ? `Found ${data.returned_count} distinct feasible options within your constraints. To find more, widen the time window or remove optional pinned stops.` : `Tìm được ${data.returned_count} phương án khác nhau đáp ứng điều kiện. Muốn có thêm lựa chọn, hãy nới khung giờ hoặc bỏ bớt điểm ghé đã ghim.`}</p>}
    </div>
    {data.options.length === 0 ? <div className="planner-routes-no-results" role="status">
      <strong>{en ? 'No feasible route was found for these settings.' : 'Chưa tìm được tuyến khả thi với lựa chọn hiện tại.'}</strong>
      <p>{en ? 'Try a wider time window, a larger budget, a different travel mode, or remove some pinned stops.' : 'Thử nới khung giờ, tăng ngân sách, đổi phương tiện hoặc bỏ bớt địa điểm ghim.'}</p>
    </div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.options.map((option, index) => {
        const plan = option.preview
        const copy = styles[option.style] || styles.balanced
        return <article key={plan.itinerary_id} className="planner-route-card flex flex-col rounded-2xl p-5 shadow-sm">
          <small className="planner-route-number font-semibold">{en ? 'Route' : 'Tuyến'} {index + 1}</small>
          <h3 className="mt-1 text-xl font-bold">{copy[en ? 1 : 0]}</h3>
          <p className="planner-route-copy mt-2 text-sm">{copy[en ? 3 : 2]}</p>
          {option.recommendation_reason && <p className="planner-route-reason mt-2 rounded-lg p-2 text-sm">{en ? 'Why it fits: ' : 'Vì sao phù hợp: '}{option.recommendation_reason}</p>}
          {option.relaxed_experience_names?.length ? <p className="planner-route-warning mt-2 rounded-lg p-2 text-sm">{en ? `Could not fit these selected experiences: ${option.relaxed_experience_names.join(', ')}.` : `Không thể xếp các trải nghiệm đã chọn này: ${option.relaxed_experience_names.join(', ')}.`}</p> : null}
          {option.relaxed_poi_names?.length ? <p className="planner-route-warning mt-2 rounded-lg p-2 text-sm">{en ? `Could not keep these pinned places: ${option.relaxed_poi_names.join(', ')}.` : `Không thể giữ các địa điểm đã ghim này trong phương án: ${option.relaxed_poi_names.join(', ')}.`}</p> : null}
          <div className="planner-route-metrics my-4 flex flex-wrap gap-2 text-sm font-semibold">
            <span>{plan.estimated_cost_vnd.toLocaleString('vi-VN')} ₫ / {en ? 'group' : 'nhóm'}</span>
            <span>{plan.total_travel_min} {en ? 'min travel' : 'phút di chuyển'}</span>
            <span>{plan.stops.length} {en ? 'stops' : 'điểm ghé'}</span>
            {(data.ranking_source === 'ranker' || data.ranking_source === 'ranker+gemini') && (
              <span className="planner-route-rank rounded-lg px-2 py-1">
                Ranker: {en ? `rank ${index + 1}/${data.options.length}` : `hạng ${index + 1}/${data.options.length}`}
              </span>
            )}
          </div>
          <p className="planner-route-origin text-xs">{en ? 'Start' : 'Xuất phát'}: {plan.origin_label}</p>
          <ol className="my-3 flex-1 space-y-3">
            {plan.stops.map((stop, i) => <li key={stop.id} className="border-l-2 border-emerald-200 pl-3">
              <small className="planner-route-time">{date(stop.start_at)} · {time(stop.start_at)}–{time(stop.end_at)}</small>
              <p className="planner-route-stop-name text-sm font-semibold">{i + 1}. {stop.name}</p>
              <p className="planner-route-poi text-xs">{stop.poi.name}</p>
            </li>)}
          </ol>
          <p className="planner-route-origin text-sm">{en ? 'Finish' : 'Điểm đến'}: {plan.destination_label}{plan.estimated_return_at ? ` · ${time(plan.estimated_return_at)}` : ''}</p>
          {plan.data_mode !== 'real' && <p className="planner-route-warning mt-2 text-xs">{en ? 'Includes demo or unverified experience data.' : 'Có dữ liệu trải nghiệm mô phỏng hoặc chưa xác minh.'}</p>}
          {plan.stops.some(stop => !stop.availability_known) && <p className="planner-route-warning mt-2 text-xs">{en ? 'Some availability needs confirmation.' : 'Một số điểm cần xác nhận lại tình trạng chỗ.'}</p>}
          <button type="button" disabled={busy} onClick={() => onChoose(option)} className="planner-route-primary mt-4 rounded-xl px-4 py-3 font-semibold disabled:opacity-50">{en ? 'Choose and view route' : 'Chọn và xem tuyến đường'}</button>
          <button type="button" disabled={busy} onClick={() => onCustomize(option)} className="planner-route-secondary mt-2 rounded-xl px-4 py-2 disabled:opacity-50">{en ? 'Customize this option' : 'Tùy chỉnh phương án này'}</button>
        </article>
      })}
    </div>}
  </div>
}
