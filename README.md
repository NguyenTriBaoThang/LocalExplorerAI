<div align="center">

<p align="center">
  <img src="./assets/images/logo.png" alt="Local Explorer AI Logo" height="200" />
</p>

<h1 align="center">Local Explorer AI</h1>

<p align="center">
  <b>Nền tảng Khám phá Trải nghiệm Đô thị Thông minh Thời gian thực, Trợ lý AI Concierge, Lập Lịch trình Khung giờ Thực (Slot-aware), Đồ họa 3D WebGL, Học máy Cục bộ (Local ML & E5) & Di chuyển Xanh cho TP. Hồ Chí Minh</b>
</p>

<p align="center">
  <a href="https://github.com/NguyenTriBaoThang/LoaclExplorerAI/actions/workflows/ci.yml">
    <img src="https://img.shields.io/badge/CI-Passing-brightgreen?logo=github" alt="CI Status"/>
  </a>
  <a href="https://github.com/NguyenTriBaoThang/LoaclExplorerAI/stargazers">
    <img src="https://img.shields.io/github/stars/NguyenTriBaoThang/LoaclExplorerAI?style=social" alt="GitHub stars"/>
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License"/>
  </a>
  <a href="./SECURITY.md">
    <img src="https://img.shields.io/badge/Security-Policy-red?logo=shield" alt="Security Policy"/>
  </a>
  <img src="https://img.shields.io/badge/PRD-3.0_Production_Ready-blueviolet" alt="PRD 3.0 Ready"/>
  <img src="https://img.shields.io/badge/ML_Ranker-NDCG%405%200.9516-success" alt="ML Ranker"/>
</p>

<p align="center">
  <b>3D WebGL Digital Twin · AI Concierge Chat · Local E5 Semantic Search · XGBoost ML Ranker · Dynamic Replanning · CartoDB 3D Vector Map · Provider & Admin Portals · Saigon Flood Risk Model</b><br/>
  React 18.3 + TypeScript 5.6 · Three.js · Vite 6 · FastAPI 0.115 · Python 3.12+ · PostgreSQL 16 + PostGIS 3.4 · Docker Compose
</p>

<p align="center">
  <a href="http://localhost:5173/"><strong>Khám phá Dashboard 3D</strong></a>
  &nbsp;|&nbsp;
  <a href="http://localhost:5173/chat"><strong>Trợ lý AI Concierge</strong></a>
  &nbsp;|&nbsp;
  <a href="./DEMO_SCRIPT.md">Kịch bản Demo</a>
  &nbsp;|&nbsp;
  <a href="./ARCHITECTURE.md">Kiến trúc Hệ thống</a>
  &nbsp;|&nbsp;
  <a href="./docs/api.md">Đặc tả API</a>
  &nbsp;|&nbsp;
  <a href="./docs/ai-prompt-catalog.md">Danh mục Prompt AI</a>
  &nbsp;|&nbsp;
  <a href="./docs/auth-and-search-setup.md">Cấu hình LLM, Google OAuth và E5</a>
  &nbsp;|&nbsp;
  <a href="./docs/integration-settings.md">Tích hợp MoMo, Goong, Gemini và quản lý khóa</a>
  &nbsp;|&nbsp;
  <a href="./docs/ml-training-and-data.md">Huấn luyện Học máy (ML)</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-18.3-61DAFB?logo=react" alt="React 18"/>
  <img src="https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript" alt="TypeScript 5.6"/>
  <img src="https://img.shields.io/badge/Three.js-WebGL_3D-black?logo=threedotjs" alt="Three.js"/>
  <img src="https://img.shields.io/badge/Vite-6.0-646CFF?logo=vite" alt="Vite 6"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16_+_PostGIS_3.4-336791?logo=postgresql" alt="PostGIS"/>
  <img src="https://img.shields.io/badge/XGBoost-Ranker-FF6600?logo=xgboost" alt="XGBoost"/>
  <img src="https://img.shields.io/badge/Sentence_Transformers-E5_Multilingual-FFD21E?logo=huggingface" alt="E5"/>
  <img src="https://img.shields.io/badge/Docker-Compose_v2-2496ED?logo=docker" alt="Docker"/>
</p>

<img src="./assets/images/banner.png" alt="Local Explorer AI Banner" width="100%"/>

</div>

---

## 🎖️ Tôn chỉ & Định vị Dự án (Mission & Technological Breakthroughs)

<p align="center">
  <b>ĐÔ THỊ THÔNG MINH · KHÁM PHÁ ĐỊA PHƯƠNG · LẬP LỊCH TRÌNH KHUNG GIỜ THỰC · TRỢ LÝ AI HỘI THOẠI · HỌC MÁY CỤC BỘ XẾP HẠNG · TÁI LẬP LỊCH TỰ ĐỘNG · BẢO TỒN VĂN HÓA SÀI GÒN</b>
</p>

**Mục tiêu cốt lõi:** Xây dựng nền tảng du lịch và trải nghiệm đô thị thông minh thế hệ mới tại TP. Hồ Chí Minh. Nền tảng giải quyết triệt để nghịch lý phổ biến của du lịch đô thị: **"Một địa điểm có trên bản đồ không đồng nghĩa với việc khách có thể tham gia trải nghiệm vào thời điểm mình đến"**.

Local Explorer AI chuyển đổi phương thức tiếp cận từ các chấm tròn tĩnh trên bản đồ sang **tối ưu hóa hành trình có khung giờ thực tế (Slot-aware)**, kết hợp giữa thuật toán tối ưu đa mục tiêu toán học và các mô hình Học máy (Machine Learning) cùng Trí tuệ nhân tạo (AI):

- **Khi tôi đến nơi, hoạt động trải nghiệm này có đang mở khung giờ cho khách tham gia hay không?**
- **Thứ tự di chuyển giữa các điểm thế nào để không bị kiệt sức vì kẹt xe và nắng nóng giờ cao điểm?**
- **Hoạt động nào đã có báo cáo chỗ trống còn lại, hoạt động nào cần liên hệ xác nhận trước?**
- **Làm sao để AI hiểu được mong muốn du lịch tự nhiên bằng tiếng Việt mà không cần điền form phức tạp?**
- **Khi một ca trải nghiệm bị hủy bất ngờ hoặc trời đổ mưa lớn, làm thế nào để tự động đổi lịch mà không hỏng cả ngày đi chơi?**
- **Làm sao các nghệ nhân, xưởng thủ công địa phương có thể chủ động quản lý số chỗ và đón khách theo kế hoạch?**

### 💡 Đột phá công nghệ cốt lõi hiện có:
- 🌆 **Digital Twin 3D WebGL Sài Gòn (Three.js)**: Bản sao số hóa 3D tương tác với hệ thống cao ốc ánh sáng neon, dòng sông Sài Gòn uốn lượn phản quang thời gian thực, camera xoay thị sai đa hướng theo chuột và các điểm ghim 3D phát xung radar.
- 💬 **Trợ Lý AI Concierge Đa Lượt (`/chat`)**: Trò chuyện bằng ngôn ngữ tự nhiên tiếng Việt, tự động bóc tách ràng buộc chuyến đi (thời gian, ngân sách, số người, sở thích) thông qua prompt `CONVERSATION_PARSER`, hiển thị Live Constraints Inspector và chuyển đổi 1-chạm sang lịch trình tối ưu.
- ⏱️ **Mô hình Dữ liệu 3 Cấp (POI → Experience → Slot)**: Định danh rõ ràng giữa địa điểm vật lý, hoạt động diễn ra tại điểm và khung giờ có sức chứa cụ thể.
- 🧮 **Heuristic Planner Không Ảo Tưởng (Hallucination-free)**: Lập lịch dựa trên thuật toán tối ưu hóa đa mục tiêu toán học xác định, loại trừ hoàn toàn rủi ro địa điểm "ảo" của các chatbot LLM tự do.
- 🤖 **Mô hình Học máy Cục bộ (Local XGBoost Ranker & E5 Semantic Search)**:
  - **XGBoost Ranker** (13 đặc trưng, đạt **NDCG@5 = 0.9516**) dùng để xếp hạng ưu tiên các hoạt động tối ưu nhất và phá vỡ thế cân bằng (tie-break).
  - **Multilingual E5 Embeddings** chạy trực tiếp trên CPU cục bộ, hỗ trợ tìm kiếm trải nghiệm theo ngữ nghĩa câu chữ (`/api/experience-search?semantic=true`) mà không lo rò rỉ dữ liệu ra bên ngoài.
- 🔄 **Tái Lập Lịch Trình Tự Động (Proactive Dynamic Replanning)**: Tự động phát hiện khi ca bị hủy (`SLOT_CANCELLED`) hoặc cảnh báo thời tiết xấu (`WEATHER_ALERT`), chạy bộ lọc solver tìm slot thay thế khả thi và dùng AI đề xuất phương án đổi lịch kèm giải thích minh bạch (XAI).
- 📜 **Lịch Sử Phiên Bản & So Sánh Đa Phương Án (`/compare`)**: Lưu vết từng phiên bản lịch trình (Itinerary Versioning) cho phép rollback; giao diện so sánh trực quan chênh lệch chi phí, thêm/bớt điểm dừng và thời gian hoàn thành.
- 🛡️ **Hệ Thống Phân Quyền Đa Tầng (RBAC) & Cổng Quản Lý Chuyên Biệt**:
  - **Traveler**: Lưu lịch sử chuyến đi, quản lý hồ sơ, chia sẻ lịch trình qua link bảo mật (`/shared/:token`), đánh giá trải nghiệm theo rubric chuẩn 5 sao.
  - **Provider Portal (`/provider-portal`)**: Quản lý chi tiết hoạt động, thêm/sửa slot với Optimistic Locking (`version`), trợ lý AI `PROVIDER_ASSISTANT` với cơ chế xác nhận 2 bước bằng token chữ ký số HMAC-SHA256.
  - **Admin Portal (`/admin`)**: Dashboard KPI thời gian thực, hàng đợi kiểm duyệt (Moderation Queue), công cụ phát hiện & hợp nhất POI trùng lặp (Fuzzy string similarity merge), quản lý người dùng và nhật ký kiểm toán (Audit Logs).
- 🌧️ **Mô hình Cảnh báo Nguy cơ Ngập lụt & Chỉ số Thời tiết/AQI**: Tích hợp mô hình phân tích rủi ro ngập lụt tại các tuyến đường TP. Hồ Chí Minh (`/api/ml/flood-risk`) và tự động điều chỉnh ưu tiên điểm dừng trong nhà khi mưa lớn hoặc AQI vượt ngưỡng an toàn.

---

## 📸 Hình ảnh Giao diện (Screenshots)

<table align="center">
<tr>
<td align="center" width="33%">
<img src="./assets/screenshots/home_3d.png" width="100%"/>
<b>3D WebGL Saigon Cityscape</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/explore.png" width="100%"/>
<b>Khám Phá & Thẻ 3D Tilt</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/planner.png" width="100%"/>
<b>Lập Lịch Trình & Xem Trước 3D</b>
</td>
</tr>
<tr>
<td align="center" width="33%">
<img src="./assets/screenshots/itinerary.png" width="100%"/>
<b>Dòng Thời Gian Laser 3D & KPI</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/map_3d.png" width="100%"/>
<b>Bản Đồ Vector 3D Radar Pins</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/provider.png" width="100%"/>
<b>Workspace Quản Lý Đối Tác</b>
</td>
</tr>
</table>

---

## 📑 Mục lục (Table of Contents)

- [Vì sao chọn Local Explorer AI](#-vì-sao-chọn-local-explorer-ai)
- [Căn chỉnh Tiêu chí Hội thi (Competition Alignment)](#-căn-chỉnh-tiêu-chí-hội-thi)
- [Đối tượng Sử dụng (User Groups)](#-đối-tượng-sử-dụng)
- [Mô hình Dữ liệu Cốt lõi (Data Model & ERD)](#-mô-hình-dữ-liệu-cốt-lõi-data-model--erd)
- [Tổng quan Tính năng Hoàn chỉnh (Feature Overview)](#-tổng-quan-tính-năng-hoàn-chỉnh-feature-overview)
- [Bộ 8 Quy trình Prompt AI & XAI Minh Bạch (PRD 3.0)](#-bộ-8-quy-trình-prompt-ai--xai-minh-bạch-prd-30)
- [Mô hình Học Máy Cục Bộ (Local Machine Learning Models)](#-mô-hình-học-máy-cục-bộ-local-machine-learning-models)
- [Thuật toán Lập Lịch Heuristic Planner](#-thuật-toán-lập-lịch-heuristic-planner)
- [Kiến trúc Hệ thống Toàn diện (System Architecture)](#-kiến-trúc-hệ-thống-toàn-diện-system-architecture)
- [Tech Stack](#-tech-stack)
- [Danh mục API Toàn diện (Complete API Reference)](#-danh-mục-api-toàn-diện-complete-api-reference)
- [Hướng dẫn Cài đặt & Khởi chạy (Getting Started)](#-hướng-dẫn-cài-đặt--khởi-chạy-getting-started)
- [Cấu hình Biến Môi Trường (.env)](#-cấu-hình-biến-môi-trường-env)
- [Kịch bản Kiểm thử & Demo Thực Tế (Demo Scenarios)](#-kịch-bản-kiểm-thử--demo-thực-tế-demo-scenarios)
- [Cấu Trúc Thư Mục Dự Án (Project Structure)](#-cấu-trúc-thư-mục-dự-án-project-structure)
- [Lộ trình Phát triển (Roadmap)](#-lộ-trình-phát-triển-roadmap)
- [Đóng góp & Giấy phép](#-đóng-góp--giấy-phép)

---

## 🧭 Vì sao chọn Local Explorer AI

| Hạn chế của Ứng dụng Bản đồ truyền thống | Giải pháp đột phá của Local Explorer AI |
|---|---|
| **Chỉ hiển thị địa điểm (POI) tĩnh** | Quản lý theo 3 cấp: Địa điểm → Hoạt động trải nghiệm → Khung giờ cụ thể (Slots) |
| **Không biết sức chứa và tình trạng chỗ** | Cập nhật trực tiếp số chỗ còn lại, đánh dấu rõ ràng chỗ cần gọi xác nhận (`tentative`) |
| **Lập lịch rời rạc, dễ kiệt sức vì kẹt xe** | Heuristic Engine tự động tính toán ma trận thời gian di chuyển thực tế theo phương tiện |
| **Chatbot AI hay bịa đặt địa điểm (Hallucination)** | Heuristic toán học xác định + XGBoost Ranker + Mô hình Prompt có schema Pydantic khóa cứng |
| **Người dùng phải tự tìm kiếm bằng form cứng nhắc** | Trợ lý AI Concierge trò chuyện tự nhiên, tự trích xuất thông số và sinh lịch trình 1-chạm |
| **Bất ngờ bị hủy ca hoặc mưa lớn là hỏng chuyến đi** | Dynamic Replanning tự động tìm hoạt động thay thế tương đương, cảnh báo thời tiết & ngập lụt |
| **Giao diện 2D phẳng, đơn điệu** | Canvas 3D WebGL Three.js sống động, thẻ 3D Tilt vệt sáng gương, bản đồ CartoDB đa chế độ |
| **Thiếu công cụ cho người làm văn hóa bản địa** | Provider Portal có Trợ lý AI quản lý ca, khóa xác nhận HMAC an toàn 2 bước |
| **Thiếu cơ chế kiểm soát chất lượng & chống trùng** | Admin Portal có Moderation Queue, kiểm toán Audit Log và Fuzzy String Duplicate POI Merge |

---

## 🏆 Căn chỉnh Tiêu chí Hội thi (Competition Alignment)

| Trọng tâm đánh giá | Triển khai thực tế trong Local Explorer AI | Giá trị thực tiễn mang lại |
|---|---|---|
| **Đô thị Thông minh (Smart City)** | Tối ưu hóa luồng di chuyển nội đô TP.HCM, tích hợp dự báo nguy cơ ngập lụt và thời tiết | Giảm áp lực giao thông giờ cao điểm, ứng phó triều cường và ngập nước đô thị |
| **Đổi mới Sáng tạo AI & ML** | Kết hợp Heuristic Planner + XGBoost Ranker (NDCG@5 0.9516) + E5 Semantic Search + 8 Prompt AI | Phản hồi dưới 50ms, không hallucination, khả năng suy luận ngữ nghĩa chuẩn xác |
| **Bảo tồn & Phát triển Văn hóa** | Ưu tiên trải nghiệm thủ công di sản (làm giấy Dó, gốm men Sài Gòn, cà phê vợt, ẩm thực Nam Bộ) | Kết nối thế hệ trẻ và du khách quốc tế với giá trị văn hóa bản địa bền vững |
| **Trải nghiệm Người dùng (UI/UX 3D)** | Canvas WebGL Three.js Sài Gòn, giao diện Nocturnal Emerald Glassmorphic, 3D Tilt Card | Tạo ấn tượng thị giác vượt trội, nâng tầm chuẩn mực ứng dụng du lịch Việt Nam |
| **Tính Khả thi & Minh bạch** | Explainable AI (XAI), Audit Trail, Offline Mock Fallback, cơ chế phân định dữ liệu mô phỏng | Ban giám khảo và người dùng có thể chạy thử nghiệm tức thì mà không lo lỗi hệ thống |

---

## 👥 Đối tượng Sử dụng (User Groups)

- 🎒 **Khách du lịch tự túc & Khách quốc tế (`traveler`)**: Cần lịch trình khám phá Sài Gòn có khung giờ chuẩn xác, có thể chat tự nhiên với AI Concierge, so sánh phương án và chia sẻ lịch trình cho bạn bè.
- 👨‍👩‍👧‍👦 **Gia đình & Nhóm bạn trẻ**: Cần hoạt động trải nghiệm vừa sức (workshop thủ công, ẩm thực), kiểm soát ngân sách chia đều theo đầu người, được cảnh báo khi trời mưa để ưu tiên điểm trong nhà.
- 🎨 **Những người yêu văn hóa & nghệ thuật**: Dễ dàng tìm kiếm trải nghiệm ngữ nghĩa qua mô hình vector E5, khám phá các xưởng gốm thủ công, làng nghề truyền thống.
- 🏪 **Nhà cung cấp trải nghiệm (`provider`)**: Sở hữu Provider Portal để cập nhật số lượng chỗ trống, mở/đóng ca trải nghiệm, sử dụng Trợ lý AI để điều phối ca làm việc an toàn.
- 🛡️ **Nhà quản trị đô thị & Vận hành nền tảng (`admin`)**: Sử dụng Admin Portal để duyệt nội dung, kiểm tra nguồn gốc minh chứng (Evidence), phát hiện và hợp nhất các địa điểm trùng lặp, theo dõi nhật ký kiểm toán.

---

## 💡 Mô hình Dữ liệu Cốt lõi (Data Model & ERD)

```text
User (RBAC) ──> Provider ──> POI (PostGIS POINT) ──> Experience ──> Slot (Optimistic Lock)
     │                                                     │               │
     └──> Itinerary ──> ItineraryStop <────────────────────┴───────────────┘
             │                │
             ├──> Version     └──> Event (SLOT_CANCELLED / WEATHER_ALERT) ──> Replan Advice
             ├──> Feedback (Rubric)
             └──> DecisionLog (XAI)
```

```mermaid
classDiagram
    class User {
        +String id
        +String email
        +String role (traveler|provider|admin)
        +String display_name
        +String phone
        +Boolean is_active
    }
    class Provider {
        +String id
        +String name
        +String slug
        +String verification_status
        +String portal_access_key
    }
    class POI {
        +String id
        +String name
        +String district
        +Float latitude
        +Float longitude
        +Geometry geom
        +String verification_status
    }
    class Experience {
        +String id
        +String title
        +List~String~ intent_tags
        +Boolean is_hands_on
        +Boolean is_indoor
        +Int duration_min
        +BigInt price_vnd
        +String verification_status
    }
    class ExperienceSlot {
        +String id
        +DateTime start_at
        +DateTime end_at
        +Int capacity_total
        +Int available_reported
        +String status (open|full|cancelled|tentative)
        +Int version
    }
    class Itinerary {
        +String id
        +String user_id
        +Date planned_date
        +DateTime start_time
        +DateTime return_deadline
        +Int group_size
        +BigInt budget_vnd
        +String travel_mode
        +Int current_version
        +String share_token
    }
    class ItineraryStop {
        +String id
        +Int stop_order
        +DateTime arrival_at
        +DateTime departure_at
        +Int wait_duration_min
        +BigInt cost_vnd
        +Boolean is_locked
    }
    class ItineraryVersion {
        +Int version_number
        +JSON stops_snapshot
        +BigInt total_cost_vnd
        +Int total_travel_time_s
    }
    class Event {
        +String event_type (SLOT_CANCELLED|WEATHER_ALERT)
        +String target_type
        +String target_id
        +String status
        +JSON metadata
    }
    class DecisionLog {
        +Int base_version
        +Int new_version
        +List~String~ preserved_intents
        +List~String~ lost_intents
        +String explanation_vi
        +List~String~ reason_codes
    }
    class Feedback {
        +Int rating (1-5)
        +String comment
        +Int relevance_grade (0-3)
        +String rubric_justification_vi
        +Boolean is_usable_for_training
    }

    User "1" --> "*" Itinerary : sở hữu
    Provider "1" --> "*" Experience : tổ chức
    POI "1" --> "*" Experience : diễn ra tại
    Experience "1" --> "*" ExperienceSlot : có các khung giờ
    Itinerary "1" --> "*" ItineraryStop : bao gồm
    Itinerary "1" --> "*" ItineraryVersion : lưu lịch sử
    Itinerary "1" --> "*" DecisionLog : giải trình XAI
    Itinerary "1" --> "*" Feedback : nhận đánh giá
    ExperienceSlot "1" --> "*" ItineraryStop : gắn với
    Event "1" --> "*" DecisionLog : kích hoạt tái lập lịch
```

---

## ⚡ Tổng quan Tính năng Hoàn chỉnh (Feature Overview)

### 1. Trợ Lý AI Concierge & Chatbot Du Lịch Sài Gòn (`/chat`)
- Giao diện trò chuyện trực quan, hỗ trợ gợi ý nhanh (Preset Prompts): *Ẩm thực & Cà phê vợt*, *Workshop gốm thủ công*, *Check-in di sản Quận 1*, *Tour đêm & Phố đi bộ*.
- Sử dụng prompt `CONVERSATION_PARSER` để trích xuất tự nhiên: Số người, khung giờ đi - về, ngân sách tối đa, sở thích và phương tiện di chuyển.
- **Thanh tra Ràng buộc Trực tiếp (Live Constraints Inspector)**: Thanh drawer hiển thị tức thì các tham số đã trích xuất kèm thanh tiến độ tỷ lệ sở thích.
- Chuyển tiếp 1-chạm (`Khởi tạo lịch trình ngay`) sang thuật toán lập lịch trình mà không cần nhập lại thông tin.

### 2. Canvas 3D WebGL Sài Gòn Tương Tác (Three.js Digital Twin)
- Dựng toàn cảnh không gian 3D trung tâm TP. Hồ Chí Minh với công nghệ Three.js.
- Các cao ốc đa giác ánh sáng, dòng sông Sài Gòn uốn lượn phản quang và các điểm ghim POI phát xung sóng radar nhấp nhô.
- Tương tác thị sai (Parallax) theo chuyển động con trỏ chuột, rê chuột hiển thị thẻ thông tin hoạt động trực tiếp.
- Chuyển đổi nhanh 2 chế độ: **Đêm Neon Cyber Glow** và **Ban Ngày Emerald Day**.

### 3. Bộ Lọc Đa Chiều & Tìm Kiếm Ngữ Nghĩa Vector E5 (`/explore`)
- **Tìm kiếm Ngữ nghĩa (`semantic=true`)**: Sử dụng mô hình vector Multilingual E5 chạy cục bộ trên CPU để xếp hạng trải nghiệm theo ngữ cảnh câu chữ.
- Tìm kiếm tức thì theo từ khóa, danh mục địa điểm, quận huyện.
- Lọc theo bán kính khoảng cách tính từ tâm trung tâm TP. Hồ Chí Minh (`max_distance_km`, `center_latitude`, `center_longitude`).
- Lọc theo tiêu chí trong nhà / ngoài trời, mức giá tối đa và số thành viên nhóm.

### 4. Thẻ Trải Nghiệm 3D Tilt Phản Chiếu Gương
- Các thẻ hoạt động được bọc trong component `TiltCard3D`, tạo cảm giác chạm nổi đa chiều (`perspective: 1000px`).
- Lớp phủ vệt sáng gương (*specular glare overlay*) chuyển động theo con trỏ chuột.
- Nhấp chọn thẻ tự động điều khiển bản đồ bay (*flyTo*) đến đúng vị trí tọa độ với hiệu ứng mượt mà.

### 5. Wizard Lập Lịch Trình 3 Bước & Thẻ Xem Trước Trực Tiếp (`/planner`)
- **Bước 1**: Đặt ngày khởi hành, khung giờ rảnh, điểm đón/trả (POI), số thành viên và hạn mức ngân sách.
- **Bước 2**: Lựa chọn phong cách và ưu tiên trải nghiệm (ẩm thực, thủ công mỹ nghệ, văn hóa, thư giãn), hỗ trợ ghim cố định trải nghiệm (`locked_experience_ids`).
- **Bước 3**: Chọn phương tiện di chuyển (xe máy, ô tô, đi bộ, xe buýt công cộng).
- **Thẻ xem trước 3D Live Day Preview**: Tự động tính toán tổng số giờ khám phá, chi phí bình quân và phương tiện ngay khi người dùng thay đổi thông số trên form.

### 6. Dòng Thời Gian Hành Trình 3D & Phân Tích KPI (`/itinerary/:id`)
- 4 thẻ KPI 3D phát sáng: Tổng thời lượng, Thời gian di chuyển, Chi phí ước tính, Số điểm dừng.
- Dòng thời gian với cột laser phát sáng kết nối các chặng dừng.
- Bản đồ vector CartoDB vẽ đường nối các chặng di chuyển kèm cự ly và thời gian ước tính.
- Thẻ giải thích AI minh bạch lý do lựa chọn (*Reason Codes*) kèm tính năng **In/Lưu PDF**.

### 7. Tái Lập Lịch Trình Tự Động (Proactive Dynamic Replanning)
- Lắng nghe các sự kiện hủy ca (`SLOT_CANCELLED`) từ đối tác hoặc cảnh báo thời tiết xấu (`WEATHER_ALERT`).
- Thuật toán solver lọc các ứng viên thay thế khả thi về thời gian, địa lý và ngân sách, sau đó dùng AI `REPLAN_ADVISOR` đề xuất phương án đổi chỗ tối ưu.
- Hộp thoại Replan Advice hiển thị các phương án thay thế kèm giải thích XAI bằng tiếng Việt.
- Khi người dùng xác nhận chấp nhận, lịch trình được cập nhật nguyên tử (Atomic Update) và tăng số hiệu phiên bản (`version`).

### 8. Lịch Sử Phiên Bản & So Sánh Lịch Trình Đa Phương Án (`/compare`)
- **Lịch sử phiên bản (Itinerary Versions)**: Lưu lại ảnh chụp toàn bộ các điểm dừng của từng phiên bản; hỗ trợ người dùng xem lại quá khứ hoặc rollback khi cần.
- **So sánh song song 2 lịch trình**: Hiển thị bảng so sánh chi tiết: chênh lệch chi phí (VND), danh sách điểm dừng được thêm/bớt, phát hiện sự thay đổi thứ tự di chuyển và chênh lệch thời gian kết thúc chuyến đi.

### 9. Chia Sẻ Lịch Trình Công Khai An Toàn (`/shared/:token`)
- Tạo liên kết chia sẻ bảo mật qua token ngẫu nhiên độ dài cao mà không làm lộ thông tin cá nhân của người dùng.
- Giao diện xem công khai thân thiện trên di động, hỗ trợ sao chép liên kết nhanh.
- Chủ sở hữu có thể thu hồi liên kết chia sẻ bất kỳ lúc nào để hủy quyền truy cập công khai.

### 10. Cổng Đối Tác Quản Lý Ca Trải Nghiệm (Provider Portal - `/provider-portal`)
- Xem danh sách các hoạt động do đối tác quản lý, thống kê số lượng ca và tình trạng sức chứa.
- Tạo mới và cập nhật khung giờ trải nghiệm với cơ chế **Optimistic Locking** (`expected_version` chống ghi đè đồng thời).
- Hiển thị số lượng lịch trình của du khách đang bị ảnh hưởng trực tiếp khi đối tác thay đổi hoặc hủy một ca.
- **Trợ lý AI Quản lý Ca (Provider Slot Assistant)**:
  - Cho phép đối tác gõ câu lệnh tự nhiên (ví dụ: *"Hôm nay xưởng nghỉ đột xuất ca chiều"*).
  - Bước 1: Xem trước hành động (`/slot-assistant/preview`), nhận mã token xác nhận có chữ ký số HMAC-SHA256 có hiệu lực 5 phút.
  - Bước 2: Xác nhận áp dụng (`/slot-assistant/confirm`), cập nhật cơ sở dữ liệu và tự động phát sinh sự kiện `SLOT_CANCELLED` để kích hoạt tái lập lịch cho du khách.

### 11. Cổng Quản Trị Hệ Thống (Admin Portal - `/admin`)
- **Bảng điều khiển KPI**: Tổng số người dùng, đối tác, địa điểm (POI), trải nghiệm chờ duyệt, minh chứng hết hạn và số ca chưa báo cáo sức chứa.
- **Hàng đợi kiểm duyệt (Moderation Queue)**: Xem xét, phê duyệt (`verified`), từ chối (`rejected`) hoặc ẩn (`hidden`) các POI, trải nghiệm và tài liệu minh chứng (Evidence).
- **Phát hiện & Hợp nhất POI Trùng lặp (Duplicate POI Detection & Merge)**:
  - Thuật toán chuẩn hóa tên tiếng Việt và tính toán độ tương đồng chuỗi mờ (Fuzzy string similarity ratio >= 0.88).
  - Tự động phát hiện các cặp POI nghi trùng lặp và cung cấp công cụ hợp nhất 1-chạm: chuyển toàn bộ Experience và ItineraryStop sang POI chính, đồng thời đánh dấu ẩn POI trùng lặp.
- **Quản lý tài khoản & phân quyền (RBAC)**: Kích hoạt/vô hiệu hóa tài khoản, gán quyền (`traveler`, `provider`, `admin`), ngăn chặn tình trạng tự khóa tài khoản quản trị.
- **Nhật ký kiểm toán toàn diện (Audit Log)**: Ghi vết đầy đủ mọi hành vi can thiệp hệ thống của quản trị viên và đối tác.

### 12. Xác Thực Người Dùng & Quản Lý Hồ Sơ
- Đăng ký và đăng nhập bằng Email/Mật khẩu với cơ chế băm mật khẩu an toàn.
- Đăng nhập một chạm bằng **Google OAuth 2.0 PKCE** với xác minh email chính chủ.
- Phiên đăng nhập được quản lý bằng **HTTP-only Cookie** (`le_session`), bảo vệ chống tấn công XSS và đánh cắp token.
- Phân quyền theo vai trò (`traveler`, `provider`, `admin`) bằng middleware backend và guard route frontend (`RoleRoute`).
- Trang hồ sơ cá nhân (`/profile`): Đổi tên hiển thị, số điện thoại, đổi mật khẩu và xem danh sách lịch trình đã lưu.

### 13. Khảo Sát Đánh Giá & Vòng Lặp Huấn Luyện AI (Feedback Loop)
- Sau khi hoàn thành chuyến đi, du khách có thể gửi đánh giá từ 1 đến 5 sao kèm nhận xét chi tiết.
- Hệ thống kích hoạt AI `FEEDBACK_LABELER` đánh giá chất lượng phản hồi theo rubric chuẩn (từ grade 0 đến 3, mức độ hoàn thành mục tiêu, lý giải bằng tiếng Việt) và gắn cờ `is_usable_for_training` để chuẩn bị dữ liệu huấn luyện ML.

---

## 🤖 Bộ 8 Quy Trình Prompt AI & XAI Minh Bạch (PRD 3.0)

Hệ thống quản lý tập trung toàn bộ prompt tại `apps/api/app/prompts/` với phiên bản hoạt động hiện tại là **`3.0.0`**. Toàn bộ kết quả đầu ra của mô hình ngôn ngữ lớn (LLM) đều được kiểm tra tính hợp lệ bằng schema Pydantic trước khi ghi vào cơ sở dữ liệu (Fail-closed mechanism):

| Tên Prompt | Đường dẫn API | Chức năng & Thực thi |
|---|---|---|
| `CONVERSATION_PARSER` | `POST /api/chat/message` | Trích xuất ràng buộc chuyến đi từ hội thoại tự nhiên thành cấu trúc `StructuredConstraints`. |
| `EXPERIENCE_TAGGER` | `POST /api/experiences/{id}/ai-tag` | Phân tích mô tả trải nghiệm để gán nhãn thực hành (`is_hands_on`), trong nhà (`is_indoor`), sở thích chính và mức độ nhạy cảm thời tiết. |
| `INTENT_SIMILARITY` | `POST /api/ai/intent-similarity` | Tính toán điểm tương đồng ngữ nghĩa và độ trùng lặp tag giữa 2 trải nghiệm để tìm hoạt động thay thế tương đương. |
| `REPLAN_ADVISOR` | `POST /api/itineraries/{id}/replan-advice` | Tiếp nhận các ứng viên đã qua sàng lọc khả thi của solver để đề xuất phương án thay thế tối ưu khi có sự cố. |
| `XAI_EXPLANATION` | Nằm trong luồng Replan Advice | Tạo lời giải thích minh bạch bằng tiếng Việt tự nhiên (`explanation_vi`) dựa trên sự thật toán học, lưu vào `decision_logs`. |
| `PROVIDER_ASSISTANT` | `/api/providers/{id}/slot-assistant/preview` | Hỗ trợ đối tác điều chỉnh hoặc hủy ca qua câu lệnh tự nhiên, sinh mã token xác nhận có chữ ký bảo mật 2 bước. |
| `FEEDBACK_LABELER` | `POST /api/itineraries/{id}/feedback/label` | Gán nhãn đánh giá của người dùng theo rubric chuẩn 4 cấp độ (grade 0-3) để làm giàu bộ dữ liệu huấn luyện ML. |
| `WEATHER_AQI_ADVISOR` | `POST /api/itineraries/{id}/weather-advisory` | Đánh giá tác động của lượng mưa (mm/h) và bụi mịn PM2.5 đến các điểm ngoài trời, tự động kích hoạt sự kiện cảnh báo `WEATHER_ALERT`. |

---

## 🧠 Mô Hình Học Máy Cục Bộ (Local Machine Learning Models)

Hệ thống triển khai 2 bài toán Học máy có giám sát (Supervised Learning) chạy hoàn toàn nội bộ trong hạ tầng ứng dụng:

```text
models/
├── ai-ranker/                       # Mô hình Xếp hạng Trải nghiệm (XGBoost)
│   ├── local_explorer_ranker.json   # Trọng số mô hình XGBRanker đã huấn luyện
│   ├── model_metadata.json          # Metadata phiên bản, NDCG metrics & feature schema
│   └── feature_schema.json          # Định nghĩa 13 đặc trưng đầu vào
├── flood-risk/                      # Mô hình Phân tích Rủi ro Ngập lụt Đô thị TP.HCM
│   ├── model.joblib                 # Mô hình phân loại ngập lụt
│   ├── preprocessor.joblib          # Tiền xử lý dữ liệu không gian
│   └── threshold.json               # Ngưỡng xác suất cảnh báo an toàn
└── e5/                              # Mô hình Vector Embedding Đa ngôn ngữ Multilingual E5
```

### 1. Mô hình Xếp hạng Trải nghiệm (Experience Ranker - XGBoost)
- **Kiến trúc:** `xgboost.XGBRanker` với hàm mục tiêu `rank:ndcg`.
- **Bộ 13 đặc trưng cốt lõi:**
  1. `tag_jaccard`: Độ trùng lặp Jaccard giữa sở thích người dùng và nhãn trải nghiệm.
  2. `intent_match`: Điểm khớp mục đích chính của chuyến đi.
  3. `is_hands_on`: Hoạt động có tính chất thực hành/workshop thủ công.
  4. `is_indoor`: Hoạt động diễn ra trong không gian kín (an toàn khi mưa/nắng).
  5. `duration_ratio`: Tỷ lệ thời lượng trải nghiệm so với quỹ thời gian khả dụng.
  6. `eta_ratio`: Tỷ lệ thời gian di chuyển so với thời lượng hoạt động.
  7. `total_time_ratio`: Tỷ lệ chiếm dụng tổng thời gian chuyến đi.
  8. `group_cost_ratio`: Tỷ lệ chi phí so với ngân sách của nhóm.
  9. `rain_mm`: Lượng mưa dự báo tại thời điểm trải nghiệm.
  10. `outdoor_rain_mm`: Lượng mưa tác động trực tiếp lên hoạt động ngoài trời.
  11. `temperature_c`: Nhiệt độ môi trường đô thị (°C).
  12. `pm2_5`: Nồng độ bụi mịn PM2.5 (µg/m³).
  13. `european_aqi`: Chỉ số chất lượng không khí châu Âu.
- **Chỉ số kiểm thử:** Đạt **NDCG@5 = 0.9516**, **NDCG@2 = 0.9031**, **Recall@5 = 1.0**.
- **Vai trò trong hệ thống:** Đóng vai trò bộ phân loại tinh chỉnh (Tie-breaker) trong Heuristic Planner và xếp hạng các ứng viên thay thế trong Dynamic Replanning (`/api/ml/rank-experiences`).

### 2. Mô hình Rủi ro Ngập lụt Đô thị Sài Gòn (Saigon Flood Risk Classifier)
- Tích hợp dữ liệu lịch sử ngập lụt TP. Hồ Chí Minh giai đoạn 2002–2026 từ 53 nguồn báo cáo chính thống kết hợp chỉ số triều cường và lượng mưa.
- Trả về xác suất rủi ro ngập lụt cho các cung đường di chuyển (`/api/ml/flood-risk`).
- Nguyên tắc an toàn: Không bao giờ giả định một tuyến đường không ngập nếu chưa có dữ liệu quan trắc đầy đủ (`unknown ≠ no-flood`).

---

## 🧮 Thuật toán Lập Lịch Heuristic Planner

Khác với các chatbot LLM tự do có thể tạo ra các địa điểm không tồn tại hoặc tính sai thời gian đi lại, Local Explorer AI sử dụng thuật toán **Heuristic Deterministic** 3 bước:

```text
Input:
  - Thời gian rảnh: [T_start, T_end]
  - Ngân sách: Budget_VND, Số người: Group_Size
  - Trọng số mục đích: Intent_Weights (thủ công, ẩm thực, văn hóa, thư giãn)
  - Phương tiện: Transport_Mode (xe máy, ô tô, đi bộ, xe buýt)
  - Điểm xuất phát/đích về và danh sách địa điểm ghim cố định (Locked)
          │
          ▼
Bước 1: Lọc Không gian Khả thi (Feasibility Pruning)
  - Loại bỏ các trải nghiệm có chi phí vượt quá ngân sách bình quân
  - Loại bỏ các ca (slot) nằm ngoài khoảng [T_start, T_end] hoặc đã hết chỗ
  - Ưu tiên giữ lại các địa điểm được người dùng ghim cố định (is_locked = True)
          │
          ▼
Bước 2: Chấm điểm Đa Mục tiêu & ML Tie-Breaking
  - Tính điểm Heuristic cơ sở: Score = w1 * Intent_Match + w2 * Slot_Freshness + w3 * Cost_Efficiency
  - Khi có nhiều ứng viên đồng điểm tại cùng mốc thời gian: Kích hoạt XGBoost Ranker (13 features)
          │
          ▼
Bước 3: Tối ưu hóa Chuỗi Hành trình (Sequential Routing Optimization)
  - Lấy quãng đường, ETA và hình học tuyến từ Goong Directions API; geocode địa chỉ nhập thành điểm đi/đến
  - ETA có nguồn, thời điểm tính và hạn cache; không quảng cáo là giao thông thời gian thực
  - Kiểm tra giờ về bao gồm cả chặng cuối đến địa chỉ đích
          │
          ▼
Output:
  - Danh sách ItineraryStops có thứ tự thời gian chuẩn xác
  - Feasibility Status: 'feasible' (đầy đủ) hoặc 'tentative' (cần gọi xác nhận)
  - Lý do đề xuất (Reason Codes), Explanation XAI và thống kê di chuyển tổng thể
```

---

## 🏗️ Kiến trúc Hệ thống Toàn diện (System Architecture)

```mermaid
flowchart TB
    subgraph Client["Presentation Layer (Client SPA - React 18 + Vite 6)"]
        ThreeCanvas["Three.js 3D WebGL Saigon Cityscape"]
        ChatConcierge["AI Concierge Chat Interface (/chat)"]
        PlannerWizard["Smart Trip Planner Wizard (/planner)"]
        LaserTimeline["Laser Timeline & KPI Analytics (/itinerary)"]
        CompareView["Side-by-side Trip Compare (/compare)"]
        ProviderPortalUI["Provider Management Portal (/provider-portal)"]
        AdminPortalUI["Admin Governance Portal (/admin)"]
        MapAdapter["Leaflet + CartoDB Map Adapter"]
        MockEngine["Offline Heuristic Engine Fallback"]
    end

    subgraph Gateway["Application Layer (FastAPI Backend - Python 3.12)"]
        AuthMiddleware["RBAC Auth & Session Cookie / Google OAuth PKCE"]
        API["FastAPI REST Endpoints"]
        CatalogService["Catalog & Experience Service"]
        PromptEngine["PromptRunner (PRD 3.0 Manifest v3_0_0)"]
        HeuristicSolver["Deterministic Heuristic Planner Solver"]
        ReplanningEngine["Dynamic Replanning Service"]
        E5SearchEngine["Local Multilingual E5 Embeddings Service"]
        MLRankerEngine["XGBoost ML Ranker Service"]
        FloodRiskEngine["Saigon Flood Risk Model Service"]
        RoutingEngine["Goong Directions + Geocoding adapters"]
        MockRoutingEngine["Mock routing (tests/demo only)"]
    end

    subgraph Persistence["Storage & Intelligence Layer"]
        PostGIS[("PostgreSQL 16 + PostGIS 3.4")]
        RedisCache[("Redis Cache")]
        LocalModels[("Local Model Artifacts: XGBoost & E5 & Flood")]
        PromptCatalog[("Versioned JSON Prompts")]
    end

    Client --> AuthMiddleware
    AuthMiddleware --> API
    API --> CatalogService
    API --> HeuristicSolver
    API --> PromptEngine
    API --> ReplanningEngine
    API --> MLRankerEngine
    API --> FloodRiskEngine

    CatalogService --> E5SearchEngine
    HeuristicSolver --> MLRankerEngine
    HeuristicSolver --> RoutingEngine
    RoutingEngine -. selected mock config .-> MockRoutingEngine
    ReplanningEngine --> PromptEngine
    ReplanningEngine --> MLRankerEngine

    CatalogService --> PostGIS
    HeuristicSolver --> PostGIS
    ReplanningEngine --> PostGIS
    PromptEngine --> PromptCatalog
    E5SearchEngine --> LocalModels
    MLRankerEngine --> LocalModels
    FloodRiskEngine --> LocalModels
    API -. Tùy chọn .-> RedisCache
```

---

## 💻 Tech Stack

| Tầng công nghệ | Công nghệ sử dụng | Vai trò & Mục đích triển khai |
|---|---|---|
| **Frontend SPA** | React 18.3, TypeScript 5.6, Vite 6.0 | Nền tảng ứng dụng đơn trang tốc độ cao, type-safe toàn diện |
| **Đồ họa 3D WebGL** | Three.js (@types/three) | Dựng mô hình 3D Digital Twin Sài Gòn, camera thị sai, hiệu ứng neon |
| **Giao diện & Styling** | Vanilla CSS, Tailwind CSS, Lucide Icons | Thiết kế Nocturnal Emerald Glassmorphic, thẻ 3D Tilt phản chiếu gương |
| **Bản đồ Địa lý** | Leaflet, React-Leaflet, CartoDB Tiles | Bản đồ vector CartoDB Voyager (Sáng) & Dark Matter (Đêm), radar pins |
| **Backend API** | Python 3.12, FastAPI 0.115, Pydantic v2 | Xây dựng RESTful API hiệu năng cao, xác thực dữ liệu chặt chẽ |
| **Cơ sở dữ liệu** | PostgreSQL 16, PostGIS 3.4, SQLAlchemy 2.0 | Lưu trữ thực thể địa lý, truy vấn không gian `geography(POINT)` |
| **Database Migration** | Alembic | Quản lý phiên bản lược đồ cơ sở dữ liệu (`0001` -> `0003_prompt_workflows`) |
| **Học máy Cục bộ (ML)** | XGBoost 2.1, Scikit-learn 1.5, NumPy, Pandas | Mô hình xếp hạng trải nghiệm NDCG@5 = 0.9516 và mô hình rủi ro ngập lụt |
| **Tìm kiếm Ngữ nghĩa** | Sentence-Transformers, Multilingual E5 | Tìm kiếm trải nghiệm theo ngữ nghĩa vector chạy cục bộ trên CPU |
| **Bảo mật & Xác thực** | HTTP-only Cookies, Google OAuth 2.0 PKCE, HMAC-SHA256 | Phân quyền RBAC (Traveler, Provider, Admin), ký token xác nhận 2 bước |
| **Container & CI/CD** | Docker Compose v2, GitHub Actions | Đóng gói môi trường đồng nhất và tự động kiểm thử lint/pytest |

---

## 📡 Danh mục API Toàn diện (Complete API Reference)

Toàn bộ API được tài liệu hóa tự động tại Swagger UI: `http://localhost:8000/docs`.

### 1. Hệ thống & Giám sát (Health & System)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `GET` | `/health` | Kiểm tra trạng thái hoạt động của hệ thống backend |
| `GET` | `/` | Thông tin cơ bản về API và chế độ dữ liệu (`data_mode: simulated`) |

### 2. Xác thực & Tài khoản (Authentication & RBAC)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `POST` | `/api/auth/register` | Đăng ký tài khoản du khách mới (`traveler`), cấp session cookie |
| `POST` | `/api/auth/login` | Đăng nhập tài khoản bằng email & mật khẩu |
| `POST` | `/api/auth/logout` | Đăng xuất và xóa session cookie |
| `GET` | `/api/auth/me` | Lấy thông tin hồ sơ người dùng đang đăng nhập |
| `PATCH` | `/api/auth/me` | Cập nhật tên hiển thị và số điện thoại |
| `POST` | `/api/auth/password` | Đổi mật khẩu tài khoản |
| `GET` | `/api/auth/google/start` | Khởi động quy trình đăng nhập Google OAuth 2.0 với PKCE |
| `GET` | `/api/auth/google/callback`| Tiếp nhận mã ủy quyền Google và thiết lập phiên đăng nhập |

### 3. Danh mục Địa điểm & Tìm kiếm Ngữ nghĩa (Catalog & Search)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `GET` | `/api/pois` | Danh sách điểm quan tâm trên bản đồ (POI) kèm tọa độ và quận |
| `GET` | `/api/pois/{id}` | Chi tiết thông tin và tọa độ địa lý của POI |
| `GET` | `/api/experiences` | Lọc trải nghiệm theo `intent`, thời gian, ngân sách, số người, bán kính |
| `GET` | `/api/experiences/{id}` | Chi tiết thông tin trải nghiệm và nhà cung cấp |
| `GET` | `/api/experiences/{id}/slots` | Danh sách khung giờ mở cửa kèm số chỗ còn lại |
| `GET` | `/api/experience-search` | Tìm kiếm trải nghiệm: hỗ trợ tìm theo từ khóa hoặc **ngữ nghĩa E5 vector** (`semantic=true`) |

### 4. Lập Lịch trình & Quản lý Hành trình (Planner & Itinerary)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `POST` | `/api/itineraries/plan` | Tạo lịch trình tối ưu bằng Heuristic Engine kết hợp ML Ranker |
| `GET` | `/api/itineraries/{id}` | Truy xuất thông tin lịch trình đã lưu |
| `GET` | `/api/me/itineraries` | Danh sách lịch trình cá nhân của du khách đang đăng nhập |
| `GET` | `/api/itineraries/{id}/versions` | Xem lịch sử các phiên bản chụp của lịch trình |
| `GET` | `/api/itinerary-comparisons` | So sánh chi tiết chênh lệch giữa 2 lịch trình (`first_id`, `second_id`) |
| `POST` | `/api/itineraries/{id}/share` | Tạo liên kết chia sẻ công khai qua token an toàn |
| `DELETE`| `/api/itineraries/{id}/share` | Thu hồi quyền truy cập liên kết chia sẻ công khai |
| `GET` | `/api/shared/itineraries/{token}` | Xem lịch trình công khai từ liên kết chia sẻ |
| `POST` | `/api/itineraries/{id}/feedback` | Du khách gửi nhận xét và chấm điểm chuyến đi (1-5 sao) |
| `GET` | `/api/itineraries/{id}/feedback` | Xem danh sách đánh giá của lịch trình |
| `GET` | `/api/notifications` | Lấy danh sách cảnh báo ca trải nghiệm bị hủy cho du khách |

### 5. Trợ lý AI Concierge & Quy trình Prompt (AI Workflows)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `POST` | `/api/chat/message` | Trò chuyện với Trợ lý AI Concierge, tự động trích xuất ràng buộc chuyến đi |
| `GET` | `/api/ai/prompts` | Xem danh mục manifest và danh sách các prompt AI đang hoạt động |
| `POST` | `/api/itineraries/{id}/replan-advice` | Đề xuất giải pháp đổi lịch khi ca bị hủy hoặc thời tiết xấu |
| `POST` | `/api/itineraries/{id}/replan-advice/accept`| Chấp nhận phương án đổi lịch và nâng cấp phiên bản lịch trình |
| `POST` | `/api/experiences/{id}/ai-tag` | Chạy AI tự động phân tích và gán nhãn thuộc tính cho trải nghiệm |
| `POST` | `/api/ai/intent-similarity` | Tính toán điểm tương đồng ngữ nghĩa giữa 2 trải nghiệm |
| `POST` | `/api/itineraries/{id}/feedback/label` | Đánh giá nhận xét của khách theo rubric 4 cấp độ để phục vụ huấn luyện ML |
| `POST` | `/api/itineraries/{id}/weather-advisory` | Đánh giá tác động thời tiết/AQI lên các điểm dừng ngoài trời |

### 6. Mô hình Học máy Cục bộ (Local Machine Learning)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `GET` | `/api/ml/status` | Kiểm tra trạng thái nạp và phiên bản của XGBoost Ranker & Flood Model |
| `POST` | `/api/ml/rank-experiences` | Xếp hạng các ứng viên trải nghiệm bằng mô hình XGBRanker (13 đặc trưng) |
| `POST` | `/api/ml/flood-risk` | Dự đoán xác suất rủi ro ngập lụt tại các cung đường đô thị TP.HCM |

### 7. Cổng Đối Tác (Provider Portal)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `GET` | `/api/provider/me` | Lấy thông tin hồ sơ đối tác |
| `GET` | `/api/provider/experiences` | Danh sách hoạt động và các khung giờ do đối tác quản lý |
| `POST` | `/api/provider/experiences` | Đăng ký bản nháp hoạt động trải nghiệm mới |
| `PATCH` | `/api/provider/experiences/{id}` | Cập nhật thông tin hoạt động (đưa về hàng đợi duyệt) |
| `DELETE`| `/api/provider/experiences/{id}` | Tạm ẩn hoạt động trải nghiệm |
| `POST` | `/api/provider/experiences/{id}/slots` | Mở thêm khung giờ trải nghiệm mới |
| `PATCH` | `/api/provider/slots/{id}` | Cập nhật sức chứa, đóng/hủy ca (Optimistic Locking) |
| `POST` | `/api/providers/{id}/slot-assistant/preview` | Trợ lý AI xem trước thao tác quản lý ca, sinh token ký HMAC |
| `POST` | `/api/providers/{id}/slot-assistant/confirm` | Xác nhận thực hiện thao tác quản lý ca từ token chữ ký số |
| `GET` | `/api/provider/audit` | Xem nhật ký kiểm toán các thao tác của đối tác |

### 8. Cổng Quản Trị Hệ Thống (Admin Portal)
| Phương thức | Đường dẫn | Chức năng |
|:---:|---|---|
| `GET` | `/api/admin/dashboard` | Thống kê số lượng người dùng, đối tác, POI và hàng đợi kiểm duyệt |
| `GET` | `/api/admin/users` | Danh sách người dùng trong hệ thống |
| `PATCH` | `/api/admin/users/{id}` | Thay đổi vai trò người dùng (`role`), kích hoạt/khóa tài khoản |
| `POST` | `/api/admin/providers` | Tạo hồ sơ và tài khoản đối tác mới |
| `GET` | `/api/admin/providers` | Danh sách các đơn vị đối tác |
| `GET` | `/api/admin/moderation` | Hàng đợi kiểm duyệt POI, Experience và tài liệu minh chứng (Evidence) |
| `PATCH` | `/api/admin/moderation/{type}/{id}` | Phê duyệt (`verified`), từ chối (`rejected`) hoặc ẩn (`hidden`) thực thể |
| `GET` | `/api/admin/duplicates/pois` | Quét và phát hiện các cặp POI nghi ngờ trùng lặp tên/tọa độ |
| `POST` | `/api/admin/duplicates/pois/merge` | Hợp nhất 2 POI trùng lặp, liên kết lại toàn bộ trải nghiệm và điểm dừng |
| `GET` | `/api/admin/audit` | Xem nhật ký kiểm toán hệ thống toàn diện |

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy (Getting Started)

### Cách 1: Khởi chạy 1-chạm với Docker Compose (Khuyên dùng)

Yêu cầu: Đã cài đặt **Docker Desktop** (Compose v2).

```bash
# 1. Clone repository
git clone https://github.com/NguyenTriBaoThang/LoaclExplorerAI.git
cd LoaclExplorerAI

# 2. Tạo file cấu hình môi trường
cp .env.example .env

# 2a. Mở .env và đặt GOONG_API_KEY để bật routing/geocoding thật

# 3. Khởi chạy toàn bộ hệ thống (Frontend + Backend + DB PostGIS + Redis)
docker compose up --build
```

Sau khi hoàn tất, mở trình duyệt:
- 🌐 **Giao diện Web 3D**: [http://localhost:5173](http://localhost:5173)
- 💬 **Trợ lý AI Concierge**: [http://localhost:5173/chat](http://localhost:5173/chat)
- 📖 **Tài liệu Swagger API**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🩺 **Kiểm tra Health**: [http://localhost:8000/health](http://localhost:8000/health)

Để dừng hệ thống:
```bash
docker compose down
```

---

### Cách 2: Khởi chạy thủ công trong môi trường phát triển (Local Dev)

#### Bước 1: Khởi động Cơ sở dữ liệu PostGIS & Redis
```bash
docker compose up -d db redis
```

#### Bước 2: Khởi động Backend (FastAPI + Python 3.12)
```bash
cd apps/api

# Tạo và kích hoạt môi trường ảo (Windows PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Cài đặt thư viện cốt lõi:
pip install -r requirements.txt

# (Tùy chọn) Cài đặt thư viện Học máy và Tìm kiếm Ngữ nghĩa:
pip install -r requirements-ml.txt
pip install -r requirements-e5.txt

# Thiết lập chuỗi kết nối và chạy Migration:
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/local_explorer"
alembic upgrade head

# Nạp dữ liệu mô phỏng demo:
python -m scripts.seed_db

# Khởi chạy server FastAPI tại cổng 8000:
uvicorn app.main:app --reload --port 8000
```

#### Bước 3: Khởi động Frontend (React 18 + Three.js + Vite)
```bash
cd apps/web

# Cài đặt dependencies:
npm install

# Khởi chạy Vite dev server:
npm run dev
```
*Frontend chạy tại cổng `http://localhost:5173`.*

---

## ⚙️ Cấu hình Biến Môi Trường (.env)

Tạo file `.env` tại thư mục gốc từ mẫu `.env.example`:

| Biến môi trường | Giá trị mặc định | Giải thích |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/local_explorer` | Chuỗi kết nối PostGIS |
| `AUTH_SECRET` | *(chuỗi ngẫu nhiên >= 32 ký tự)* | Khóa bí mật ký mã hóa session cookie |
| `APP_SIGNING_SECRET` | *(chuỗi ngẫu nhiên)* | Khóa ký token xác nhận 2 bước cho Provider AI |
| `ADMIN_API_KEY` | *(tùy chọn)* | Khóa bảo mật gọi các endpoint AI quản trị viên |
| `OPENAI_API_KEY` | *(tùy chọn)* | API key cho các prompt LLM (Hỗ trợ OpenAI hoặc các endpoint tương thích) |
| `ROUTING_PROVIDER` | `goong` | Nhà cung cấp tuyến đường; `mock` chỉ dùng cho demo/kiểm thử |
| `GEOCODING_PROVIDER` | `goong` | Nhà cung cấp geocoding địa chỉ |
| `GOONG_API_KEY` | *(bắt buộc để dùng Goong)* | Key chỉ được API server gửi đến Directions/Geocoding, không đặt trong frontend |
| `GOONG_ETA_TTL_SECONDS` | `300` | Thời hạn cache ETA trong tiến trình API; không phải tuổi dữ liệu giao thông |
| `GEOCODE_CACHE_TTL_SECONDS` | `86400` | Thời hạn cache kết quả geocoding |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | URL endpoint của nhà cung cấp LLM |
| `INSTALL_ML` | `true` | Bật tính năng nạp mô hình XGBoost Ranker & Flood Risk |
| `INSTALL_E5` | `true` | Bật tính năng tìm kiếm ngữ nghĩa cục bộ Multilingual E5 |
| `GOOGLE_CLIENT_ID` | *(tùy chọn)* | Client ID đăng nhập Google OAuth 2.0 PKCE |
| `GOOGLE_CLIENT_SECRET` | *(tùy chọn)* | Client Secret đăng nhập Google |

Planner yêu cầu chọn cả điểm xuất phát và điểm về để xét trọn chặng đi-về. Goong hỗ trợ xe máy, đi bộ và ô tô trong cấu hình hiện tại; transit/xe đạp không được quy đổi sang loại phương tiện khác. Tài liệu Directions V2 mô tả capability và bảng giá trị `vehicle` chưa hoàn toàn đồng nhất, vì vậy cần smoke-test với key/tài khoản Goong thật trước pilot. Thiếu key hoặc Goong lỗi thì API báo lỗi rõ ràng, không tự thay bằng ETA giả.

---

## 🎯 Kịch bản Kiểm thử & Demo Thực Tế (Demo Scenarios)

### Kịch bản 1: Trò chuyện tự nhiên với Trợ lý AI Concierge (`/chat`)
1. Truy cập `/chat`, chọn gợi ý nhanh *"Ẩm thực & Cà phê vợt"*.
2. Nhập: *"Nhóm mình 2 người, muốn khám phá ẩm thực hẻm xưa và cà phê vợt Sài Gòn, đi từ 08:30 đến 16:30, tổng ngân sách 800.000₫ bằng xe máy."*
3. Quan sát **Live Constraints Inspector** tự động bóc tách số người (2), ngân sách (800.000₫), giờ đi (08:30), giờ về (16:30), phương tiện (xe máy) và tỷ lệ sở thích ẩm thực.
4. Bấm *"Khởi tạo lịch trình ngay"* để nhận lịch trình tối ưu có khung giờ thực tế trong chưa đầy 50ms.

### Kịch bản 2: Lập lịch truyền thống & Thẻ Xem Trước 3D Live Day Preview (`/planner`)
1. Truy cập `/planner`. Chọn khoảng thời gian 09:00 - 16:00, ngân sách 1.000.000₫, 2 người.
2. Đánh dấu chọn sở thích *Thủ công mỹ nghệ* và *Ẩm thực Nam Bộ*.
3. Quan sát Thẻ Xem Trước 3D bên phải tự động tính toán tổng số giờ, chi phí bình quân mỗi người và phương tiện đề xuất.
4. Bấm *"Tạo Lịch Trình Ngay"* để điều hướng sang trang kết quả `/itinerary/:id`.

### Kịch bản 3: Tái lập lịch trình tự động (Proactive Dynamic Replanning)
1. Khi một ca trong hành trình bị hủy hoặc có cảnh báo thời tiết xấu, hệ thống phát sinh sự kiện `Event`.
2. Truy cập lịch trình, giao diện tự động hiển thị thanh thông báo cảnh báo và nút *"Yêu cầu đề xuất đổi lịch"*.
3. Hộp thoại Replan Advice mở ra, phân tích slot thay thế khả thi và hiển thị lời giải thích XAI bằng tiếng Việt.
4. Bấm *"Chấp nhận phương án"*, lịch trình được cập nhật tức thì, phiên bản được nâng lên v2 và lưu ảnh chụp phiên bản cũ để xem lại hoặc rollback.

### Kịch bản 4: Đối tác quản lý ca với Trợ lý AI (Provider Slot Assistant)
1. Đăng nhập với tài khoản đối tác (`provider`), truy cập `/provider-portal`.
2. Nhập vào ô trợ lý: *"Hôm nay xưởng nghỉ đột xuất các ca chiều do bảo trì bàn xoay gốm"*.
3. Hệ thống trả về bản xem trước thao tác (`CANCEL_SLOT`) kèm mã token xác nhận có chữ ký bảo mật hiệu lực 5 phút.
4. Đối tác bấm xác nhận, ca được chuyển sang trạng thái `cancelled`, đồng thời hệ thống báo số lượng lịch trình du khách bị ảnh hưởng.

### Kịch bản 5: Quản trị viên duyệt kiểm duyệt & Hợp nhất POI trùng lặp (`/admin`)
1. Đăng nhập với tài khoản quản trị (`admin`), truy cập `/admin`.
2. Kiểm tra hàng đợi kiểm duyệt: Phê duyệt một trải nghiệm mới đăng ký.
3. Chuyển sang tab *Phát hiện POI trùng lặp*: Hệ thống hiển thị cặp POI nghi trùng nhau dựa trên độ tương đồng chuỗi mờ (Fuzzy string similarity).
4. Bấm *"Hợp nhất"*: Toàn bộ hoạt động và điểm dừng được chuyển sang POI chính an toàn, POI phụ được chuyển sang trạng thái ẩn (`hidden`), lưu nhật ký kiểm toán `AuditLog`.

---

## 📁 Cấu Trúc Thư Mục Dự Án (Project Structure)

```text
LoaclExplorerAI/
├── .github/
│   ├── workflows/               # CI/CD Workflows (ci.yml, release.yml)
│   ├── ISSUE_TEMPLATE/          # Mẫu tạo issue báo lỗi và đề xuất tính năng
│   └── PULL_REQUEST_TEMPLATE.md # Mẫu gửi Pull Request chuẩn
├── apps/
│   ├── api/                     # Backend FastAPI, SQLAlchemy, PostGIS & ML
│   │   ├── app/
│   │   │   ├── adapters/        # LLM Provider Adapters (OpenAI JSON-mode)
│   │   │   ├── api/routes/      # API Endpoints (admin, ai, auth, catalog, chat, ml, planner, provider)
│   │   │   ├── core/            # Config, Enums & Security
│   │   │   ├── db/              # Database Engine & Session Management
│   │   │   ├── models/          # SQLAlchemy Entities (User, POI, Slot, Itinerary, Audit...)
│   │   │   ├── prompts/         # Versioned Prompt Catalog v3_0_0 (manifest.json)
│   │   │   ├── repositories/    # Data Access Layer
│   │   │   ├── schemas/         # Pydantic Schemas (AI, Auth, Management, ML, Planner)
│   │   │   └── services/        # Business Logic (Planner, Replan, ML Ranker, Flood, E5...)
│   │   ├── migrations/          # Alembic Migrations
│   │   ├── scripts/             # Script nạp dữ liệu demo (seed_db.py)
│   │   └── tests/               # Bộ test tự động với pytest
│   └── web/                     # Frontend React 18 + TypeScript + Three.js + Leaflet
│       ├── src/
│       │   ├── api/             # API Client tích hợp Offline Mock Engine Fallback
│       │   ├── auth.tsx         # Auth Context & RBAC Protected Route (RoleRoute)
│       │   ├── components/3d/   # Canvas 3D City WebGL & Thẻ 3D TiltCard
│       │   ├── components/map/  # MapAdapter với CartoDB Voyager / Dark Matter
│       │   ├── layouts/         # AppLayout kính mờ và Navigation Bar nổi
│       │   └── pages/           # Home, Chat, Explore, Planner, Itinerary, Compare, Portals...
├── assets/                      # Hình ảnh đồ họa, banner, logo, screenshots
├── data/                        # Dữ liệu mô phỏng và báo cáo ngập lụt lịch sử TP.HCM
├── docs/                        # Tài liệu kỹ thuật chi tiết (API, Architecture, Prompts, ML)
├── models/                      # Thư mục chứa Artifacts mô hình (XGBoost, E5, Flood Risk)
├── notebooks/                   # Jupyter Notebooks huấn luyện Ranker & Flood Model trên Colab
├── docker-compose.yml           # Cấu hình cụm container chính
├── docker-compose.override.yml  # Cấu hình phát triển cục bộ
├── docker-compose.prod.yml      # Cấu hình triển khai production
├── ARCHITECTURE.md              # Đặc tả kiến trúc kỹ thuật chi tiết
├── DEMO_SCRIPT.md               # Kịch bản thuyết trình demo 5-7 phút
├── COMPETITION_SUBMISSION.md    # Tài liệu nộp bài hội thi hoàn chỉnh
├── CONTRIBUTING.md              # Quy chuẩn đóng góp mã nguồn
├── SECURITY.md                  # Chính sách bảo mật & báo cáo lỗ hổng
└── README.md                    # Tài liệu chính của dự án
```

---

## 🗺️ Lộ trình Phát triển (Roadmap)

- [x] **Phase 0**: Khởi tạo kiến trúc nền tảng, thiết kế cơ sở dữ liệu PostGIS và dữ liệu mô phỏng.
- [x] **Phase 1**: Giao diện Khám phá trải nghiệm, bộ lọc tìm kiếm và bản đồ số Leaflet.
- [x] **Phase 2**: Thuật toán Heuristic Planner tối ưu hóa đa mục tiêu và dòng thời gian Itinerary.
- [x] **Phase 2.5**: Nâng cấp đồ họa **3D WebGL (Three.js)** Sài Gòn, thẻ 3D Tilt phản chiếu gương, bản đồ CartoDB đa chế độ và cơ chế Offline Mock Engine.
- [x] **Phase 3**: Tìm kiếm ngữ nghĩa đa ngôn ngữ cục bộ bằng **Multilingual E5 Embeddings** (`semantic=true`).
- [x] **Phase 4**: Tái lập lịch trình tự động khi có sự cố hủy ca/thời tiết (**Proactive Dynamic Replanning**) & Quản lý phiên bản lịch trình (Versioning & Rollback).
- [x] **Phase 5**: Cổng thông tin đối tác (**Provider Portal**) & Trợ lý AI quản lý ca có token chữ ký bảo mật 2 bước HMAC-SHA256.
- [x] **Phase 6**: Tích hợp thuật toán Học máy **XGBoost Ranker** (13 đặc trưng, NDCG@5 = 0.9516) phục vụ xếp hạng và giải quyết hòa điểm (tie-break).
- [x] **Phase 7**: Tích hợp mô hình dự báo **Rủi ro Ngập lụt Đô thị TP.HCM** và tư vấn điều chỉnh điểm ngoài trời khi mưa lớn/AQI cao.
- [x] **Phase 8**: Cổng quản trị hệ thống (**Admin Portal**), hàng đợi kiểm duyệt (Moderation Queue), công cụ phát hiện & hợp nhất POI trùng lặp (Fuzzy duplicate merge) và nhật ký kiểm toán (Audit Logs).
- [x] **Phase 9**: **Trợ lý AI Concierge Chatbot (`/chat`)** trích xuất ràng buộc tự nhiên, thanh tra Live Constraints Inspector và công cụ **So sánh lịch trình đa phương án (`/compare`)**.
- [ ] **Phase 10**: Tích hợp dữ liệu giao thông thời gian thực và cổng thanh toán trực tuyến (VNPAY / MoMo).

---

## 🤝 Đóng góp & Giấy phép

Dự án được phân phối theo giấy phép mã nguồn mở **MIT License**. Mọi đóng góp, báo cáo lỗi và đề xuất tính năng mới xin vui lòng gửi thông qua **Pull Request** hoặc **Issues**. Xem thêm tại [CONTRIBUTING.md](CONTRIBUTING.md).

---

<div align="center">
  <sub>Được phát triển với niềm đam mê dành cho nhịp sống, công nghệ thông minh và chiều sâu văn hóa TP. Hồ Chí Minh.</sub>
</div>
