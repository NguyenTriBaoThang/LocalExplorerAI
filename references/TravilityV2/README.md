# Travility

App desktop lên kế hoạch du lịch trong nước cho người Việt: mô tả chuyến đi bằng một câu, AI dựng lịch trình theo ngày trên bản đồ, chỉ dùng địa điểm thật có trong dữ liệu. Tiền, quãng đường và các xung đột (vượt ngân sách, đóng cửa, mưa, không kịp di chuyển) do code tính, không do AI đoán.

> **Trạng thái:** đồ án nhóm đang phát triển, chưa phát hành cho người dùng cuối. Dữ liệu hiện có 37 địa điểm ở Đà Lạt, trong đó 27 chưa kiểm chứng. Tiến độ từng tính năng: [docs/ROADMAP.md](docs/ROADMAP.md).

## Tính năng

- **Lập lịch bằng một câu.** "Đi Đà Lạt 3 ngày, 3 triệu, thích cafe" → lịch trình theo ngày, đủ ba bữa, có chỗ ở, hiện trên bản đồ cùng tuyến đường.
- **Thấy AI đang làm gì.** Từng lượt tìm địa điểm được phát về app ngay (SSE) và hiện thành pin trên bản đồ.
- **Hỏi lại khi thiếu thông tin.** Chưa biết phương tiện hoặc giờ đến, giờ về thì app hỏi một vòng rồi mới lập lịch.
- **Xung đột do code tính.** Vượt ngân sách, địa điểm đóng cửa, khả năng mưa (Open-Meteo), không kịp di chuyển (Goong Distance Matrix).
- **Sửa lịch bằng hội thoại.** Đổi một điểm dừng, ghim điểm muốn giữ, mỗi lần sửa là một phiên bản mới và quay lại được phiên bản cũ.
- **Xuất PDF theo phiên bản đang xem.** PDF lưu snapshot lịch trình, chỗ ở, chặng di chuyển, chi phí, xung đột hiện có, số phiên bản và thời điểm xuất.
- **Góp ý và duyệt lịch theo nhóm.** Góp ý trong Chat tạo preview; chỉ người tổ chức mới có thể áp dụng preview thành phiên bản lịch mới.
- **Xử lý sự cố không cần AI.** "Báo đóng cửa", "Đổi chỗ khác", "Giả sử mưa", "Tôi trễ 30 phút" → code đề xuất phương án thay thế giữ đúng mục đích của điểm dừng.
- **Đổi nhà cung cấp AI bằng biến môi trường.** Mọi lời gọi đi qua giao thức OpenAI; mặc định dùng Gemini, đổi sang OpenAI không sửa code.
- **Chạy được thành cụm phân tán (tuỳ chọn).** Hàng đợi Redis Streams, worker lập lịch, cache và chế độ phát lại cho LLM, cân bằng tải, lập lịch đa agent.

## Kiến trúc

```
desktop (pywebview) ──► client (React + MapLibre) ──HTTP + SSE──► api (FastAPI)
                                                                   ├─► Postgres + pgvector   địa điểm, chuyến đi, lịch trình
                                                                   ├─► LLM qua giao thức OpenAI   Gemini / OpenAI
                                                                   └─► Goong (bản đồ, quãng đường) · Open-Meteo (mưa)
```

AI chỉ làm hai việc: đọc yêu cầu thành dữ liệu chuyến đi, và chọn địa điểm từ kết quả tìm kiếm rồi xếp thứ tự. Mọi địa điểm trong lịch phải là thứ AI đã nhận từ công cụ tìm kiếm ([ADR-0001](docs/adr/0001-ai-chi-chon-place-co-san.md)); lịch chứa địa điểm lạ bị từ chối.

Cụm phân tán thêm `nginx`, hai bản `api`, các worker `planner`, `llm-gateway` và Redis. Sơ đồ và cách vận hành: [docs/runbook-cum.md](docs/runbook-cum.md).

## Yêu cầu

- Docker và Docker Compose
- Python 3.12 trở lên và [uv](https://docs.astral.sh/uv/)
- Node.js 20.19 trở lên
- Key của một nhà cung cấp LLM (Gemini hoặc OpenAI) và key [Goong](https://goong.io) cho bản đồ

## Chạy lần đầu

```bash
cp server/.env.example server/.env        # điền LLM_API_KEY, EMBED_API_KEY, JWT_SECRET
python -c "import secrets;print(secrets.token_urlsafe(32))"   # dán kết quả vào JWT_SECRET
cp client/.env.example client/.env        # điền hai key Goong

docker compose up -d --build              # Postgres, Redis và API ở http://localhost:8000
cd server && uv sync && uv run python -m scripts.import_places ../data/places
cd ../client && npm install && npm run build
cd ../desktop && uv sync && uv run python main.py
```

Trong app, bấm **Đăng ký** (email bất kỳ, mật khẩu từ 8 ký tự) rồi gõ yêu cầu đầu tiên.

Vài điều hay vấp:

- API không khởi động nếu `JWT_SECRET` còn là giá trị mẫu.
- Gemini gói miễn phí: giữ `LLM_MODEL=gemini-3.5-flash-lite`. Bản `gemini-2.5-flash` chỉ cho 5 request mỗi phút, lập lịch sẽ báo "Không kết nối được AI". Lỗi thật nằm trong `docker compose logs api`.
- Không có credit OpenAI cho embedding: dùng khối Gemini đã chú thích sẵn trong `server/.env.example`, rồi chạy lại `import_places`. Đổi nhà cung cấp embedding luôn phải import lại ([ADR-0003](docs/adr/0003-mot-sdk-openai-hai-provider.md)).

## Cấu hình

Toàn bộ biến và chú thích nằm trong [server/.env.example](server/.env.example) và [client/.env.example](client/.env.example). Các biến chính:

| Biến | Ý nghĩa |
|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Nhà cung cấp chat, theo giao thức OpenAI |
| `EMBED_BASE_URL`, `EMBED_API_KEY`, `EMBED_MODEL` | Nhà cung cấp embedding cho tìm địa điểm |
| `JWT_SECRET` | Khoá ký token đăng nhập, bắt buộc đổi |
| `GOONG_API_KEY` | Quãng đường và thời gian di chuyển thật; để trống thì ước lượng theo đường chim bay |
| `REDIS_URL` | Bật hàng đợi lập lịch, cache và giới hạn theo người dùng; khi đặt phải chạy thêm `uv run python -m app.worker` |
| `PLANNER_MODE` | `single` (mặc định) hoặc `multi`: ba agent chuyên gia tìm địa điểm song song |
| `VITE_GOONG_MAPTILES_KEY`, `VITE_GOONG_API_KEY` | Bản đồ nền và tuyến đường ở client |

Để trống các biến phần "Scale" thì app chạy một tiến trình, không cần Redis.

## Cụm phân tán (tuỳ chọn)

```bash
docker compose down
docker compose -f docker-compose.cluster.yml up -d --build
```

Cụm gồm `nginx`, 2 `api`, 2 `planner`, 3 `planner-agent`, `llm-gateway`, Redis và Postgres, dùng khoảng 850 MB RAM. Cách ghi kịch bản rồi phát lại khi mất mạng, tắt thử một worker, đo `single` với `multi`: [docs/runbook-cum.md](docs/runbook-cum.md).

## Phát triển

```bash
docker compose up -d db redis && cd server && uv run pytest     # test server (cần Postgres và Redis)
cd client && npm test && npm run build                           # test và build client
cd client && npm run dev                                         # client dev ở http://localhost:5173
cd desktop && uv run python main.py http://localhost:5173        # mở app trỏ vào bản dev
```

- Sửa code server: `docker compose up -d --build api`. Sửa `server/.env`: `docker compose up -d --force-recreate api`.
- Sửa `data/places/*.json`: chạy lại `import_places` (ghi đè theo `ext_id`, không mất dữ liệu).
- Build client xong mà app desktop vẫn trắng hoặc chạy bản cũ (macOS): tắt app, xoá `~/Library/Caches/python3`, mở lại.

## Cấu trúc thư mục

```
client/     React + TypeScript + MapLibre: Chat, Timeline, bản đồ
desktop/    Cửa sổ pywebview mở client
server/
  app/      FastAPI: agent, luật tính tiền và xung đột, chuyến đi, hàng đợi, llm-gateway
  scripts/  import địa điểm, golden set
  tests/    pytest, chạy trên Postgres và Redis thật
data/places/  Dữ liệu địa điểm (JSON), nguồn duy nhất để import
docker/     Cấu hình nginx, khởi tạo database
docs/       PRD, lộ trình, ADR, spec, plan, runbook
```

## Tài liệu

| Tài liệu | Trả lời câu hỏi |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Làm gì, vì sao, cho ai |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Việc nào xong, việc nào đang làm, ai làm |
| [CONTEXT.md](CONTEXT.md) | Thuật ngữ dùng trong code, giao diện và issue |
| [docs/2026-09-25-hien-trang-app.md](docs/2026-09-25-hien-trang-app.md) | Code đang chạy thế nào |
| [docs/adr/](docs/adr/) | Quyết định kiến trúc và lý do |
| [docs/superpowers/specs/](docs/superpowers/specs/), [plans/](docs/superpowers/plans/) | Thiết kế kỹ thuật và kế hoạch từng giai đoạn |
| [docs/runbook-cum.md](docs/runbook-cum.md) | Vận hành cụm phân tán |

Khi tài liệu mâu thuẫn: PRD thắng spec; `CONTEXT.md` thắng về cách gọi tên.

## Đóng góp

1. Việc được ghi thành [GitHub Issue](https://github.com/toilact/TravilityV2/issues); nhãn theo [docs/agents/triage-labels.md](docs/agents/triage-labels.md).
2. Làm trên nhánh riêng, mở PR vào `main`. Test server và client phải xanh.
3. Dùng đúng thuật ngữ trong `CONTEXT.md`. Thông báo cho người dùng viết bằng tiếng Việt.
4. Đổi yêu cầu thì sửa PRD; quyết định kiến trúc mới thì thêm một ADR.

## Nhóm

| Thành viên | Phụ trách |
|---|---|
| Đỗ Chí Thành ([@toilact](https://github.com/toilact)) | Agent, luật, sửa lịch, hệ phân tán |
| Đặng Trần Minh Nhật ([@minhatt1901](https://github.com/minhatt1901)) | Client, bản đồ, giao diện |
| Nguyễn Duy Quân ([@skyduyquan2-sudo](https://github.com/skyduyquan2-sudo)) | Dữ liệu địa điểm, import |
| Nguyễn Thanh Tùng ([@nguyentung206](https://github.com/nguyentung206)) | Đăng nhập, đóng gói |

## Giấy phép

Dự án chưa có giấy phép. Khi chưa có file `LICENSE`, mã nguồn mặc định thuộc quyền của các tác giả; hãy mở issue nếu bạn muốn dùng lại.
