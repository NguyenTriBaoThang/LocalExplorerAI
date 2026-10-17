# Revision giữ mục đích — Design

> 2026-09-29 · Cập nhật 2026-09-30: §13 quyết định lát C · Trạng thái: chờ review · Liên quan: PRD §5.4, §5.7, §6, §12, §13; ADR-0001, ADR-0006.
> Thuật ngữ theo [CONTEXT.md](../../../CONTEXT.md); thuật ngữ mới ở mục 3.
> Nguồn ý tưởng: `thamkhao/PRD_Local_Explorer_AI.docx` (PRD 3.0) và `thamkhao/Local_Explorer_AI_Lo_Trinh_Trien_Khai_Chuc_Nang.docx`.

## 1. Vấn đề

Khi một phần Itinerary hỏng (quán đóng cửa, trời mưa, đến trễ, người dùng không thích một Stop), cách duy nhất hiện nay là chat để AI **lập lại toàn bộ** lịch trình. Cách này chậm (10–30 giây), có thể đổi cả những Stop đang ổn, và không cho biết lịch mới còn giữ được điều người dùng muốn hay không.

Local Explorer AI đặt đúng bài toán này làm lõi: *bảo toàn mục đích trải nghiệm trong một lịch trình khả thi*. Tài liệu này mang ý tưởng đó vào Travility, giữ nguyên bối cảnh đồ án: desktop, Đà Lạt, demo cho giảng viên.

**Thành công khi:**
- Với Itinerary Đà Lạt 2 ngày có quán cafe chill ở ngày 1, bấm "Báo đóng cửa" trên quán đó → trong < 2 giây có tối đa 3 phương án.
- Mỗi phương án thay bằng Place khác có Intent `thu-gian`, mở cửa đúng giờ đó, không sinh Conflict cứng mới, và không đụng Stop nào khác.
- Mỗi phương án có bảng so sánh (tiền, giờ kết thúc ngày, phút di chuyển, Intent giữ/mất) và một câu giải thích lấy từ các số đó.
- Bấm "Áp dụng" → xuất hiện version mới.
- Bảng đánh giá cho thấy B2 (engine) giữ Intent tốt hơn B0/B1 trên bộ kịch bản cố định. Nếu kết quả không như vậy, báo đúng kết quả.

## 2. Quyết định

| # | Chủ đề | Quyết định |
|---|---|---|
| D1 | Phạm vi | Làm sâu đồ án, không đổi sang cuộc thi. Không lấy tầng Experience/Slot/sức chứa, Provider Portal, đặt chỗ, dự báo ngập. |
| D2 | Mục đích | Khái niệm **Intent** mới, ánh xạ từ Tag bằng bảng cố định trong code. Không sửa JSON Place. |
| D3 | Trọng số | Code suy ra từ Preference: Intent có Tag bắt buộc → 2, chỉ có Tag ưu tiên → 1. Không có UI chỉnh trọng số. |
| D4 | Engine | **Code thuần, không gọi LLM** (ADR-0006). LLM không chọn phương án thay thế và không tạo câu giải thích. |
| D5 | Sự cố | 4 loại do người dùng báo: `closed`, `disliked`, `rain`, `late`. Thêm `insert` cho bản đồ theo thời điểm. |
| D6 | Áp dụng | Proposal chưa phải version. Người dùng chủ động bấm "Áp dụng" mới tạo version mới. Không bao giờ tự đổi lịch. |
| D7 | Pinned Stop | `rain`/`late` không đụng Pinned Stop. `closed`/`disliked` trên Pinned Stop bị khoá; muốn đổi thì bỏ ghim trước. |
| D8 | ML | Hàm điểm tay là baseline. XGBRanker chỉ được bật khi thắng baseline trên tập test chia theo tình huống. |
| D9 | Chat | Tới lát F, sự cố chỉ báo bằng nút trên UI. Lát F thêm tool để LLM nhận diện câu kiểu "ngày 2 mưa thì sao" và chuyển sang engine. |
| D10 | Lộ trình | Cắt Inspiration Photo và Destination thứ 3 để có người làm lát D và E. |

## 3. Thuật ngữ mới (thêm vào CONTEXT.md)

- **Intent** (Mục đích): lý do lớn khiến người dùng chọn chuyến đi, gom nhiều Tag lại. Có 5 Intent:

  | Intent | Tag |
  |---|---|
  | `am-thuc` | an-dia-phuong, hai-san, an-chay |
  | `thien-nhien` | thien-nhien, view-dep |
  | `van-hoa` | lich-su, van-hoa |
  | `thu-gian` | cafe-chill, yen-tinh, lang-man |
  | `vui-choi` | soi-dong, dem, mua-sam, check-in |

  `gia-dinh`, `gia-re`, `sang-trong` là ràng buộc, không phải Intent. Intent của một Place = tập Intent của các Tag nó mang.
- **Intent Retention** (Mức giữ mục đích, R): R = Σ wₖ·zₖ / Σ wₖ. wₖ là trọng số Intent k của Trip (D3). zₖ = 1 nếu Itinerary có ít nhất một Stop mà Place thuộc Intent k. Trip không có Intent nào (Σw = 0) thì R không xác định và không hiện. Đây là chỉ số sản phẩm, không phải xác suất hài lòng.
- **Disruption** (Sự cố): một thay đổi làm Itinerary hiện tại không còn phù hợp. Có 4 loại: Place đóng cửa, người dùng không thích một Stop, mưa một ngày, trễ N phút từ một Stop.
- **Proposal** (Phương án): một Itinerary ứng viên do engine tạo từ một Disruption, kèm số liệu so sánh và lý do. Chưa phải version. Chỉ trở thành version khi người dùng áp dụng.

_Avoid_: alternative, option (trong code dùng `options` cho danh sách Proposal là chấp nhận được), candidate khi nói với người dùng.

## 4. Engine thay thế — `server/app/replan.py`

Là hàm thuần, trừ bước 2 cần một truy vấn DB (truyền vào dạng callback để test không cần DB).

```python
class Disruption(BaseModel):
    kind: Literal["closed", "disliked", "rain", "late", "insert"]
    day_index: int
    stop_index: int | None = None   # closed/disliked/late
    minutes: int | None = None      # late: 5–240
    place_id: int | None = None     # insert
    time: str | None = None         # insert, HH:MM

class ProposalOption(BaseModel):
    itinerary: Itinerary
    changed: list[tuple[int, int]]  # (day_index, stop_index) đã đổi/thêm/bỏ
    metrics: dict                   # xem 4.6
    reason_codes: list[str]
    explanation: str

def propose(trip, itin, places, disruption, candidates_fn, rain, hub, score_fn=score) \
        -> list[ProposalOption] | NoFeasible
```

### 4.1 Stop bị ảnh hưởng
- `closed`, `disliked`: Stop `(day_index, stop_index)`. Stop đó là Pinned → 422.
- `rain`: mọi Stop `outdoor` không ghim của ngày `day_index`. Không có Stop nào → `NoFeasible(["NOTHING_OUTDOOR"])`.
- `late`: cộng `minutes` vào `start_time` của Stop `stop_index` và các Stop sau nó trong cùng ngày. Stop nào sau khi dời bị `closed`, vượt giờ cuối Pace, hoặc (ngày cuối) vi phạm `after_departure` thì bị ảnh hưởng. Pinned Stop bị dời giờ nhưng không bị thay. Nếu chính nó hết hợp lệ thì phương án ghi lý do `PINNED_CONFLICT`, không bị loại.
- `insert`: không có Stop bị ảnh hưởng. Chèn một Stop mới `(place_id, time, duration mặc định 60′)`. Kết quả chỉ có 1 phương án.

### 4.2 Ứng viên
Thêm vào `places.py`:
```python
def similar_places(conn, place_id, kind, exclude_ids, exclude_tags, limit=20) -> list[Place]
    # ORDER BY embedding <=> (SELECT embedding FROM places WHERE id = place_id)
```
Dùng embedding đã lưu nên không gọi API embedding: nhanh và chạy được khi mất mạng. `kind` giữ nguyên kind của Stop bị mất. `exclude_ids` gồm mọi Place đã có trong Itinerary và Stay. `exclude_tags` là `trip.avoided_tags`.

### 4.3 Lọc ràng buộc cứng (tái dùng `rules.py`)
- `is_open(place, weekday, start_time, duration)`. Không có ngày đi thì dùng quy tắc "mở ở ít nhất một thứ" giống `find_conflicts`.
- `rain`: chỉ giữ `outdoor = False`.
- Kịp giờ: `make_leg(prev, cand).duration_min` ≤ khoảng trống từ lúc Stop trước kết thúc tới `start_time`. Phải đi kịp tới Stop sau theo cùng cách tính.

### 4.4 Chấm điểm
```python
def features(trip, lost: Place, cand: Place, prev, nxt) -> dict:
    # intent_overlap (có trọng số Trip), tag_jaccard, extra_travel_min, extra_cost_vnd,
    # price_ratio, outdoor, distance_km_from_lost
def score(f: dict) -> float:
    return 3 * f["intent_overlap"] + f["tag_jaccard"] - f["extra_travel_min"] / 30 - f["extra_cost_vnd"] / 200_000
```
Chữ ký `score(features) -> float` giữ cố định để ranker ML (mục 7) thay thế được. Các hệ số là ước lượng ban đầu, sẽ được chỉnh trong lát E1.

### 4.5 Dựng Proposal
1. Dựng lại `Draft` từ Itinerary hiện tại: mỗi Stop giữ `place_id`, `start_time`, `duration_min`, `reason`, `pinned`.
2. Phương án k (k = 0..2) thay mỗi Stop bị ảnh hưởng bằng ứng viên tốt thứ k của nó, không trùng Place giữa các Stop. Đổi `reason` thành câu sinh từ code (vd "Thay {tên cũ} (đóng cửa) — cùng mục đích Thư giãn").
3. Gọi `build_itinerary(trip, draft, places, rain, hub)` để tiền, Leg và Conflict dùng đúng code hiện có.
4. Loại phương án có Conflict **cứng** mới so với bản cũ. Conflict cứng gồm `closed`, `before_arrival`, `after_departure`, `rain_outdoor` (với sự cố mưa), và `over_budget` nếu bản cũ chưa vượt.
5. `late` có thêm phương án "Bỏ Stop" cho mỗi Stop bị ảnh hưởng.
6. Không còn phương án nào → `NoFeasible(reason_codes)`, ví dụ `NO_OPEN_CANDIDATE`, `NO_INDOOR_CANDIDATE`, `NOT_REACHABLE_IN_TIME`, `OVER_BUDGET`.

### 4.6 So sánh + giải thích (code, không LLM)
`metrics` của mỗi phương án (so với bản cũ):
- `cost_delta`: tiền tăng/giảm
- `day_end_before`, `day_end_after`: giờ kết thúc ngày bị ảnh hưởng
- `travel_min_delta`: phút di chuyển tăng/giảm
- `retention_before`, `retention_after`: R trước và sau
- `intents_kept`, `intents_lost`: Intent còn giữ và bị mất

`reason_codes`: `INTENT_MATCH`, `INTENT_PARTIAL`, `INDOOR_FOR_RAIN`, `CLOSED_AT_TIME`, `LATE_SHIFT`, `STOP_DROPPED`, `FARTHER`, `CLOSER`, `CHEAPER`, `PRICIER`, `PINNED_CONFLICT`.

`explanation` ghép từ template tiếng Việt với các trường trên. Ví dụ: "Giữ mục đích Thư giãn; thêm 12 phút di chuyển, rẻ hơn 30.000đ; ngày 1 vẫn kết thúc 20:30." Không dùng tỉ lệ phần trăm "phù hợp".

## 5. Dữ liệu & API

### 5.1 Schema (`server/app/schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS proposals (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  base_version integer NOT NULL,
  disruption jsonb NOT NULL,
  options jsonb NOT NULL,          -- [] khi no_feasible; lưu cả reason_codes
  chosen_index integer,
  applied_version integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
```
Bảng này kiêm **log feedback**: phương án nào đã hiện, người dùng chọn cái nào hay bỏ qua (`chosen_index` null).

### 5.2 Endpoint (trong `trips.py`, kiểm quyền sở hữu Trip như hiện có: Trip của User khác → 404)
| Endpoint | Vào | Ra |
|---|---|---|
| `POST /trips/{id}/disruptions` | `{version, ...Disruption}` | `{proposal_id, options: ProposalOption[] }` hoặc `{proposal_id, no_feasible: reason_codes}`. JSON thường, không SSE. `version` không phải bản mới nhất → 409. |
| `POST /trips/{id}/proposals/{pid}/apply` | `{option: int}` | Payload như event `itinerary` (itinerary, places, trip_id, version). `base_version` lệch bản mới nhất → 409. Đã apply rồi → trả lại version đã tạo (idempotent). |
| `GET /trips/{id}/reachable` | `?version&day&time=HH:MM` | `[{place_id, status}]`, với `status ∈ open_reachable / open_far / closed`. "Đến kịp" = mở tại `time`, đi từ Stop liền trước `time` (hoặc Stay/Hub) ≤ 20 phút, và còn mở ít nhất 45 phút sau khi tới. |

Không thêm event SSE mới.

## 6. Client

- **Thẻ Stop:** menu có **Báo đóng cửa** · **Đổi chỗ khác** · **Tôi trễ** (chip 15/30/60′). Hai mục đầu bị khoá khi Stop đã ghim, kèm tooltip "Bỏ ghim để đổi".
- **Header ngày:** nút **Giả sử mưa**.
- **ProposalPanel** (`client/src/ProposalPanel.tsx`): tối đa 3 thẻ, mỗi thẻ có Stop mới (ảnh, tên), bảng chênh lệch và câu giải thích. Map vẽ Place thay thế bằng màu riêng. **Áp dụng** gọi apply rồi xử lý như event `itinerary`, nên version mới vào dãy v1·v2·v3. **Huỷ** đóng panel. `no_feasible` hiện lý do bằng tiếng Việt.
- **TimeSlider** (`client/src/TimeSlider.tsx`): chọn ngày + thanh giờ theo bước 15′ → gọi `/reachable` (debounce) → pin đổi màu: xanh = mở và đến kịp, vàng = mở nhưng xa, xám = đóng. Bấm pin xanh → "Thêm vào lúc HH:MM" → Disruption `insert` → ProposalPanel.
- **Timeline header:** chip Intent (✓/✗) và R.
- Kiểu mới đặt trong `client/src/api.ts`.

## 7. Đánh giá & ML — `server/eval/`

Chạy ngoài app. Không import vào `app` khi chạy server.

### 7.1 Kịch bản cố định (lát E1)
- Lưu 10 Itinerary Đà Lạt từ planner làm fixture (`eval/fixtures/*.json`). Sinh ~40 Disruption bằng seed cố định, chia đều 4 loại → `eval/scenarios.json`.
- **B0:** Place cùng kind gần nhất (haversine). **B1:** gần nhất nhưng qua bộ lọc cứng 4.3. **B2:** engine đầy đủ.
- Chỉ số:
  - tỉ lệ khả thi (không có Conflict cứng mới)
  - R trung bình sau sự cố
  - tỉ lệ giữ Intent của Stop bị mất
  - Δ tiền, Δ phút đi
  - thời gian xử lý
- `uv run python -m eval.run` in bảng markdown. Kết quả chỉ chứng minh hành vi phần mềm trên dữ liệu mô phỏng, không phải hiệu quả ngoài thực tế.

### 7.2 Ranker (lát E2)
- ~150 tình huống × 8 ứng viên lấy từ bước 4.2–4.3. Xuất CSV có `features` và cột `grade` trống.
- Rubric 0–3: 3 = cùng Intent chính, trải nghiệm tương đương · 2 = cùng Intent, khác kiểu · 1 = chỉ liên quan một phần · 0 = sai mục đích (vd "mua gốm" thay "làm gốm").
- 2 người chấm độc lập 20% chung để đo Cohen's kappa và thống nhất rubric.
- Train `xgboost.XGBRanker` (dependency group `ml`, không cài cho server mặc định). Dùng GroupKFold theo tình huống để chống leakage. Fit mọi bước tiền xử lý chỉ trên fold train.
- Báo NDCG@5 (chính), MRR, Top-1, kèm bootstrap CI theo tình huống. Đối chứng là `score` tay.
- Lưu `model.json` + `feature_schema_version`. Engine chỉ nạp model khi có `RANKER_PATH` **và** báo cáo cho thấy model thắng. Không thắng thì giữ `score` tay và ghi rõ trong báo cáo.
- **Feedback:** `eval/export_feedback.py` xuất bảng `proposals` ra CSV (đã hiện gì, chọn gì) làm nhãn bổ sung. Đồ án không có người dùng thật, nên đây chủ yếu là hạ tầng.

## 8. Chia lát & phân vai

| Lát | Nội dung | Người | Tuần | Phụ thuộc |
|---|---|---|---|---|
| A | Intent + R (`domain.py`, `rules.intent_retention`) + chip Timeline | Thành + Nhật | T4 | — |
| B | Engine `closed`/`disliked` + `proposals` + 2 endpoint + ProposalPanel | Thành (server) + Nhật (UI) | T4–T5 | A, version #24 |
| C | `rain` + `late` | Thành | T5–T6 | B |
| D | `/reachable` + TimeSlider + `insert` | Tùng | T6 | B |
| E1 | Kịch bản + B0/B1/B2 + báo cáo | Quân | T5–T6 | B |
| E2 | Rubric, gán nhãn, XGBRanker, export feedback | Quân + 1 người chấm chéo | T7–T8 | E1 |
| F | Chat → Disruption (LLM tool `report_disruption`) | Thành | T9 | B, C |

Revision bằng chat (#22), Pinned Stop (#25) và version (#24) vẫn làm ở T2–3 theo PRD, vì là nền cho lát B.

## 9. Lỗi & biên

- Trip/proposal của User khác → 404. `version` hoặc `base_version` cũ → 409. Disruption sai (stop_index ngoài phạm vi, Stop đã ghim với `closed`/`disliked`, `minutes` ngoài 5–240) → 422.
- Không có phương án → trả `no_feasible`, không phải lỗi HTTP. UI hiện lý do.
- Place bị thiếu embedding không xảy ra (cột `NOT NULL`).
- Đồng thời: hai lần apply khác nhau trên cùng `base_version` → lần sau nhận 409 nhờ `UNIQUE (trip_id, version)` và kiểm tra bản mới nhất trong cùng transaction.

## 10. Kiểm thử

- `server/tests/test_replan.py` (hàm thuần, fixture Place, không cần DB):
  - `closed` → mọi phương án có Intent trùng Stop bị mất, không trùng Place, không có Conflict cứng mới, Stop khác giữ nguyên
  - `rain` → chỉ Place trong nhà
  - `late` → dời giờ đúng; Stop quá giờ bị thay hoặc bỏ
  - Pinned Stop không đổi; `no_feasible` có reason codes
  - `explanation` không chứa "%"
- `server/tests/test_disruptions_api.py` (Postgres Docker):
  - 404 với User khác; 409 với version cũ; apply 2 lần → 1 version
  - `chosen_index` được lưu
- `test_rules.py`: `intent_retention` trong các trường hợp Σw = 0, đủ và thiếu Intent.
- Client (vitest): format bảng so sánh và câu reason code tiếng Việt.
- `uv run python -m eval.run` chạy hết và in bảng.
- E2E desktop theo kịch bản demo mục 11.

## 11. Kịch bản demo bổ sung (chèn sau bước 6 của PRD §3.2)

1. Itinerary Đà Lạt 2 ngày đang mở. Timeline hiện chip Thư giãn ✓ Thiên nhiên ✓ Ẩm thực ✓, R = 100%.
2. Bấm "Báo đóng cửa" trên quán cafe ngày 1 → ProposalPanel hiện 3 phương án trong < 2 s, map tô màu Place thay thế.
3. So phương án 1 (cafe khác, +8′, R giữ 100%) với phương án 3 (gần hơn nhưng mất Thư giãn) → đọc câu giải thích.
4. Áp dụng phương án 1 → v3 xuất hiện, Stop đổi được tô sáng.
5. Kéo TimeSlider ngày 2 tới 15:00 → pin đổi màu → bấm một pin xanh → "Thêm vào lúc 15:00".
6. Mở báo cáo đánh giá B0/B1/B2 (và ranker nếu thắng) trong slide.

## 12. Ngoài phạm vi

Tầng Experience/Slot/sức chứa, Provider Portal, đặt chỗ/giữ chỗ, sự kiện từ bên ngoài (outbox/worker), OR-Tools tối ưu lại cả ngày, LLM viết câu giải thích, UI chỉnh trọng số Intent, nhãn dữ liệu thật/mô phỏng trên từng Place.

## 13. Lát C — quyết định (chốt 2026-09-30)

Phần này bổ sung và **thay thế** §4.1, §4.5 và §6 ở những điểm liên quan tới `rain` và `late`.

| # | Chủ đề | Quyết định |
|---|---|---|
| C1 | Mưa | Stop bị ảnh hưởng là mọi Stop `outdoor` chưa ghim của ngày `day_index`. Ứng viên chỉ lấy Place có `outdoor = False`. Không ghi `rain_chance`: forecast thật giữ nguyên, version mới chỉ khác ở các Stop được thay. `reason` của Stop mới là "Thay {tên cũ} (mưa)". Stop ngoài trời đã ghim giữ nguyên, phương án gắn thêm mã `PINNED_CONFLICT`. Ngày không có Stop nào bị ảnh hưởng → `NoFeasible(["NOTHING_OUTDOOR"])`. |
| C2 | Nhiều Stop | Phương án k (k = 0..2) lấy ứng viên tốt thứ k của từng Stop bị ảnh hưởng, không trùng Place giữa các Stop. Stop không còn ứng viên hợp lệ thì **bị bỏ** khỏi phương án (không loại cả phương án), gắn mã `STOP_DROPPED`, câu giải thích ghi "bỏ {tên} (không có chỗ thay phù hợp)". Phương án không thay được Stop nào (chỉ có bỏ) chỉ giữ lại một bản. |
| C3 | Trễ | `minutes` ∈ 5–240. Cộng `minutes` vào `start_time` của Stop `stop_index` và mọi Stop sau nó trong ngày; Stop đã ghim cũng bị dời. Sau khi dời, Stop **hỏng** là Stop thuộc một trong hai trường hợp: (a) **đóng cửa** ở giờ mới → thay bằng ứng viên cùng kind đang mở vào giờ mới; (b) **quá giờ**: kết thúc sau `PACE_HOURS[pace][1]`, hoặc sau `last_day_limit(trip)` nếu là ngày cuối → bỏ ở mọi phương án, vì thay Place khác không làm lịch kết thúc sớm hơn. Không có Stop hỏng → đúng 1 phương án "Chỉ dời giờ" (`LATE_SHIFT`). Có Stop hỏng → tối đa 2 phương án thay (`LATE_SHIFT` + mã của thay thế) và 1 phương án "Bỏ các Stop hỏng" (`LATE_SHIFT`, `STOP_DROPPED`). Stop đã ghim bị hỏng thì không thay cũng không bỏ, gắn mã `PINNED_CONFLICT`. |
| C4 | UI | Stop đang chọn trên Timeline có thêm hàng **Tôi trễ 15′ · 30′ · 60′**, kể cả khi Stop đã ghim. Header ngày có nút **☂ Giả sử mưa**, chỉ hiện khi ngày có Stop ngoài trời chưa ghim. Kết quả hiện trong ProposalPanel hiện có, tối đa 3 thẻ. |
| C5 | Engine | Tổng quát hoá `propose` thành ba bước: (1) `_affected` trả về Draft gốc (với `late` là Draft đã dời giờ) và danh sách Stop hỏng `(day, stop, lost, mode)`, trong đó `mode ∈ replace/drop/keep`; (2) xếp hạng ứng viên riêng cho từng Stop `replace` bằng `_reject` + `score`; (3) dựng phương án k rồi gọi `build_itinerary`, loại phương án có Conflict cứng mới như §4.5. `closed`/`disliked` là trường hợp chỉ có một Stop `replace`. Mọi test của lát B phải giữ nguyên và xanh. |
| C6 | API | `Disruption.kind` thêm `rain`, `late`. `stop_index` bắt buộc với `closed`/`disliked`/`late` và phải bỏ trống với `rain`. `minutes` bắt buộc với `late`. Sai → 422. Không thêm endpoint mới. |
