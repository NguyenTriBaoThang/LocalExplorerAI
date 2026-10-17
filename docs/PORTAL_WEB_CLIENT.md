# Portal ↔ Web khách: dữ liệu và màn hình tương ứng

Tài liệu này ghi lại **portal (đối tác + quản trị) thu thập/quản lý dữ liệu gì**, **API nào đưa dữ liệu đó ra web khách**
(`apps/web`), và **màn hình/chức năng nào trên web dùng nó**. Khi thêm một trường mới trong portal, cập nhật bảng ở đây
để đội web biết cần hiển thị gì.

Trạng thái: ✅ đã làm trên web · 🟡 làm một phần · ⬜ chưa làm (đề xuất)

## 1. Dữ liệu do portal quản lý

### 1.1 Địa điểm & danh lam thắng cảnh (admin → `Địa điểm & Danh thắng`)

| Trường | Ý nghĩa | API công khai | Web |
|---|---|---|---|
| `name`, `category`, `district`, `address`, `latitude`, `longitude` | Thông tin bắt buộc, được xác minh theo nguồn khi xuất bản | `GET /api/pois`, `GET /api/pois/{id}` | ✅ `/places/:id`, bản đồ Khám phá |
| `description` | Mô tả dài | như trên | ✅ `/places/:id` |
| `image_urls[]` | Ảnh, ảnh đầu là ảnh bìa | như trên | ✅ ảnh bìa + thư viện ảnh ở `/places/:id`, thẻ địa điểm trong bộ sưu tập |
| `opening_hours`, `ticket_info` | Giờ mở cửa, giá vé (văn bản tự do) | như trên | ✅ chip thông tin ở `/places/:id` |
| `tags[]` | Thẻ chủ đề | như trên | ✅ `/places/:id` · ✅ lọc theo thẻ ở Khám phá (Lọc thêm → Địa điểm) |
| `is_landmark` | Danh thắng nổi bật | như trên | ✅ nhãn "Danh thắng" · ✅ bộ lọc "Chỉ danh lam thắng cảnh" ở Khám phá, dải "Danh thắng" trên bản đồ 3D (liên kết `/places/:id`, nút 3D khi có mô hình) |
| `source_url` | Nguồn xác minh (chỉ admin) | không công khai; web nhận `source_evidence` | ✅ (đã có sẵn huy hiệu xác minh) |
| trạng thái `draft / verified / hidden` | Chỉ `verified` (và dữ liệu demo `simulated`) hiển thị với khách | lọc phía server | ✅ |

> Xuất bản = admin nhập URL nguồn HTTPS → hệ thống ghi minh chứng đã xác minh cho phiên bản dữ liệu hiện tại (12 tháng).
> Sửa tên/địa chỉ/tọa độ/loại của địa điểm đã xuất bản sẽ tự xác minh lại theo cùng nguồn.

### 1.2 Nội dung website (admin → `Nội dung website`)

| Dữ liệu | Trường | API công khai | Web |
|---|---|---|---|
| Banner trang chủ | `title`, `subtitle`, `image_url`, `link_url`, `is_active`, `sort_order`, `starts_at`, `ends_at` | `GET /api/content/home` → `banners` (chỉ banner đang bật và trong khung thời gian) | ✅ dải banner dưới hero trang chủ |
| Bộ sưu tập địa điểm | `title`, `description`, `place_ids[]`, `is_active`, `sort_order` | `GET /api/content/home` → `collections[].places` (bỏ qua địa điểm chưa xuất bản) | ✅ mục "Bộ sưu tập" trang chủ → `/places/:id` |
| Bài viết / Cẩm nang | `title`, `slug`, `excerpt`, `body` (Markdown), `cover_url`, `category`, `status`, `published_at` | `GET /api/content/home` → `articles` (6 bài mới), `GET /api/content/articles?category=&q=`, `GET /api/content/articles/{slug}` | ✅ mục Cẩm nang trang chủ, `/guides`, `/guides/:slug`, menu "Cẩm nang" |

Markdown hỗ trợ: `#`/`##`/`###`, đoạn văn, `- ` danh sách, `> ` trích dẫn, `**đậm**`. Web render bằng text node (không chèn HTML).

### 1.3 Đối tác & trải nghiệm (đối tác → `Trải nghiệm & Slot`, `Địa điểm của tôi`, `Hồ sơ`)

| Dữ liệu | Nơi nhập | API công khai | Web |
|---|---|---|---|
| Trải nghiệm (tên, mô tả, chủ đề, thời lượng, giá, trong nhà, tự tay làm) | Đối tác; admin kiểm duyệt ở `Nội dung website → Kiểm duyệt` | `GET /api/experiences`, `/experiences/{id}` (kèm `rating_*`, `provider_name`, `provider_slug`) | ✅ Khám phá, Lập lịch, `/experiences/:id` |
| Slot (giờ, sức chứa, chỗ trống, hạn xác nhận) | Đối tác | `GET /api/experiences/{id}/slots` | ✅ Khám phá, Lập lịch, đặt chỗ |
| Địa điểm của đối tác | Đối tác; admin duyệt | như 1.1 | ✅ |
| Hồ sơ đối tác (tên cơ sở, giới thiệu, liên hệ, website) | Đối tác; admin duyệt | `GET /api/partners?q=` (danh bạ: chỉ đối tác đã duyệt, đang hoạt động và có trải nghiệm đang mở); `GET /api/partners/{slug}` (hồ sơ, web chưa dùng). Không lộ mã số thuế, giấy phép, tài liệu, ghi chú duyệt | ✅ `/provider`: chỉ xem thẻ đối tác đang hợp tác + nút "Đăng ký trở thành đối tác" dẫn sang trang đăng ký của portal. Duyệt/khóa đối tác làm ở portal (Quản trị → Đối tác) |

### 1.4 Đánh giá (du khách viết trên web → đối tác trả lời trong portal)

| Bước | API | Màn hình |
|---|---|---|
| Du khách thấy booking đã tham gia chưa đánh giá | `GET /api/me/reviewable-bookings` | ✅ thẻ "Đánh giá trải nghiệm đã tham gia" ở `/profile` |
| Du khách gửi đánh giá (1–5 sao + nhận xét) | `POST /api/bookings/{id}/review` (booking `confirmed`, slot đã bắt đầu, mỗi booking 1 lần) | ✅ `/profile` |
| Đối tác xem & trả lời | `GET /api/provider/me/reviews`, `POST /api/provider/me/reviews/{id}/reply` | ✅ portal `Đánh giá` |
| Mọi người xem đánh giá + phản hồi | `GET /api/experiences/{id}/reviews` (tên tác giả rút gọn, VD "Anh N.") | ✅ panel dưới bản đồ ở Khám phá, `/experiences/:id` · ✅ điểm sao trên thẻ trải nghiệm (`rating_average`, `rating_count` trong `ExperienceRead`) |

### 1.5 Lượt truy cập (web gửi → portal thống kê)

| Web gửi | Khi nào | Portal dùng ở |
|---|---|---|
| `POST /api/analytics/pageview` `{visitor_id, session_id, path, referrer}` | Mỗi lần đổi route (`usePageViewTracking` trong `AppLayout`) | Admin `Tổng quan`: khách, lượt xem, trang xem nhiều, nguồn, thiết bị, theo giờ |
| … `+ {entity_type: 'poi', entity_id}` | Mở `/places/:id` | Admin: "Địa điểm được xem nhiều", lượt xem 30 ngày của từng địa điểm |
| … `+ {entity_type: 'article', entity_id}` | Mở `/guides/:slug` | Admin: trang xem nhiều |
| … `+ {entity_type: 'experience', entity_id}` | Du khách **chủ động** chọn một trải nghiệm ở Khám phá | Đối tác `Thống kê`: lượt xem, tỷ lệ chuyển đổi |

Quyền riêng tư: không lưu IP, user agent hay query string; `visitor_id`/`session_id` là số ngẫu nhiên trong
localStorage/sessionStorage và chỉ được lưu dưới dạng HMAC; tôn trọng Do-Not-Track và Global Privacy Control; bỏ qua bot;
không theo dõi `/admin`, `/provider-portal`. Nếu web thêm trang chi tiết mới (VD `/experiences/:id`), gọi `useEntityView`
và thêm đường dẫn vào `ENTITY_PAGES` trong `src/analytics.ts` để không đếm trùng.

## 2. Việc web khách nên làm tiếp

1. ✅ Trang chi tiết trải nghiệm `/experiences/:id` (mô tả, khung giờ, đánh giá, địa điểm, liên kết đối tác).
2. ✅ Danh bạ đối tác `/provider` (thẻ + nút đăng ký). Không có trang hồ sơ riêng trên web khách.
3. ✅ Điểm sao trung bình trên thẻ trải nghiệm.
4. ✅ Lọc theo `tags`/`is_landmark` ở Khám phá và dải "Danh thắng" trên bản đồ 3D.
5. ✅ `/admin` và `/provider-portal` đã gỡ khỏi web khách: hai đường dẫn này chuyển người dùng sang portal
   (`/admin`, `/partner`) theo `VITE_PORTAL_URL` (mặc định `http://localhost:8081`). Các màn hình Rủi ro ngập, Công cụ AI, Vận hành,
   Tích hợp, Nhập địa điểm & Trùng lặp, Trợ lý cập nhật ca, Nguồn xác minh đã có ở portal.
6. ✅ Các key i18n `footer.*`, `profile.savedTrips`, `profile.updateSuccess`, `provider.subtitle` đã được bổ sung.

## 3. Lưu ý vận hành

- Ảnh dùng đường dẫn tương đối (`/images/...`) phải tồn tại ở **cả** `apps/web/public` và `apps/portal/public`; với ảnh
  mới nên dùng URL HTTPS. (Chưa có chức năng tải ảnh lên — đề xuất thêm kho ảnh/S3.)
- Quyền mới (migration `0016`): `admin:places`, `admin:content`, `admin:analytics`, `provider:reviews`,
  `provider:analytics`, `review:write` — chỉnh được ở portal `Phân quyền`.
- Web khách cần `VITE_PORTAL_URL` trỏ tới portal để nhân viên đăng nhập ở web được chuyển đúng nơi.
- `PORTAL_APP_URL` phải được đặt để link email của đối tác/admin trỏ về portal và để origin của portal qua kiểm tra CSRF.
