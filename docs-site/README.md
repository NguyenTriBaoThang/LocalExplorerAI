# Local Explorer AI — Documentation Site

Trang tài liệu kỹ thuật tĩnh và showcase của **Local Explorer AI** — được xây dựng bằng React, TypeScript và Vite, triển khai lên GitHub Pages.

> **Đây không phải ứng dụng sản phẩm** (`apps/web`) — không cần backend, database, API key hay biến môi trường nào.

---

## ⚙️ Công nghệ

- **Framework**: React + TypeScript + Vite
- **Icons**: `lucide-react`
- **Routing**: Hash-based (`#/architecture`, `#/api`, ...) — deep links hoạt động trên GitHub Pages không cần server fallback
- **3D**: Không dùng Three.js — trang Digital Twin là sơ đồ SVG nhẹ
- **Hosting**: GitHub Pages via GitHub Actions

---

## 🚀 Phát triển Cục bộ

```bash
cd docs-site
npm install
npm run dev
```

## 🏗️ Build

```bash
npm run build
```

Output tại `docs-site/dist/`. `base: './'` đảm bảo build hoạt động đúng dưới bất kỳ GitHub Pages URL nào.

## 👁️ Preview

```bash
npm run preview
```

---

## 🌐 Triển khai GitHub Pages

1. Push repository lên GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Workflow `.github/workflows/deploy-pages.yml` tự động build `docs-site` và deploy qua `configure-pages`, `upload-pages-artifact` và `deploy-pages` actions.

**Trigger**: Push đến `main` hoặc `gh-page` có thay đổi trong `docs-site/`, hoặc chạy thủ công (workflow_dispatch).

**URL công khai**: `https://nguyentribaothang.github.io/LocalExplorerAI/`

---

## 📝 Nguồn Nội dung Tài liệu

Toàn bộ nội dung lấy từ mã nguồn thực tế của repository:

| Nội dung | Nguồn |
|---|---|
| Endpoints, access levels | `@router` decorators trong `apps/api/app/api/routes/`, `require_roles` dependencies |
| Request/Response bodies | Pydantic schemas tại `apps/api/app/schemas/` |
| Ranker features (15) | `FEATURE_NAMES` trong `apps/api/app/services/ranker_features.py` |
| ML caveats & safety | `docs/ml-training-and-data.md` |
| Demo walkthrough, story, roadmap | `DEMO_SCRIPT.md`, `COMPETITION_SUBMISSION.md`, `README.md` |
| Screenshots | `assets/screenshots/*.png`, converted to WebP in `public/img/` |

Dữ liệu tương tác (concierge demo, replanning, digital twin, explainability meter) sử dụng sample data viết tay và được đánh dấu rõ ràng — không gọi backend.

---

## ⚠️ Lưu ý Khoảng cách Tài liệu (Known Gaps)

> [!WARNING]
> - `ARCHITECTURE.md` cũ mô tả Haversine routing — đã được **cập nhật** để phản ánh Goong Directions API thực tế.
> - Trained model weights (ranker, E5, flood) **không có trong repository** — cần huấn luyện hoặc tải về trước khi chạy ML endpoints.
> - Trang Digital Twin trong docs-site là SVG schematic — không dùng Three.js như ứng dụng thật.

---

## 📁 Cấu trúc Thư mục

```text
docs-site/
├── src/
│   ├── data/        # Static JSON data cho interactive demos
│   ├── pages/       # Trang tài liệu: architecture, api, ml, planning, demo...
│   └── components/  # Shared UI components
├── public/
│   └── img/         # Screenshots & diagrams (WebP format)
├── index.html
└── vite.config.ts
```
