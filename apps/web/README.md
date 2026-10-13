# Local Explorer AI — Frontend Web Application

Ứng dụng Web SPA hiện đại của nền tảng **Local Explorer AI**, được xây dựng trên nền tảng **React 18.3**, **TypeScript 5.6**, **Vite 6**, và đồ họa **Three.js (WebGL 3D)**. Giao diện được thiết kế theo phong cách *Nocturnal Emerald Glassmorphic* kết hợp *Warm Light Theme*, tối ưu hóa trải nghiệm thị giác và tương tác mượt mà cho du khách khám phá TP. Hồ Chí Minh.

---

## 🎨 Điểm Nhấn Thiết Kế & Công Nghệ (Design & Tech Stack)

- **Cốt lõi**: [React 18.3](https://react.dev/), [TypeScript 5.6](https://www.typescriptlang.org/), [Vite 6](https://vitejs.dev/)
- **Đồ họa Không gian 3D**: [Three.js](https://threejs.org/) WebGL Digital Twin — mô phỏng các tòa cao ốc trung tâm TP.HCM, dòng sông Sài Gòn phản quang uốn lượn, hiệu ứng neon rực rỡ và camera chuyển động thị sai (Parallax). Tích hợp Trình xem 3D Landmark Viewer (`/map-3d`) nạp mô hình GLB chi tiết các công trình biểu tượng (Nhà thờ Đức Bà Sài Gòn...) với hệ thống kiểm soát góc xoay, độ cao và tỉ lệ thực tế.
- **Thẻ 3D Tilt Card**: Hiệu ứng góc nhìn đa chiều (`perspective: 1000px`) với lớp phủ phản chiếu vệt sáng gương (*specular glare overlay*) chuyển động mềm mại.
- **Bản đồ Địa lý Đa chế độ**: [Leaflet](https://leafletjs.com/) + [React-Leaflet](https://react-leaflet.js.org/) tích hợp CartoDB Voyager (chế độ Sáng) và CartoDB Dark Matter (chế độ Tối), hiển thị các điểm ghim radar nhấp nhô và vẽ hình học tuyến đường thực tế từ Goong API.
- **Hệ thống Song ngữ Toàn diện (VI / EN)**: Bộ chuyển đổi ngôn ngữ nhanh trên thanh điều hướng (`LanguageSwitcher`), hỗ trợ đầy đủ tiếng Việt và tiếng Anh.
- **Hệ thống Chủ đề Kép (Dual Theme)**:
  - 🌙 **Nocturnal Emerald Dark Theme**: Phong cách đêm huyền bí cyberpunk, viền sáng neon lục bảo và hiệu ứng kính mờ (Glassmorphism).
  - ☀️ **Warm Light Theme**: Phong cách ban ngày tươi sáng, ấm áp, độ tương phản cao và trang nhã.
- **Bộ biểu tượng**: [Lucide React](https://lucide.dev/)
- **Điều hướng & Phân quyền**: [React Router DOM v6](https://reactrouter.com/) kết hợp hệ thống Route Guards (`CustomerRoute`, `RoleRoute`) và tự động định hướng theo vai trò (`RoleHome`).
- **Offline Mock Engine Fallback**: Tự động kích hoạt bộ giả lập heuristic cục bộ khi không có kết nối backend, đảm bảo người dùng và ban giám khảo luôn trải nghiệm được sản phẩm mượt mà không bị gián đoạn.

---

## 🧭 Kiến trúc Trang & Tuyến đường (Pages & Routes)

| Tuyến đường (Route) | Tên Trang | Mô tả & Chức năng | Phân quyền truy cập |
|---|---|---|---|
| `/` | `RoleHome` / `HomePage` | Trang chủ với Canvas 3D WebGL Sài Gòn, thông điệp định vị và lối tắt nhanh. Tự động chuyển hướng nếu là Provider hoặc Admin | Công khai |
| `/map-3d` | `Map3DPage` | Bản đồ & Trình diễn 3D Digital Twin các công trình biểu tượng (Nhà thờ Đức Bà...), xoay / phóng to thu nhỏ / xem thông tin kiến trúc & lịch sử | Công khai |
| `/places` | `PlacesPage` | Danh mục địa điểm du lịch & văn hóa Sài Gòn (Quận 1...), tìm kiếm, lọc theo loại hình, đánh giá sao và hình ảnh thực địa | Khách du lịch (`traveler`) / Vãng lai |
| `/places/:id` | `PlaceDetailPage` | Chi tiết địa điểm: bộ sưu tập ảnh, bản đồ vị trí, giờ mở cửa, giá vé, đánh giá trải nghiệm và liên kết hoạt động | Khách du lịch (`traveler`) / Vãng lai |
| `/explore` | `ExplorePage` | Khám phá danh mục địa điểm và hoạt động, tìm kiếm ngữ nghĩa E5, bộ lọc đa chiều và bản đồ radar | Khách du lịch (`traveler`) / Vãng lai |
| `/chat` | `ChatPage` | Trợ lý AI Concierge thông minh, trích xuất ràng buộc chuyến đi với Live Constraints Inspector, tạo lịch trình 1-chạm | Khách du lịch (`traveler`) / Vãng lai |
| `/planner` | `PlannerPage` | Wizard lập lịch trình 3 bước, tự động gợi ý địa chỉ qua Goong Geocoding, Thẻ xem trước 3D Live Day Preview | Khách du lịch (`traveler`) / Vãng lai |
| `/itinerary/:id` | `ItineraryPage` | Dòng thời gian laser, 4 thẻ KPI 3D, đường đi Goong geometry, đặt chỗ 15p & thanh toán VNPay/MoMo, hộp thoại đổi lịch Replan | Khách du lịch (`traveler`) / Vãng lai |
| `/compare` | `ComparePage` | So sánh trực quan song song 2 lịch trình: chênh lệch chi phí, danh sách điểm dừng thêm/bớt và thời gian | Chỉ dành cho Traveler đã đăng nhập |
| `/shared/:token` | `SharedItineraryPage` | Giao diện xem lịch trình công khai bảo mật qua token, tối ưu cho thiết bị di động | Công khai |
| `/login` & `/register` | `AuthPage` | Đăng ký, đăng nhập tài khoản Email/Password hoặc Google OAuth 2.0 PKCE 1-chạm | Công khai |
| `/profile` | `ProfilePage` | Quản lý thông tin cá nhân, danh sách lịch trình đã lưu và đổi mật khẩu | Người dùng đã đăng nhập |
| `/provider` | `ProviderPage` | Trang thông tin và giới thiệu dành cho các nghệ nhân, đối tác văn hóa bản địa | Khách du lịch (`traveler`) / Vãng lai |
| `/provider-portal` | `ProviderPortalPage` | Cổng quản lý hoạt động, khung giờ (Optimistic Locking), Trợ lý AI HMAC 2 bước (`ProviderSlotAssistantPanel`), tài liệu minh chứng, xem & duyệt yêu cầu đặt chỗ | Đối tác (`provider`) / Admin |
| `/admin` | `AdminPage` | Bảng điều khiển KPI, hàng đợi duyệt Moderation, phát hiện & hợp nhất POI trùng lặp, quản lý tài khoản, cấu hình Integrations (VNPay, MoMo, Goong, Gemini, Google), quản trị Telegram Bot & n8n webhook, tham số hệ thống Planner, Place Import Staging, AI Tools, Flood Risk, Operations Panel và Audit Logs | Quản trị viên (`admin`) |
| `/about` | `AboutPage` | Giới thiệu sứ mệnh dự án, đội ngũ phát triển, kiến trúc kỹ thuật và giải pháp công nghệ | Khách du lịch (`traveler`) / Vãng lai |

---

## 📁 Cấu trúc Thư mục (`apps/web`)

```text
apps/web/
├── public/                # Tài nguyên tĩnh (favicon, logo, icons, models_3d test pages)
├── src/
│   ├── api/               # API Client (Axios) tích hợp Offline Mock Engine Fallback
│   ├── components/        # Thư viện thành phần giao diện:
│   │   ├── 3d/            # CityHero3D (WebGL Cityscape), Map3DLandmarkViewer (GLB loader), TiltCard3D, landmark/
│   │   ├── common/        # LanguageSwitcher, StatusBadge
│   │   ├── experience/    # ExperienceCard hiển thị thẻ trải nghiệm & tags
│   │   └── map/           # MapAdapter (Leaflet + CartoDB tiles + Goong polylines)
│   ├── hooks/             # Custom React Hooks (theme, window size, debounce)
│   ├── layouts/           # AppLayout (Header thanh điều hướng nổi, Theme toggle, Footer)
│   ├── locales/           # Từ điển đa ngôn ngữ (vi.ts, en.ts)
│   ├── pages/             # 16 trang ứng dụng chính & các Panels nghiệp vụ:
│   │   ├── HomePage.tsx               # Trang chủ với Canvas 3D
│   │   ├── Map3DPage.tsx              # Bản đồ 3D Landmark công trình biểu tượng
│   │   ├── PlacesPage.tsx             # Danh mục địa điểm du lịch & văn hóa Sài Gòn
│   │   ├── PlaceDetailPage.tsx        # Trang chi tiết địa điểm du lịch & ảnh thực tế
│   │   ├── ExplorePage.tsx            # Khám phá danh mục & Semantic search
│   │   ├── ChatPage.tsx               # AI Concierge Chatbot & Constraints
│   │   ├── PlannerPage.tsx            # Lập lịch trình 3 bước & Preview 3D
│   │   ├── ItineraryPage.tsx          # Dòng thời gian, Goong route, thanh toán
│   │   ├── ComparePage.tsx            # So sánh 2 phương án lịch trình
│   │   ├── SharedItineraryPage.tsx    # Xem lịch trình chia sẻ công khai
│   │   ├── AuthPage.tsx               # Đăng nhập & Đăng ký
│   │   ├── ProfilePage.tsx            # Hồ sơ người dùng & lịch trình đã lưu
│   │   ├── ProviderPage.tsx           # Giới thiệu đối tác địa phương
│   │   ├── ProviderPortalPage.tsx     # Cổng quản lý của nghệ nhân / đối tác
│   │   ├── ProviderSlotAssistantPanel.tsx # Trợ lý AI tạo slot 2 bước HMAC
│   │   ├── AdminPage.tsx              # Cổng Quản trị viên trung tâm
│   │   ├── AdminAiToolsPanel.tsx      # Quản trị prompt & model AI
│   │   ├── AdminFloodRiskPanel.tsx    # Bảng phân tích rủi ro ngập lụt
│   │   ├── AdminOperationsPanel.tsx   # Giám sát email outbox & hệ thống
│   │   └── AboutPage.tsx              # Giới thiệu dự án & kiến trúc
│   ├── auth.tsx           # Context quản lý phiên đăng nhập và các Guard (CustomerRoute, RoleRoute)
│   ├── router.tsx         # Cấu hình React Router v6
│   ├── styles.css         # Hệ thống Design Tokens, 3D Effects, Glassmorphism, Dual Theme
│   ├── main.tsx           # Điểm khởi đầu ứng dụng React
│   └── types.ts           # Định nghĩa TypeScript Types & Data Schemas
├── index.html             # HTML template chính với Google Fonts (Be Vietnam Pro, Inter)
├── package.json           # Danh sách thư viện và scripts npm
├── postcss.config.js      # Cấu hình PostCSS & Autoprefixer
├── tailwind.config.js     # Cấu hình Tailwind CSS
├── tsconfig.json          # Cấu hình TypeScript compiler
└── vite.config.ts         # Cấu hình Vite build tool & proxy
```

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy Cục bộ

### Yêu cầu tiên quyết:
- Đã cài đặt **Node.js 18+** hoặc **Node.js 20+**
- Trình quản lý gói `npm` (đi kèm Node.js)

### Bước 1: Cài đặt thư viện dependencies
```powershell
cd apps/web
npm install
```

### Bước 2: Khởi chạy Development Server
```powershell
npm run dev
```
Sau khi khởi chạy thành công, mở trình duyệt tại:
👉 **[http://localhost:8080](http://localhost:8080)** *(hoặc [http://localhost:5173](http://localhost:5173) tùy theo cấu hình cổng)*

*Lưu ý: Mặc định Vite trong `vite.config.ts` được cấu hình proxy tự động chuyển tiếp các yêu cầu `/api` và `/health` sang backend chạy tại `http://127.0.0.1:8000`.*

### Bước 3: Kiểm tra lỗi kiểu dữ liệu (Lint / Typecheck)
```powershell
npm run lint
```

### Bước 4: Đóng gói ứng dụng cho Production (Build)
```powershell
npm run build
```
*Kết quả build sẽ nằm tại thư mục `apps/web/dist/`, sẵn sàng triển khai qua Nginx hoặc dịch vụ lưu trữ tĩnh.*

> [!TIP]
> **Lưu ý triển khai trên môi trường Linux / CI (GitHub Actions):**
> Do lỗi xử lý gói phụ thuộc tùy chọn hệ điều hành của npm (issue [#4828](https://github.com/npm/cli/issues/4828)), khi tạo lockfile từ Windows/macOS, tệp nhị phân Rollup Linux có thể bị thiếu trên môi trường CI. Pipeline CI tại `.github/workflows/ci.yml` đã được cấu hình tự động bổ sung `@rollup/rollup-linux-x64-gnu` đảm bảo quá trình build luôn thành công ổn định.

---

## 💡 Trải nghiệm Demo & Offline Fallback

Khi khởi chạy frontend độc lập mà backend FastAPI chưa bật:
- Ứng dụng sẽ tự động phát hiện mất kết nối backend và kích hoạt **Offline Mock Engine**.
- Du khách vẫn có thể:
  - Trải nghiệm khám phá các hoạt động demo trên bản đồ.
  - Sử dụng AI Concierge Chatbot (chế độ phản hồi offline thông minh).
  - Lập lịch trình và xem dòng thời gian 3D với dữ liệu mẫu hoàn chỉnh.
- Khi backend được kích hoạt, ứng dụng sẽ tự động chuyển sang gọi RESTful API trực tiếp mà không cần cấu hình thêm.
