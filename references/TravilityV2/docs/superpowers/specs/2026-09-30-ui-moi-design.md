# UI mới: map toàn màn hình, rail, panel nổi, Map ↔ Timeline

> 2026-09-30 · Lát T4 trong [ROADMAP](../../ROADMAP.md) · Issue #2, #16, #4 · PRD §7.5.
> Mockup đã duyệt: https://claude.ai/artifact/FqsEi2pjdHPdM2qoYD83ih (bản 1). Thuật ngữ theo [CONTEXT.md](../../../CONTEXT.md).

## 1. Mục tiêu

Màn chính giống mockup, và kịch bản demo (PRD §3.2) vẫn chạy như trước:

1. Bản đồ phủ kín cửa sổ. Rail ở bên trái, panel Chat nổi bên trái, panel Timeline nổi bên phải, mỗi panel thu gọn được.
2. Bấm Stop trên Timeline thì bản đồ bay tới Place và mở popup Place. Bấm pin trên bản đồ thì Timeline cuộn tới Stop đó và tô viền.
3. Khi vừa có Itinerary, hoặc khi mở Trip, xem version, restore, bản đồ chỉ `fitBounds` toàn tuyến. Camera bay qua từng Stop chỉ khi bấm "Xem hành trình", và dừng ngay khi người dùng kéo bản đồ hoặc bấm Dừng.
4. Tải lại app vẫn thấy đường tuyến.

Giữ nguyên: luồng SSE, `api.ts`, ClarifyCard, ConfirmCard, ProposalPanel, Login.

## 2. Quyết định (chốt trong buổi grill 2026-09-30)

| # | Quyết định | Lý do |
|---|---|---|
| U1 | Mockup là HTML tĩnh (Artifact), Claude dựng, nhóm duyệt qua link | Nhanh, sát Tailwind thật; Onboarding và Hồ sơ đã cắt nên không vẽ |
| U2 | #2, #16 và #4 làm chung một lát | Popup và "Xem hành trình" nằm trên layout mới; tách ra thì phải làm popup hai lần |
| U3 | Place chưa có `photo_url` thì dùng ô màu theo `kind` kèm icon | 37/37 Place chưa có ảnh; ảnh thật về cùng mốc dữ liệu 15/10 |
| U4 | Hai panel nổi hai bên, thu gọn được; cửa sổ < 1100px chỉ mở một panel | Vừa chat vừa nhìn lịch như hiện tại, ít phải đổi component nhất |
| U5 | Rail: logo, ＋ Chuyến mới, 🗂 Chuyến đi của tôi (popover), ⎋ Đăng xuất. Không có 👤 | Hồ sơ đã cắt |
| U6 | Popup Place chỉ có nút Ghim. Nút báo sự cố nằm trên thẻ Stop **đang chọn** | Đúng acceptance của #4, popup gọn |
| U7 | Nhật làm `PlacePopup` theo props ở §4.3. Tới task đó mà chưa xong thì mình tự làm | Phân vai Q7/Q8 |
| U8 | State `selected` đặt ở `App`, không dùng Context hay thư viện state | Chỉ một state dùng chung; App khoảng 200 dòng |

## 3. Server

`agent.place_brief` trả thêm `open_hours` và `description`. Đây là nguồn chung của `places` trong các event `tool_call` và `itinerary`, nên mọi Itinerary lưu **từ nay** đều có hai trường này.

Itinerary đã lưu từ trước không có hai trường đó. Client coi chúng là tuỳ chọn; thiếu thì popup ẩn dòng giờ mở và mô tả. Không migrate dữ liệu cũ vì chỉ là dữ liệu dev.

Test: `place_brief` có `open_hours` và `description`; event `itinerary` của một lượt lập lịch có đủ hai trường.

## 4. Client

### 4.1 Layout (`App.tsx`)
```
<div relative h-screen overflow-hidden>
  <MapView absolute inset-0 …/>
  <Rail …/>                                   // absolute left-0, w-16
  <FloatingPanel side="left"  title=… open=chatOpen  onToggle>  <ChatPanel …/>  </FloatingPanel>
  <FloatingPanel side="right" title="Lịch trình" open=tlOpen onToggle> <Timeline …/> </FloatingPanel>
  {itinerary && <TourButton …/>}              // đáy giữa
</div>
```
- `FloatingPanel`: khung nổi (nền mờ, bo góc, đổ bóng). Khi đóng thì còn một nút nhỏ ghi tiêu đề (Chat có badge số tin). Chỉ lo hiện/ẩn, không biết gì về nội dung.
- Cửa sổ < 1100px (`matchMedia`): mở panel này thì panel kia đóng. Hàm thuần `togglePanels(state, side, narrow)` có test.
- Header panel Chat: "Destination · N ngày" và dòng phụ "Ngân sách …". Chưa có Trip thì ghi "Chuyến mới".
- Có Itinerary thì Timeline tự mở. Chưa có thì Timeline ẩn hẳn, không hiện nút thu gọn.

### 4.2 Rail + popover (`Rail.tsx`, mới)
- Nút ＋ (khi có Trip đang mở), 🗂, ⎋. Có `aria-label` và `title` tiếng Việt.
- Bấm 🗂 thì mở popover danh sách `trips` (Destination · số ngày · "Tạo dd/mm"). Chọn một Trip, bấm ra ngoài hoặc bấm Esc thì popover đóng.
- Gỡ `<details>` "Chuyến đi của tôi" và nút Đăng xuất khỏi `ChatPanel`.

### 4.3 PlacePopup (`PlacePopup.tsx`, mới, giao Nhật)
```ts
props: { place: Place; date: string | null; pinned: boolean; onPin?: (pinned: boolean) => void }
```
- Ảnh: `photo_url`, hoặc `<PlaceThumb kind>` (ô màu + icon theo `kind`, dùng chung với thẻ Stop).
- Tên, chip loại, giá (`0` → "Miễn phí"), Trong nhà/Ngoài trời, giờ mở hôm đó từ `openToday`, mô tả.
- Nút 📌 Ghim / Đã ghim (`aria-pressed`). Không có `onPin` (đang xem bản cũ, đang mở Proposal) thì ẩn nút.
- Hiển thị bằng `<Popup>` của react-map-gl, neo tại Place đang chọn.

### 4.4 Hàm thuần mới (`place.ts`, có test vitest)
- `openToday(open_hours | undefined, date: string | null): string | null`
  - `{}` → "Mở cả ngày"
  - có giờ của ngày đó → "Mở hôm nay 07:00–22:00"
  - `null` → "Hôm nay đóng cửa"
  - thiếu `open_hours` hoặc `date` → `null` (ẩn dòng)
  - Khoá ngày trong tuần giống server (`mon`…`sun`), xem thêm khoá `daily` nếu có.
- `kindStyle(kind) → { label, icon, className }` cho `cafe`, `an-uong`, `tham-quan`, `cho-o`, `giai-tri`; kind lạ dùng mặc định.

### 4.5 Map ↔ Timeline (`selected` ở `App`)
- `selected` (kiểu ở dòng Stay bên dưới). Đặt về `null` khi đổi Trip, version hoặc Itinerary.
- Timeline: bấm thẻ Stop thì `onSelect(day, stop)`. Thẻ đang chọn có viền vàng, hiện các nút báo sự cố, và `scrollIntoView({block: 'nearest'})` mỗi khi `selected` đổi. Nút ghim và nút sự cố gọi `stopPropagation`.
- MapView: có `selected` thì `flyTo` Place đó (zoom 15) và mở `PlacePopup`. Bấm marker thì `onSelect`. Đóng popup thì `onSelect(null)`.
- Stay: marker "Chỗ ở" bấm được và mở popup không có nút Ghim (Stay không ghim được). Kiểu đầy đủ: `selected: { day: number; stop: number } | 'stay' | null`.
- Ghim trong popup gọi đúng hàm `pin` của App như nút trên Timeline.

### 4.6 Camera (`MapView.tsx`)
- Bỏ vòng bay tự động trong effect vẽ tuyến.
- Effect theo `itinerary`: vẽ tuyến rồi `fitBounds` mọi Stop và Stay (padding chừa chỗ hai panel đang mở).
- `TourButton` → `tour()`: bay lần lượt qua các Stop theo ngày và giờ (dùng lại tham số bay hiện có), cập nhật `selected` để Timeline chạy theo. Nút đổi thành "⏹ Dừng · Ngày d · điểm i/n · tên".
- Dừng khi bấm Dừng, khi `onMoveStart` có `originalEvent` (người dùng kéo hoặc cuộn), hoặc khi Itinerary đổi. Dùng cờ huỷ trong `useRef`, không dùng `setTimeout` chồng nhau.
- `prefers-reduced-motion`: `flyTo` và `fitBounds` dùng `duration: 0`.

### 4.7 Lỗi không vẽ tuyến sau khi tải lại
DB có đủ Leg (đã kiểm tra: `from_place_id` và `to_place_id` đầy đủ), nên lỗi ở client. Task đầu của plan: tái hiện (đăng nhập, có Trip, tải lại), tìm nguyên nhân gốc theo systematic-debugging, sửa rồi ghi lại. Nghi ngờ hàng đầu: `routes` được set trước khi style Goong load xong, hoặc `places` lúc mở Trip không khớp khoá.

### 4.8 Giao diện
- Token màu trong `index.css` (`@theme` của Tailwind 4) theo mockup:
  - `pine` #1f4d3a
  - `pine-soft` #e3ece5
  - `marigold` #e0a21b
  - `mist` #f3f5f1
  - Màu tuyến giữ `DAY_COLORS`.
- Font Be Vietnam Pro qua `<link>` Google Fonts trong `index.html`, fallback `system-ui`. App vốn đã cần mạng (Gemini, Goong) nên không thêm dependency npm.
- Logo: SVG núi đơn giản như mockup, đặt trong Rail và favicon.
- Empty state (chưa có Trip): câu chào "Cuối tuần này bạn muốn đi đâu?" kèm 3 gợi ý bấm được. Bấm gợi ý thì gửi luôn tin đó.

## 5. Lỗi
- Popup mở cho Place đã biến mất khỏi Itinerary (sau restore hoặc apply): `selected` về `null` khi Itinerary đổi, nên không mở được.
- Ghim lỗi (422/409): bong bóng đỏ trong chat như hiện có. Nếu Chat đang thu gọn thì badge tăng.
- Goong Direction lỗi: vẫn vẽ đường thẳng (giữ `legLine` hiện có).

## 6. Test
- Server (pytest): §3.
- Client (vitest, không DOM): `openToday`, `kindStyle`, `togglePanels`, và hàm thứ tự tour `tourStops(itinerary) → [{day, stop}]`.
- E2E thủ công (Playwright + Gemini thật, rồi một lần trên app desktop):
  1. Lập Trip Đà Lạt.
  2. Bấm Stop và pin qua lại hai chiều.
  3. Ghim trong popup.
  4. "Xem hành trình" rồi kéo map giữa chừng thì dừng.
  5. Thu gọn và mở hai panel.
  6. Thu cửa sổ về 1000px.
  7. Tải lại: thấy tuyến và không có camera tự bay.

## 7. Ngoài phạm vi
- Ảnh Place thật (mốc dữ liệu 15/10), Onboarding, Hồ sơ.
- Animate Stop vừa đổi trên bản đồ. Timeline đã có viền `changed`.
- Marker Hub và Leg tới/từ Hub.
- Km thật bằng Distance Matrix (#7, Thành).
- Các lỗi nhỏ còn tồn từ lát Revision (restore trả 500 khi trùng version, thiếu câu "Bỏ ghim" ở client…). Để một lát dọn riêng.
