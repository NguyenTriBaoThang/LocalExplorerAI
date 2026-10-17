# Travility — PRD (Product Requirements Document)

> Phiên bản 1 · khởi tạo 2026-09-25 · cập nhật phạm vi chia sẻ 2026-10-14 · Người đọc: toàn bộ thành viên nhóm.
> PRD là nguồn chính trả lời **làm gì và vì sao**. Chi tiết kỹ thuật từng giai đoạn nằm trong [docs/superpowers/plans/](superpowers/plans/).
> Thuật ngữ in đậm theo [CONTEXT.md](../CONTEXT.md). Quyết định kiến trúc ở [docs/adr/](adr/). Hiện trạng code chi tiết: [2026-09-25-hien-trang-app.md](2026-09-25-hien-trang-app.md).

Ký hiệu trạng thái: ✅ đã có trong code · 🟡 có một phần · ⏳ chưa làm · ❌ ngoài phạm vi hoặc đã cắt.

---

## 1. Tổng quan & vấn đề

Người Việt đi du lịch trong nước thường mất hàng giờ ghép thông tin từ nhiều nguồn: chọn điểm tham quan, quán ăn, chỗ ở, tính đường đi và tổng chi phí sao cho vừa ngân sách. Kết quả thường là một lịch trình đi vòng, vượt ngân sách, hoặc ghé nơi đang đóng cửa.

**Travility** hiện là app desktop: người dùng mô tả chuyến đi bằng một câu ("Đi Đà Lạt 3 ngày, 3 triệu, thích cafe chill"), AI dựng **Itinerary** theo ngày trên bản đồ 3D, dùng **Place** thật đã được kiểm chứng. Chi phí và các **Conflict** (vượt Budget, đóng cửa, mưa…) do code tính chính xác. Sau đó người dùng chỉnh lịch trình bằng hội thoại (**Revision**). Ở giai đoạn 1, **Organizer** có thể xuất PDF của version đang xem và nhập **GroupReview** trong Trip Chat để AI tạo bản xem trước; chỉ Organizer quyết định áp dụng. Giai đoạn 2 dự kiến mở rộng sang app mobile native để **Guest** xem lịch được chia sẻ và gửi góp ý trực tiếp. Không làm web app.

Bối cảnh: đồ án nhóm 4 người, 10 tuần, demo trực tiếp 10–15 phút trên một laptop trước giảng viên.

## 2. Mục tiêu & chỉ số thành công

**Mục tiêu chính:** kịch bản demo (mục 3.2) chạy trơn tru từ đầu đến cuối trên laptop demo, kể cả khi mất mạng.

| Chỉ số | Mục tiêu | Cách đo |
|---|---|---|
| Itinerary hợp lệ (không Place lạ, đúng số ngày, có Stay) | ≥ 90% | Golden set 15 prompt × 2 provider (Gemini dev, OpenAI demo) |
| Thời gian từ gửi yêu cầu đến có Itinerary | < 30 giây (OpenAI) | Đo trong golden set |
| Sự kiện đầu tiên hiện trên UI | < 2 giây | Event `thinking` ngay khi gửi |
| Revision chỉ đổi Stop liên quan, không đụng Pinned Stop | 100% | pytest + golden set Revision |
| Dữ liệu Place | Đà Lạt ≥ 150 (T4); Destination thứ 2 ≥ 150 (T8) | Đếm trong `data/places/` |
| Demo offline | Chạy hết kịch bản khi tắt mạng | Diễn tập với demo_cache |

**Không phải mục tiêu:** phát hành cho người dùng thật, chạy nhiều máy, doanh thu.

## 3. Người dùng & kịch bản

### 3.1 Người dùng
- **Organizer** của nhóm nhỏ (1–10 người): sinh viên, nhân viên văn phòng, gia đình. Họ biết mình thích gì ("cafe chill", "ăn chay", "thiên nhiên") và có ngân sách, nhưng không muốn tự ghép lịch. Organizer sở hữu Trip và giữ quyền chọn, áp dụng version.
- **Thành viên trong nhóm:** nhận PDF do Organizer gửi và phản hồi qua kênh họ đang dùng. Trong giai đoạn 1, Organizer nhập hoặc tóm tắt các ý kiến đó trong Trip Chat. Giai đoạn 2 dự kiến cho phép Guest gửi góp ý trực tiếp qua app mobile native.
- **Người xem demo (giảng viên):** cần thấy rõ AI "đang làm gì", kết quả đáng tin (Place thật, tiền tính đúng) và có khoảnh khắc "wow".

### 3.2 Kịch bản demo (10–15 phút)
1. Mở app → đăng nhập (hoặc đăng ký → onboarding chọn sở thích).
2. Gõ hoặc nói: "Đi Đà Lạt 3 ngày, 2 người, 3 triệu, thích cafe chill và thiên nhiên".
3. Map bay tới Đà Lạt. Pin vàng nhấp nháy xuất hiện dần theo từng lần AI tìm Place (**khoảnh khắc wow chính**).
4. Itinerary hiện ra: tuyến đường tô màu theo ngày, Timeline có giờ, giá, lý do chọn, tổng chi phí so với Budget, Conflict (nếu có).
5. Bấm "Xem hành trình": camera bay qua từng Stop.
6. Ghim một quán cafe → nói "Ngày 2 mưa thì sao?" → chỉ các Stop ngoài trời đổi; Stop đã ghim giữ nguyên; map animate chỗ đổi; version v2 xuất hiện.
7. "Bớt 500k" → v3 rẻ hơn. Bấm v1 để xem lại, "Quay lại bản này".
8. "Đổi sang homestay" → Stay đổi, chi phí tính lại.
9. Báo đóng cửa một quán → 3 Proposal giữ Intent + bảng so sánh → áp dụng; kéo thanh giờ để thêm Place (§5.11).
10. Organizer xuất PDF của version đang xem và gửi cho nhóm qua kênh bên ngoài Travility.
11. Thành viên góp ý ngoài app; Organizer chọn **Góp ý nhóm** trong Trip Chat, chọn version được nhắc tới, nhập phản hồi → AI tạo preview → Organizer áp dụng hoặc huỷ (§5.12).
12. Cinematic recap có thuyết minh.
13. Tắt wifi, chạy lại bước 2 → vẫn chạy nhờ demo_cache.

## 4. Thuật ngữ

Dùng đúng thuật ngữ trong [CONTEXT.md](../CONTEXT.md): User, Traveler Profile, Destination, Trip, Itinerary, Conflict, Revision, Pinned Stop, Place, Stop, Suggestion, Inspiration Photo, Stay, Leg, Travel Mode, Pace, Forecast, Tag, Preference, Organizer, GroupReview, Guest. Tránh các từ trong mục _Avoid_ của file đó, cả trong code lẫn UI.

## 5. Yêu cầu chức năng

### 5.1 Tài khoản
| Yêu cầu | Trạng thái |
|---|---|
| Đăng ký / đăng nhập email + mật khẩu (bcrypt, JWT 7 ngày) | ✅ |
| Trip thuộc đúng một User và mặc định chỉ User đó thấy | ✅ |
| Đăng xuất | ✅ |
| Đăng nhập Google (loopback redirect cho app desktop) | ⏳ (cắt đầu tiên nếu trễ) |
| Quên mật khẩu qua email | ⏳ (cắt đầu tiên nếu trễ) |

Tiêu chí chấp nhận: token hết hạn → về màn đăng nhập kèm thông báo; User A gọi `GET /trips/{id}` của User B → 404. Chỉ luồng chia sẻ rõ ràng của giai đoạn 2 cấp Guest quyền giới hạn xem Itinerary được chia sẻ; quyền đó không mở Trip Chat, Traveler Profile hay Trip khác.

### 5.2 Traveler Profile ⏳
- Sau khi đăng ký: **onboarding 1 màn**, bỏ qua được. Chọn Tag sở thích bằng chip có icon (bắt buộc / ưu tiên / tránh), Pace, Travel Mode.
- Sửa trong màn **Hồ sơ**.
- Khi tạo Trip, Profile được chép vào Trip. **Câu chat luôn thắng Profile** khi mâu thuẫn. Đổi Profile không ảnh hưởng Trip đã có.
- Cần bảng `traveler_profiles`.
- Nếu trễ: cắt onboarding, giữ màn Hồ sơ.

### 5.3 Lập Trip & Itinerary (lõi)
| Yêu cầu | Trạng thái |
|---|---|
| Hiểu câu tự nhiên → Trip (Destination, số ngày, ngày đi, số người, Budget, Tag, Pace, Travel Mode) | ✅ |
| Destination chưa hỗ trợ → báo rõ danh sách đang có | ✅ |
| AI tìm Place bằng pgvector (đúng Destination, đủ Tag bắt buộc, loại Tag cần tránh) | ✅ |
| AI chỉ được dùng Place đã trả về từ tool; Place lạ → làm lại 1 lần (ADR-0001) | ✅ |
| Stream tiến trình qua SSE (`thinking`, `trip`, `tool_call`, `clarify`, `itinerary`, `error`) | ✅ |
| Thiếu phương tiện / giờ đến–về → hỏi lại một vòng bằng chip (event `clarify`, `POST /trips/{id}/plan`) | ✅ |
| Luôn trả Itinerary kèm Conflict thay vì báo lỗi | ✅ |
| Mỗi Stop có lý do chọn (reason) | ✅ |
| Lưu Trip + Itinerary; mở lại Trip cũ | ✅ |
| Trả lời bằng giọng nói / nhập bằng giọng nói | ⏳ (mục 5.8) |

Tiêu chí chấp nhận: 15 prompt golden set cho ≥ 90% Itinerary hợp lệ; không bao giờ xuất hiện Place không có trong database.

### 5.4 Revision, Pinned Stop, phiên bản ✅ (không được cắt)
- **Chat gắn với Trip đang mở.** Khi đã có Itinerary, tin nhắn theo luồng chat thông thường là câu hỏi hoặc Revision của Trip đó. **Góp ý nhóm** là hành động riêng, được Organizer bật rõ ràng để tạo bản xem trước; không trộn với Revision thường (§5.12). Muốn chuyến khác thì bấm nút **"Chuyến mới"**. App không tự đoán ý người dùng.
  🟡 Đã có (2026-09-29): khi Trip đã có lịch, AI tự phân loại tin nhắn — **câu hỏi** được trả lời bằng số liệu code tính (không tạo version); **yêu cầu sửa** thành thao tác trên lịch cũ (Stop không nhắc tới giữ nguyên, Stop đổi có viền); **đổi thông tin gốc** (số ngày, Budget…) hỏi xác nhận rồi lập lại, giữ Place cũ làm gợi ý. ✅ 2026-09-30: ghim (lưu trên Trip, `PATCH /trips/{id}/pins`), dãy version + "Quay lại bản này" (`POST /trips/{id}/restore/{version}`), lịch sử chat (`GET /trips/{id}/messages`). Còn thiếu: animate Stop đổi trên map (làm cùng UI mới).
- Mỗi Trip có lịch sử chat riêng, được lưu lại (mở Trip cũ thấy lại hội thoại).
- Mỗi Revision tạo **một version Itinerary mới, bất biến**. Chỉ Stop liên quan đến yêu cầu được đổi.
- **Pinned Stop:** ghim / bỏ ghim từ popup Place hoặc icon trên Timeline. Ghim **không tạo version mới**; đây là trạng thái áp cho Revision kế tiếp. Code kiểm tra Draft và **từ chối Draft đổi hoặc xoá Stop đã ghim** (AI làm lại 1 lần, giống cơ chế Place lạ).
- **Version:** Timeline có dãy `v1 · v2 · v3`. Bấm version cũ để xem. "Quay lại bản này" tạo version mới chép từ bản cũ, không xoá gì.
- Sau Revision: Stop thay đổi được tô sáng trên Timeline và animate trên map (client so sánh hai version).

Tiêu chí chấp nhận: pytest chứng minh Draft đụng Pinned Stop bị từ chối; Revision "bớt 500k" cho version mới có `total_cost` thấp hơn; undo không làm mất version nào.

### 5.5 Chỗ ở (Stay)
| Yêu cầu | Trạng thái |
|---|---|
| Một Stay cho cả Trip (bắt buộc khi Trip > 1 ngày), là điểm đầu/cuối mỗi ngày | ✅ |
| Tính theo đêm × số phòng (2 người/phòng) | ✅ |
| Phân loại chỗ ở bằng Tag: `khach-san`, `homestay`, `hostel`, `resort` | ⏳ thêm vào bộ Tag và dữ liệu |
| Đổi Stay bằng Revision ("đổi sang homestay rẻ hơn") | ⏳ đi cùng 5.4 |

### 5.6 Đường đi & chi phí
| Yêu cầu | Trạng thái |
|---|---|
| Leg giữa các điểm liên tiếp; Leg < ~800 m thì đi bộ | ✅ |
| Chi phí: xe máy thuê theo ngày × số xe + xăng/km; Grab theo công thức cố định | ✅ |
| Budget = ăn + vé + Stay + Leg (không gồm di chuyển liên tỉnh, ADR-0005) | ✅ |
| Km thật từ **Goong Distance Matrix ở server**; lỗi thì dùng chim bay × 1.3 | ✅ (#7) |
| Xe máy riêng / ô tô riêng: không tiền thuê; ô tô 3.500đ/km + gửi xe 50.000đ/ngày | ✅ |
| Conflict mới **"không kịp di chuyển"**: thời gian Leg dài hơn khoảng trống giữa hai Stop (du di 5′) | ✅ (#7) |
| Tối ưu thứ tự Stop bằng thuật toán | ❌ ngoài phạm vi (phá khung giờ AI đã xếp) |

Tiêu chí chấp nhận: km trên Timeline khớp với tuyến Goong vẽ trên map (sai số < 10%).

### 5.7 Forecast ✅
- Trip có ngày đi trong 16 ngày tới → lấy khả năng mưa theo ngày từ Open-Meteo. Lỗi thì lập lịch không có thời tiết.
- Ngày mưa ≥ 60% + Stop ngoài trời → Conflict `rain_outdoor`.

### 5.8 Giọng nói ⏳
- Nút mic → STT (OpenAI) → gửi như tin nhắn chat.
- Câu tóm tắt của AI được đọc bằng TTS (OpenAI); có nút tắt tiếng.

### 5.9 Inspiration Photo ❌ (đã cắt 2026-09-29, nhường chỗ §5.11)
- Kéo thả ảnh → vision mô tả không khí → embedding → 3–5 **Suggestion** hiện trên map với màu riêng.
- Chấp nhận một Suggestion = một Revision ("thêm nơi này vào ngày 2").

### 5.10 Cinematic recap + PDF (PDF desktop ✅; recap ⏳)
- Nút "Xem hành trình" (bản đơn giản, làm cùng UI mới): camera bay qua các Stop, dừng được bất cứ lúc nào.
- Recap đầy đủ: bay toàn tuyến kèm thuyết minh TTS.
- Organizer xuất PDF là snapshot của version Itinerary đang xem, gồm Itinerary theo ngày và bảng chi phí. PDF ghi số version và thời điểm xuất; muốn chia sẻ lịch mới thì xuất lại sau khi có version mới.
- Organizer gửi PDF qua kênh bên ngoài Travility. Phản hồi được nhập trong Trip Chat bằng luồng **Góp ý nhóm** (§5.12). PDF không cấp quyền truy cập Trip.

### 5.11 Revision giữ mục đích 🟡 (mới, từ ý tưởng Local Explorer AI)
Spec: [2026-09-29-revision-giu-muc-dich-design.md](superpowers/specs/2026-09-29-revision-giu-muc-dich-design.md) · [ADR-0006](adr/0006-thay-the-theo-muc-dich-bang-code.md).
- **Intent** và **Intent Retention (R)**: chip ✓/✗ và R trên Timeline.
- **Disruption** do người dùng báo (đóng cửa · không thích · mưa · trễ giờ) → code (không LLM) tạo tối đa 3 **Proposal** giữ Intent của Stop bị mất, kèm bảng so sánh và giải thích từ số liệu. "Áp dụng" tạo version mới.
- **Bản đồ theo thời điểm:** kéo giờ → Place tô màu theo mở + đến kịp / mở nhưng xa / đóng; thêm Place vào đúng giờ đó.
- **Đánh giá:** ~40 kịch bản cố định, so B0 (gần nhất) / B1 (gần nhất + qua bộ lọc) / B2 (engine). Sau đó gán nhãn 0–3, train XGBRanker; chỉ bật khi thắng hàm điểm tay (NDCG@5).

Trạng thái: lát A (Intent + R) và lát B (đóng cửa / không thích → Proposal → áp dụng) đã có. Lát C–F (mưa, trễ giờ, bản đồ theo thời điểm, đánh giá, ranker, chat → Disruption) chưa làm.

Tiêu chí chấp nhận: "Báo đóng cửa" cho phương án trong < 2 s, cùng Intent, không có Conflict cứng mới, không đụng Pinned Stop; bảng B0/B1/B2 chạy được bằng `uv run python -m eval.run`.

### 5.12 Chia sẻ và duyệt góp ý lịch

#### Giai đoạn 1 — Desktop (đã triển khai; kiểm tra hộp thoại in trên máy người dùng đang chờ)
- Trip mặc định riêng tư và chỉ Organizer truy cập được. Organizer xuất PDF của version đang xem, sau đó gửi qua kênh họ chọn bên ngoài Travility; app không tự gửi PDF hay cấp quyền truy cập qua file này.
- Organizer mở **Góp ý nhóm** trong Trip Chat, chọn version mà phản hồi nói tới (mặc định version đang xem), rồi nhập hoặc tóm tắt góp ý từ nhóm. Chat thông thường tiếp tục dùng Revision như trước.
- Nếu góp ý nhắc đến version cũ hơn bản mới nhất, app cảnh báo và tạo preview dựa trên Itinerary mới nhất; vẫn giữ version nguồn để đối chiếu.
- AI diễn giải góp ý thành thay đổi. Code tính lại chi phí/Leg và kiểm tra luật; app hiện tóm tắt, Stop thay đổi, chi phí và Conflict trong preview. Preview chưa tạo version.
- Organizer chọn **Áp dụng** hoặc **Huỷ**. Huỷ không tạo version Itinerary mới; góp ý vẫn nằm trong Trip Chat và proposal được ghi nhận là đã huỷ. Áp dụng tạo version Itinerary mới, giữ nguyên các version trước. Nếu Itinerary nền đổi sau khi tạo preview, từ chối áp dụng preview cũ và yêu cầu tạo lại trên bản mới.
- Tiêu chí chấp nhận: PDF khớp version được chọn và ghi rõ số version; preview không tạo version trước khi áp dụng; Huỷ không đổi lịch; Áp dụng tạo version mới; preview dựa trên version cũ báo rõ ngữ cảnh và được kiểm tra bằng luật của code.

#### Giai đoạn 2 — Mobile native (kế hoạch, chưa triển khai)
- Organizer bật chia sẻ Trip và gửi link/mã mời riêng. Guest không cần tài khoản; lời mời chỉ cho phép xem Itinerary đang chia sẻ và gửi góp ý, không cho xem Trip Chat, Traveler Profile hay Trip khác.
- Guest xem lịch ở chế độ chỉ đọc, có thể chọn **Giữ lại** hoặc **Muốn đổi** cho từng Stop và thêm ghi chú. Góp ý gắn với version được xem; nếu lịch đã đổi, góp ý cũ vẫn giữ nguyên version nguồn.
- Organizer xem tên và từng góp ý trên desktop, sau đó đưa phản hồi vào cùng luồng preview, áp dụng hoặc huỷ như giai đoạn 1. Guest chỉ thấy tổng hợp của nhóm.
- Lời mời hết hạn theo ngày kết thúc chuyến đi (hoặc ngày Organizer chọn nếu chưa có ngày đi) và có thể thu hồi sớm. Push chỉ gửi tới thiết bị đã bật thông báo.
- Đây là kế hoạch cho app mobile native; không làm web app. Framework, push provider và phát hành store sẽ được quyết định riêng trước khi triển khai giai đoạn này.

## 6. Quy tắc nghiệp vụ

Code thực thi, không để prompt quyết định. Nguồn: spec + các quyết định mới.

- AI chỉ tham chiếu Place trả về từ tool. Place lạ bị từ chối, AI làm lại 1 lần (ADR-0001).
- **LLM chỉ chọn Place và xếp giờ; tiền, Leg và Conflict do code tính** (`server/app/rules.py`).
- Budget = ăn + vé + Stay + chi phí Leg; không gồm di chuyển liên tỉnh.
- Một Stay cho cả Trip (bắt buộc khi Trip > 1 ngày); đêm × số phòng (2 người/phòng); không phải Stop.
- Chi phí Stop = giá Place × số người. Xe máy thuê = ngày × số xe (2 người/xe).
- Pace: thong thả 3–4 Stop (9h–20h) · vừa 5 (8h–21h) · dày 6–7 (7h–22h).
- Conflict: vượt Budget · ngoài giờ mở cửa (theo thứ nếu có ngày đi) · thiếu Tag bắt buộc · Stop ngoài trời ngày mưa ≥ 60% · *(mới)* không kịp di chuyển giữa hai Stop.
- Stop ngày 1 cách giờ đến ≥ 60 phút; Stop ngày cuối kết thúc trước giờ về ≥ 90 phút (Conflict `before_arrival` / `after_departure`).
- Biết Arrival Mode và Destination có Hub → ngày 1 xuất phát từ Hub, ngày cuối kết thúc tại Hub.
- Revision không được sửa hay xoá Pinned Stop. Ghim không tạo version.
- Itinerary bất biến. Mọi thay đổi (kể cả "quay lại bản cũ") tạo version mới.
- Câu chat thắng Traveler Profile khi mâu thuẫn.
- Trip: 1–7 ngày, 1–10 người, Budget > 0, đúng một Destination.
- Trip thuộc đúng một User và mặc định riêng tư. Trong desktop giai đoạn 1, chỉ Organizer truy cập Trip; PDF là snapshot tĩnh do Organizer tự gửi ngoài app. Quyền Guest xem lịch được cấp riêng trong mobile giai đoạn 2, không bao gồm Trip Chat, Traveler Profile hoặc Trip khác.
- GroupReview gắn với version nguồn. Preview không phải version; chỉ Organizer áp dụng mới tạo version Itinerary kế tiếp. Không tự chọn ý kiến đa số và không tự đổi lịch.
- Proposal do code tạo, không do LLM (ADR-0006); không bao giờ tự áp dụng. `rain`/`late` không đụng Pinned Stop.

## 7. UI/UX

### 7.1 Luồng màn hình
```
Mở app ─► có token? ─không─► [Đăng nhập / Đăng ký] ─(đăng ký)─► [Onboarding sở thích] (bỏ qua được)
             │ có                      │                                   │
             ▼                         ▼                                   ▼
       [Màn chính] ◄───────────────────┴───────────────────────────────────┘
       mở Trip gần nhất (hoặc empty state nếu chưa có)
```

### 7.2 Bố cục màn chính (thay 3 cột cố định hiện tại)
```
┌──┬──────────────────────────────────────────────────────────┐
│R │                 BẢN ĐỒ 3D TOÀN MÀN HÌNH                  │
│A │  ┌───────────┐                          ┌─────────────┐  │
│I │  │ CHAT      │                          │ TIMELINE    │  │
│L │  │ panel nổi │     pin, tuyến, popup    │ panel nổi   │  │
│  │  │ thu gọn   │                          │ v1·v2·v3    │  │
│  │  │ được      │                          │ chi phí,    │  │
│  │  │ [🎤][ô][➤]│   [▶ Xem hành trình]     │ Conflict    │  │
│  │  └───────────┘                          └─────────────┘  │
└──┴──────────────────────────────────────────────────────────┘
Rail: ＋ Chuyến mới · 🗂 Danh sách Trip (ngăn kéo) · 👤 Hồ sơ · ⎋ Đăng xuất
```

### 7.3 Hành vi theo sự kiện
| Thời điểm | Chat | Map | Timeline |
|---|---|---|---|
| Chưa có Trip | Empty state có ảnh + câu gợi ý bấm được | Destination mặc định | Ẩn / thu gọn |
| Vừa gửi | Bong bóng user; trạng thái "AI đang lên lịch…"; khoá gửi | Xoá pin tìm kiếm cũ | — |
| `trip` | — | Bay tới thành phố | Xoá lịch trình cũ |
| `tool_call` | "Đang tìm: … (n kết quả)" | Pin vàng nhấp nháy dồn dần | — |
| `itinerary` (lần đầu) | Tóm tắt của AI (+ TTS) | Vẽ tuyến theo màu ngày; **fit toàn tuyến** (không tự bay) | Tổng tiền, Conflict, các ngày |
| `itinerary` (Revision) | Tóm tắt thay đổi | Animate Stop đổi | Version mới trong dãy; tô sáng Stop đổi |
| `error` | Bong bóng đỏ, lời nhắn tiếng Việt | — | — |

### 7.4 Tương tác
- **Map ↔ Timeline hai chiều.** Bấm Stop trên Timeline → map bay tới Place + mở popup. Bấm pin → Timeline cuộn tới Stop đó.
- **Popup Place:** ảnh, tên, giá, giờ mở hôm đó, trong nhà/ngoài trời, nút **Ghim**.
- **"Xem hành trình":** camera bay qua từng Stop, dừng được. Người dùng luôn có thể kéo map.
- **Danh sách Trip:** Destination, số ngày, ngày tạo. Bấm để mở Trip kèm lịch sử chat và version mới nhất.
- **Chia sẻ và góp ý:** Organizer xuất PDF của version đang xem. Trong Trip Chat, chọn **Góp ý nhóm**, chỉ rõ version nguồn, xem preview rồi áp dụng hoặc huỷ. Luồng này không thay đổi cách gửi Revision thông thường.

### 7.5 Nguyên tắc thẩm mỹ
- Bản đồ là nhân vật chính, chiếm trọn màn hình. Chat và Timeline là panel nổi bán trong suốt, thu gọn được.
- Tông ấm gợi du lịch Việt; có logo; empty state có ảnh; thẻ Stop có ảnh Place.
- Luôn hiện tiến trình thay vì spinner trống. Lỗi hiện bằng câu tiếng Việt thân thiện, không chặn thao tác.
- Mockup chi tiết chốt trong một phiên thiết kế riêng trước khi code UI mới.

## 8. Kiến trúc

Chi tiết: [ADR-0002](adr/0002-postgres-tu-host-app-desktop-la-client.md), [ADR-0003](adr/0003-mot-sdk-openai-hai-provider.md), [ADR-0004](adr/0004-goong-cho-ban-do.md).

> **Chỉnh 2026-10-01:** server sẽ thành một cụm 4 service (`api`, `planner`, `llm-gateway`, `places`) sau `nginx`, có Redis (queue, cache, rate limit), bản sao đọc và 2 shard — [ADR-0007](adr/0007-cum-phan-tan-tren-docker-compose.md), [ADR-0008](adr/0008-cap-theo-loai-du-lieu.md), [spec](superpowers/specs/2026-10-01-scale-he-phan-tan-design.md). Sơ đồ dưới đây là **chế độ đơn giản**, vẫn chạy được và là mặc định khi dev. Hợp đồng HTTP + SSE với client không đổi.

```
CLIENT (desktop/ + client/)          pywebview + React/Vite/Tailwind + MapLibre (tile/Directions Goong)
   │ HTTP + SSE, JWT                  chỉ lưu JWT
SERVER (docker compose)
   api  FastAPI: auth · agent · tools · rules · forecast · (voice · vision · demo_cache)
        giữ key LLM/embedding; gọi OpenAI/Gemini, Open-Meteo, Goong Distance Matrix (mới)
   db   Postgres + pgvector: users, traveler_profiles*, destinations, places, trips,
        itineraries (version), messages*        (* = bảng mới)
```
- Server tắt thì app không dùng được. Khi demo, cả hai chạy trên một laptop; cổng chỉ mở trên `127.0.0.1`.
- **API đã thêm:** `POST /trips/{id}/plan` (SSE; áp câu trả lời của event `clarify` rồi lập lịch).
- **API đã thêm (2026-09-30):** `GET /trips/{id}?version=N` · `PATCH /trips/{id}/pins` · `POST /trips/{id}/restore/{version}` · `GET /trips/{id}/messages`. Revision đi qua `POST /trips` với `trip_id` (followup), không cần endpoint riêng.
- **Event SSE:** giữ 6 event hiện có (thêm `clarify` — event cuối của `POST /trips` khi thiếu thông tin). Event `itinerary` thêm `version` và danh sách Stop đã đổi. Thêm event mới thì phải sửa cả server lẫn kiểu `AgentEvent` trong `client/src/api.ts`.

## 9. Dữ liệu Place

- Nguồn duy nhất: `data/places/<destination>.json`, commit vào git. Nạp bằng `scripts/import_places.py` (upsert, sinh embedding). Không có màn Admin; sửa Place = sửa JSON + PR + chạy lại import.
- Trường: `ext_id`, tên, `kind` (an-uong, cafe, tham-quan, giai-tri, cho-o), toạ độ, giá, giờ mở theo thứ, trong nhà/ngoài trời, Tag (bộ từ vựng cố định), mô tả, ảnh.
- **Quy trình bán tự động:**
  1. Lấy ứng viên (tên, toạ độ, loại) từ OpenStreetMap/Goong.
  2. AI nháp Tag, mô tả, giá.
  3. **Thành viên kiểm chứng tay** (Place phải có thật và đúng).
  4. Commit JSON.
- Mục tiêu: Đà Lạt ≥ 150 (hiện 10) trước T4; Đà Nẵng – Hội An ≥ 150 trước T8 (Destination thứ 3 đã cắt).
- Ảnh Place lưu local phía server để demo không phụ thuộc mạng.

## 10. Yêu cầu phi chức năng
- **Hiệu năng:** event đầu < 2 s; Itinerary < 30 s với OpenAI.
- **Chịu lỗi:** Goong lỗi → vẽ đường thẳng / dùng km chim bay; Forecast lỗi → bỏ qua; LLM lỗi → thông báo thử lại; stream đứt → báo trong chat.
- **Demo offline:** cache của `llm-gateway` ở chế độ `replay` phát lại phản hồi theo hash(request) (#14 gộp vào #48).
- **Quy mô (mới 2026-10-01):** mỗi kỹ thuật — load balancing, caching, rate limit, message queue, microservice, replication, sharding, CAP — phải trình diễn được trên laptop demo bằng load test hoặc tắt node; bảng trình diễn ở spec §12.
- **Bảo mật:** mọi secret nằm trong `.env`, không commit. Key Goong nằm trong bundle client, chấp nhận cho demo; nếu phát hành phải giới hạn domain hoặc cho server làm proxy.
- **Tiếng Việt:** toàn bộ UI và câu trả lời AI bằng tiếng Việt.
- **Đóng gói:** PyInstaller cho client desktop; server bằng `docker compose`.

## 11. Ngoài phạm vi giai đoạn 1
- Phát hành cho người dùng thật, hosting trên cloud. (Cụm nhiều service trên một laptop đã **vào** phạm vi từ 2026-10-01.)
- Tự động chuyển node chính khi database chết; thêm shard khi đang chạy; cache theo ngữ nghĩa.
- Dự đoán động đất, dự đoán độ đông, recommender (cân nhắc và loại 2026-10-01).
- Nhiều Stay trong một Trip; đặt phòng / thanh toán.
- Guest tự xem Trip và gửi góp ý trực tiếp ngoài desktop: dự kiến ở mobile native giai đoạn 2 (§5.12), chưa triển khai trong giai đoạn 1.
- Web app; không nằm trong các giai đoạn hiện tại.
- Thuật toán tối ưu thứ tự Stop.
- Di chuyển liên tỉnh (vé máy bay, xe khách).
- Màn Admin quản lý Place.

## 12. Lộ trình & phân vai

Bắt đầu 2026-09-25. Công việc được theo dõi bằng GitHub Issues #2–#41; bảng tổng ở issue #42 và [ROADMAP.md](ROADMAP.md).

> **Chỉnh 2026-10-01:** Thành thêm lát scale hệ phân tán T2–T6 (#48–#52) và mô hình dự đoán mưa T7 (#53); nhận #14 từ Tùng. #37 + #26 dời sang T8.
>
> **Chỉnh 2026-09-30:** Thành + AI gánh lõi và đường găng. Việc của thành viên khác là việc thêm, tách rời và cắt được, không chặn ai. Lộ trình theo tuần mới nằm ở [ROADMAP.md](ROADMAP.md).

| Thành viên | Vai | Issue |
|---|---|---|
| **Đỗ Chí Thành** (@toilact) — trưởng nhóm | B: Agent, rules, Revision (đường găng) + Goong Matrix + golden set + demo | #17, #22, #24, #25, #26, #39, #18, #38, #7, #31, #32, #36, #37, #6, #29 |
| **Đặng Trần Minh Nhật** (@minhatt1901) | A: Client React, bản đồ, UI mới, giọng nói phía client, recap | #2, #3, #4, #16, #23, #40, #8, #9, #28 |
| **Nguyễn Thanh Tùng** (@nguyentung206) | D: Bản đồ theo thời điểm, PDF, Google login, quên mật khẩu, demo_cache, đóng gói | #33, #11, #12, #13, #14, #15 |
| **Nguyễn Duy Quân** (@skyduyquan2-sudo) | C: Dữ liệu Place (script thu thập + 2 Destination), đánh giá engine + ranker | #5, #19, #20, #41, #34, #35 |

| Tuần | Nội dung | Trạng thái |
|---|---|---|
| T1 | Plan 1: nền tảng + AI Trip Planner lõi | ✅ |
| T2–3 | Plan 2: Revision + Pinned + version + Traveler Profile; UI mới (map full, panel nổi, rail, Map↔Timeline) | ⏳ |
| T4 | Đà Lạt 150 Place; Goong Distance Matrix + Conflict "không kịp" | ⏳ |
| T5 | Giọng nói (STT/TTS) | ⏳ |
| T4–T6 | Revision giữ mục đích (lát A–D, §5.11): Intent, engine, ProposalPanel, mưa/trễ, bản đồ theo thời điểm | 🟡 A, B xong |
| T5–T8 | Đánh giá B0/B1/B2 + ranker (lát E) — Quân | ⏳ |
| T6 | ~~Inspiration Photo~~ (cắt) → Tùng làm bản đồ theo thời điểm | — |
| T7 | Google login + quên mật khẩu | ⏳ |
| T8 | Cinematic recap; Destination thứ 2 (thứ 3 đã cắt) | ⏳ |
| T9 | Chuyển sang OpenAI, golden set, polish | ⏳ |
| T10 | demo_cache, PyInstaller, kịch bản và diễn tập demo | ⏳ |
| Bổ sung 2026-10-14 | Desktop giai đoạn 1: PDF snapshot + GroupReview trong Trip Chat | ✅ trong code; kiểm tra hộp thoại in thủ công đang chờ |
| Giai đoạn 2 | Mobile native: Guest xem lịch được chia sẻ và gửi góp ý trực tiếp; không làm web | ⏳ chưa triển khai |

## 13. Thứ tự cắt khi trễ
Đã cắt (2026-09-29, nhường chỗ §5.11): Inspiration Photo, Destination thứ 3.
Đã cắt (2026-09-30, nhóm thực tế do một người gánh đường găng): Google login + quên mật khẩu (#12, #13), Traveler Profile + onboarding (#18, #23), cá nhân hoá lát 2 (#38), Destination thứ 2 Đà Nẵng – Hội An (#20).

Lát scale (2026-10-01) cắt theo thứ tự riêng, không đụng danh sách dưới: sharding → tách `places` → đa agent (về agent đơn). Mô hình mưa cắt được độc lập. #26 là thứ cắt đầu tiên nếu T8 trễ.

1. Cinematic recap (giữ nút "Xem hành trình" đơn giản)
2. ML ranker (giữ bảng B0/B1/B2)
3. Bản đồ theo thời điểm

**Không cắt:** lõi lập Itinerary · Revision + Pinned + version · Disruption → Proposal (lát A–C) · email/mật khẩu · UI mới · Đà Lạt 150 Place.

## 14. Rủi ro
| Rủi ro | Xử lý |
|---|---|
| Gemini và OpenAI khác nhau về tool-calling | Golden set 15 prompt chạy trên cả hai; 2 tuần cuối chỉ dùng OpenAI |
| Thiếu dữ liệu → AI lặp Place, demo kém | Quy trình bán tự động; Đà Lạt ưu tiên số 1 |
| Server phải chạy khi demo | `docker compose up` trên laptop demo; checklist khởi động |
| Mạng yếu khi demo | demo_cache replay; ảnh Place lưu local |
| Làm lại UI tốn thời gian | Chốt mockup trước; giữ nguyên logic SSE hiện có |
| Revision đổi quá nhiều Stop | Kiểm tra bằng code + golden set Revision |
| Goong Matrix hết quota / lỗi | Fallback công thức chim bay × 1.3 |
| Cụm phân tán làm demo kém ổn định | Chế độ đơn giản (`docker compose up`) là đường lui; đóng băng kiến trúc cuối T6 |

## 15. Câu hỏi mở
- ~~Có cần ADR cho việc chuyển tính km sang Goong Distance Matrix ở server không?~~ Không (2026-10-01): quyết định đã nằm ở §5, đảo lại chỉ cần bỏ `GOONG_API_KEY`.
- Nguồn ảnh Place (tự chụp, Goong, Wikimedia) và vấn đề bản quyền.
- Giới hạn độ dài lịch sử chat gửi cho LLM trong mỗi Revision.
- Có vẽ lại tuyến đường trên map bằng dữ liệu từ server để khỏi gọi Goong Directions ở client không?
