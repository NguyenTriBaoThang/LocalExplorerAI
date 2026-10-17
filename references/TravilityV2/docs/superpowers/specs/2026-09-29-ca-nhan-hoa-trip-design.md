# Cá nhân hoá Trip — Design

> 2026-09-29 · Trạng thái: chờ review · Liên quan: PRD §5.2, §5.3, §5.5, §5.6, §6; ADR-0001, ADR-0005.
> Thuật ngữ theo [CONTEXT.md](../../../CONTEXT.md); thuật ngữ mới ở mục 9.

## 1. Vấn đề

AI hiện lập lịch chỉ từ một câu chat → `Trip` (Destination, số ngày, Budget, Tag, Pace, Travel Mode xe máy/Grab). Nó không biết:

- người dùng từ đâu tới, mấy giờ đến và mấy giờ về → ngày 1 xếp Stop lúc 8h dù 14h mới tới;
- người dùng đã có xe riêng chưa → vẫn tính tiền thuê xe máy;
- người dùng đã đặt chỗ ở chưa → AI tự chọn Stay khác;
- người dùng đi vì một điểm cụ thể ("đi Huế để thăm Kinh thành") → không đảm bảo điểm đó có trong Itinerary;
- sở thích giữa các chuyến → lần nào cũng phải nói lại.

**Mục tiêu:** Itinerary phản ánh hoàn cảnh thật của người dùng, vẫn giữ hai nguyên tắc: AI chỉ chọn Place thật (ADR-0001), tiền/Leg/Conflict do code tính.

**Thành công khi:** với câu "Đi Đà Lạt 2 ngày, 5 triệu, thăm Thung lũng Tình Yêu" + trả lời "đã đặt KS X, đến 14h, về 16h, đi ô tô riêng", Itinerary: có Thung lũng Tình Yêu; ngày 1 không có Stop trước 15h; ngày cuối không có Stop sau 14h30; Stay là KS X với chi phí 0; không có tiền thuê xe.

## 2. Quyết định

| # | Chủ đề | Quyết định |
|---|---|---|
| D1 | Nơi xuất phát | Chỉ dùng để căn giờ đến/về. Không tính tiền/thời gian liên tỉnh (giữ ADR-0005). |
| D2 | Chỗ ở đã đặt | Tìm trong Place `kind=cho-o` trước; không có → Goong Geocoding (server). Lưu là **Booked Stay**, chi phí 0. |
| D3 | Điểm phải đến | Chỉ Place có sẵn. Code kiểm tra Draft chứa nó; thiếu → Conflict. Không có trong DB → báo rõ, vẫn lập lịch. |
| D4 | Thu thập thông tin | Parse câu chat; thiếu thông tin quan trọng → hỏi lại **một vòng** bằng chip, có "Bỏ qua, cứ lên lịch". |
| D5 | Phương tiện | Thêm Travel Mode `xe-may-rieng`, `o-to-rieng`. Thêm **Arrival Mode** (máy bay/xe khách/tàu/tự lái) chỉ để biết điểm xuất phát ngày 1. |
| D6 | Cá nhân hoá lâu dài | Traveler Profile (PRD §5.2) + thành phố đang sống + có xe máy/ô tô riêng. Câu chat thắng Profile. |
| D7 | Dữ liệu | Tính năng không phụ thuộc Destination; demo bằng Đà Lạt. Thêm Huế là việc dữ liệu riêng. |

## 3. Luồng

```
POST /trips {message}                                   (SSE)
  thinking → parse_trip (LLM) → merge Traveler Profile → resolve Must-visit, Booked Stay
  → lưu Trip → event trip
  → missing_questions(trip) rỗng?  ── có ──► forecast → plan() → itinerary      (như hiện tại)
                                   └ không ─► event clarify {trip_id, questions} → đóng stream

POST /trips/{id}/plan {answers | skip:true}             (SSE)
  áp answers vào Trip bằng code (không gọi LLM) → resolve Booked Stay nếu có tên
  → cập nhật trips.spec → event trip → forecast → plan() → itinerary
```

- **Code quyết định thiếu gì**, không phải LLM: tool `record_trip` để trống trường người dùng không nói; sau khi merge Profile, trường còn trống và nằm trong danh sách sau thì hỏi:
  1. `stay` — "Bạn đã đặt chỗ ở chưa?" · chip: *Đã đặt (nhập tên)* / *Để AI chọn*.
  2. `travel_mode` — "Bạn di chuyển trong thành phố bằng gì?" · chip: *Thuê xe máy* / *Grab* / *Xe máy riêng* / *Ô tô riêng*.
  3. `arrival` — chỉ khi Trip có ngày đi: "Mấy giờ bạn tới và mấy giờ về?" · ô giờ đến, ô giờ về, chip Arrival Mode.
- Hỏi tối đa một vòng. `/plan` với trường vẫn trống → dùng mặc định (Stay: AI chọn; Travel Mode: `xe-may`; không ràng buộc giờ).
- `/plan` trên Trip đã có Itinerary → 409.

## 4. Mô hình dữ liệu

### 4.1 `Trip` (`server/app/domain.py`)
Thêm (đều tuỳ chọn, mặc định rỗng):

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `origin_city` | `str \| None` | Thành phố xuất phát, để hiển thị và gợi ý Arrival Mode. |
| `arrival_mode` | `Literal["may-bay","xe-khach","tau","tu-lai"] \| None` | |
| `arrival_time` | `HHMM \| None` | Giờ tới Destination ngày 1. |
| `departure_time` | `HHMM \| None` | Giờ rời Destination ngày cuối. |
| `booked_stay` | `BookedStay \| None` | `{name, lat, lon, place_id: int \| None}`. |
| `stay_decided` | `bool` | `True` khi người dùng đã trả lời câu `stay` (kể cả "để AI chọn"). |
| `must_visit_place_ids` | `list[int]` | Place bắt buộc đã khớp. |
| `unmatched_must_visit` | `list[str]` | Tên người dùng nêu nhưng không có trong DB. |

`travel_mode` đổi thành `TravelMode | None` ở bước parse (None = chưa nói); khi lập lịch luôn có giá trị. `TravelMode` thêm `xe-may-rieng`, `o-to-rieng`.

### 4.2 `Itinerary`, `Leg`, `Conflict`
- `Itinerary.booked_stay: BookedStay | None` — khi Stay không phải Place. `stay_place_id` giữ nguyên cho Stay là Place.
- `Leg.from_place_id`, `to_place_id` → `int | None`; `None` = Booked Stay hoặc Hub. `Leg.mode` thêm `"o-to"`.
- `Conflict.kind` thêm `before_arrival`, `after_departure`, `missing_must_visit`.

### 4.3 Dữ liệu Destination
`data/places/<dest>.json` → `destination.hubs` tuỳ chọn: `{"may-bay": {"name","lat","lon"}, "xe-khach": {...}, "tau": {...}}`. Cần cột `hubs jsonb` trong bảng `destinations`; `import_places` ghi cột này.

### 4.4 Bảng `traveler_profiles` (`server/app/schema.sql`)
`user_id` (PK, FK users) · `home_city` · `has_motorbike` · `has_car` · `required_tags` · `preferred_tags` · `avoided_tags` · `pace` · `travel_mode` · `updated_at`.

## 5. Thành phần

| Đơn vị | File | Việc | Phụ thuộc |
|---|---|---|---|
| `parse_trip` | `server/app/agent.py` | Tool `record_trip` thêm trường ở 4.1 + `must_visit_names: list[str]`, `booked_stay_name: str`. Không đoán trường người dùng không nói. | LLM |
| `merge_profile(trip, profile)` | `server/app/profile.py` | Điền trường trống từ Profile; `has_car` → `o-to-rieng`, `has_motorbike` → `xe-may-rieng`; Tag hợp nhất (chat thắng khi mâu thuẫn). Hàm thuần. | — |
| `missing_questions(trip)` | `server/app/agent.py` | Trả danh sách câu hỏi mục 3. Hàm thuần. | — |
| `apply_answers(trip, answers)` | `server/app/agent.py` | Áp answers vào Trip, validate bằng Pydantic. Hàm thuần. | — |
| `resolve_must_visit(conn, dest, names)` | `server/app/places.py` | Khớp tên không dấu (`unaccent` + `ILIKE`; thêm `CREATE EXTENSION IF NOT EXISTS unaccent` vào `schema.sql`); không thấy → embedding top-1 với ngưỡng khoảng cách. Trả `(ids, unmatched)`. | pgvector |
| `resolve_stay(conn, dest, name)` | `server/app/places.py` | Như trên với `kind=cho-o`; không thấy → `geocode`. | geocode |
| `geocode(name, center)` | `server/app/geocode.py` | Goong Geocoding; bỏ kết quả xa tâm Destination > 30 km; lỗi → `None`. | Goong, `GOONG_API_KEY` |
| `trip_brief` | `server/app/agent.py` | Thêm: giờ đến/về, điểm xuất phát ngày 1 (Hub theo Arrival Mode hoặc Booked Stay), "Stay đã đặt: X — không tìm cho-o", "Place bắt buộc: …". | — |
| `plan` | `server/app/agent.py` | Nạp sẵn Place bắt buộc (và Booked Stay nếu là Place) vào `seen` để AI được dùng. | — |
| `build_itinerary` | `server/app/rules.py` | Mục 6. | — |
| `/profile` | `server/app/profile.py` | `GET` (mặc định khi chưa có) / `PUT`. | auth |
| `/trips`, `/trips/{id}/plan` | `server/app/trips.py` | Mục 3. Tách "forecast + plan + lưu Itinerary" khỏi `_run` thành hàm dùng chung. | — |
| Client | `client/src/api.ts`, component chat, màn Hồ sơ | Kiểu event `clarify`; chip + ô nhập + "Bỏ qua"; gọi `/plan`; màn Hồ sơ đơn giản (onboarding cắt theo PRD §5.2). | — |

## 6. Quy tắc (code thực thi)

- **Giờ đến:** Stop ngày 1 bắt đầu trước `arrival_time + 60'` → Conflict `before_arrival`.
- **Giờ về:** Stop ngày cuối kết thúc sau `departure_time − 90'` → Conflict `after_departure`.
- **Điểm xuất phát ngày 1:** có Hub theo Arrival Mode → Leg đầu ngày 1 đi từ Hub; không có → từ Stay như hiện tại. Điểm kết thúc ngày cuối tương tự.
- **Place bắt buộc:** mỗi id trong `must_visit_place_ids` không xuất hiện ở Stop nào → Conflict `missing_must_visit`. Draft thiếu nó vẫn hợp lệ (không bắt AI làm lại) — nhất quán với "luôn trả Itinerary kèm Conflict".
- **Booked Stay:** Leg đầu/cuối mỗi ngày tính từ toạ độ Booked Stay; chi phí Stay = 0; Draft không cần `stay_place_id` (nếu AI vẫn gửi thì bỏ qua).
- **Xe riêng:** `xe-may-rieng` = xăng/km như `xe-may`, không tiền thuê. `o-to-rieng` = xăng ô tô/km (`CAR_FUEL_PER_KM = 3_500`) + `CAR_PARKING_PER_DAY = 50_000` × số ngày, không chia theo số người (một xe ≤ 7 người). Leg < 800 m vẫn đi bộ.
- **Unmatched Must-visit** không phải Conflict: báo trong event `trip` (`unmatched_must_visit`) để chat hiện "Chưa có dữ liệu X".

## 7. Lỗi

- Geocoding lỗi/không thấy → Booked Stay bỏ trống, chat báo "Không tìm thấy X, AI sẽ chọn chỗ ở"; không chặn lập lịch.
- `answers` sai định dạng giờ → 422 từ Pydantic, client hiện lỗi cạnh ô nhập.
- Giờ về ≤ giờ đến ở Trip 1 ngày → 422 "Giờ về phải sau giờ đến".
- Ràng buộc giờ làm ngày 1 hoặc ngày cuối không còn chỗ cho Stop → AI vẫn nộp ≥ 1 Stop (DraftDay yêu cầu), Conflict báo rõ.

## 8. Kiểm thử

- `rules`: `before_arrival`, `after_departure`, `missing_must_visit`; Booked Stay → chi phí Stay 0 và Leg đầu ngày từ toạ độ Booked Stay; `o-to-rieng` không tiền thuê, có phí gửi xe; Leg từ Hub khi có Arrival Mode.
- `merge_profile`, `missing_questions`, `apply_answers`: bảng ca kiểm (chat thắng Profile; có ngày đi mới hỏi giờ; skip → mặc định).
- `resolve_must_visit`/`resolve_stay`: khớp không dấu ("thung lung tinh yeu"), không khớp → unmatched; geocode giả lập.
- API (FakeClient): câu thiếu thông tin → `clarify`; `/plan` answers → `itinerary`; `/plan` lần 2 → 409; `/profile` GET/PUT, User khác không đọc được.
- E2E: curl `/trips` → `clarify` → `/plan` với câu ở mục 1 → kiểm tra tiêu chí thành công; chạy thử trong app desktop.

## 9. Thuật ngữ mới (thêm vào CONTEXT.md)

- **Origin** (Nơi xuất phát): thành phố người dùng đi từ đó tới Destination. Chỉ dùng để căn giờ, không tính tiền. _Avoid_: điểm đi, home.
- **Arrival / Departure** (Giờ đến / Giờ về): thời điểm tới Destination ngày 1 và rời Destination ngày cuối.
- **Arrival Mode** (Phương tiện đến): cách tới Destination — máy bay, xe khách, tàu, tự lái. Khác Travel Mode (di chuyển trong thành phố).
- **Hub** (Điểm đến nơi): sân bay/bến xe/ga của một Destination; điểm đầu ngày 1 và điểm cuối ngày cuối.
- **Booked Stay** (Chỗ ở đã đặt): Stay người dùng tự đặt trước; có thể không phải Place; chi phí 0.
- **Must-visit Place** (Điểm phải đến): Place người dùng nêu là lý do chuyến đi; thiếu trong Itinerary là Conflict.

## 10. Tài liệu cần cập nhật

- CONTEXT.md: mục 9.
- PRD: §5.2 (Profile thêm home_city, xe riêng), §5.3 (clarify, Must-visit), §5.5 (Booked Stay), §5.6 (xe riêng), §6 (quy tắc mới), §8 (API `POST /trips/{id}/plan`, event `clarify`).
- ADR-0006 mới: "Booked Stay có thể nằm ngoài Place" — nới ADR-0001 **chỉ cho Stay người dùng tự cung cấp**; AI vẫn không được tự nghĩ ra địa điểm.

## 11. Chia lát triển khai

Mỗi lát một implementation plan riêng, merge độc lập:

1. **Clarify + giờ đến/về + xe riêng** — 4.1 (trừ Booked Stay/Must-visit), 4.2 (Leg mode, Conflict giờ), Hub (4.3), `missing_questions`, `apply_answers`, `/plan`, client chip.
2. **Booked Stay + Must-visit** — `resolve_stay`, `geocode`, `resolve_must_visit`, quy tắc tương ứng, ADR-0006.
3. **Traveler Profile** — bảng, `/profile`, `merge_profile`, màn Hồ sơ.

Vùng code: Thành (agent/rules/domain/trips), Nhật (client), Quân (hubs, import), Tùng (profile/auth). Người phụ trách vùng review phần của mình.

## 12. Ngoài phạm vi

Tính tiền/thời gian di chuyển liên tỉnh; đặt vé/đặt phòng; học sở thích tự động từ lịch sử Trip; nhiều Stay trong một Trip; gợi ý Destination từ Origin.
