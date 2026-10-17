# Runbook cụm Travility

Cụm phân tán chạy bằng `docker-compose.cluster.yml` ([spec](superpowers/specs/2026-10-01-scale-he-phan-tan-design.md)). Dev hằng ngày vẫn dùng `docker compose up` (một tiến trình). Hai chế độ dùng chung cổng nên chỉ bật một.

## Dựng cụm

```bash
docker compose down                                        # tắt chế độ một tiến trình nếu đang chạy
docker compose -f docker-compose.cluster.yml up -d --build
cd server && uv run python -m scripts.import_places ../data/places   # lần đầu: volume mới chưa có Place
docker compose -f ../docker-compose.cluster.yml exec api uv run --no-dev python -m scripts.seed_users   # User mẫu
```

`nginx` (trước 2 bản `api`) ở `localhost:8000`, `llm-gateway` ở `localhost:8001`, `places` ở `localhost:8002` (hai cổng sau chỉ để kiểm tra), `pg-catalog` ở `localhost:5432`. Mọi lệnh dưới đây viết tắt `dc` = `docker compose -f docker-compose.cluster.yml`.

## Số đếm của gateway

```bash
dc exec redis redis-cli mget gw:stat:hit gw:stat:miss gw:stat:provider_call gw:stat:wait gw:stat:fallback
```

## Ghi kịch bản demo rồi phát lại khi mất mạng

Request LLM phải lặp lại y nguyên mới trúng cache, nên "hôm nay" phải cố định và database không được import lại giữa lúc ghi và lúc phát.

1. Chọn ngày ghi, ví dụ hôm nay. Bật cụm ở chế độ ghi, không hết hạn:
   ```bash
   DEMO_TODAY=2026-10-01 GATEWAY_CACHE=on GATEWAY_CHAT_TTL=0 dc up -d
   ```
2. Có mạng: chạy đúng kịch bản demo trong app, từng tin nhắn theo đúng thứ tự, trên Trip mới.
3. Chuyển sang phát lại (giữ nguyên `DEMO_TODAY`):
   ```bash
   DEMO_TODAY=2026-10-01 GATEWAY_CACHE=replay dc up -d
   ```
4. Tắt mạng, tạo Trip mới, chạy lại kịch bản. Tin nhắn ngoài kịch bản → bong bóng lỗi (gateway trả 503).

Ngày đi trong kịch bản nên nằm trong 16 ngày kể từ `DEMO_TODAY` để có dự báo mưa. Kết quả dự báo lúc ghi (kể cả lỗi) được giữ lại cho lúc phát.

## Xoá cache

```bash
dc exec redis sh -c "redis-cli --scan --pattern 'gw:cache:*' | xargs -r redis-cli del"   # chỉ cache LLM/embedding
dc exec redis redis-cli flushdb                                                           # mọi thứ: cache, km Goong, dự báo, số đếm
```

## Queue và planner (T3)

Cụm có 2 bản `api` sau `nginx` (cổng 8000) và 2 `planner`. Header `X-Upstream` của mọi phản hồi cho biết bản `api` nào phục vụ.

```bash
dc exec redis redis-cli xlen jobs                          # số việc đã đẩy (tối đa ~1000 mục gần nhất)
dc exec redis redis-cli xpending jobs planners - + 10      # việc đang chạy: id, planner giữ nó, ms im lặng, số lần giao
dc logs -f planner
```

### Tắt một planner giữa lúc lập lịch

1. Gửi một yêu cầu lập lịch trong app. Dùng câu chưa từng gửi: câu đã có trong cache của gateway chạy xong trước khi kịp tắt.
2. `dc exec redis redis-cli xpending jobs planners - + 10` → dòng thứ hai là id container đang giữ việc.
3. `docker kill <id>`.
4. Sau khoảng 20 giây Chat hiện "Đang thử lại…", rồi ra lịch. Danh sách chuyến đi chỉ có một Trip.
5. Bật lại: `dc up -d`.

Việc chạy lại tối đa một lần. Tắt cả hai `planner` thì request báo lỗi sau 120 giây; việc đã chờ quá 120 giây bị bỏ khi `planner` bật lại, không chạy muộn.

### Rate limit

Mỗi User tối đa `PLAN_RPM` (mặc định 5) tin nhắn / lập lịch mỗi phút; vượt → 429 kèm `Retry-After`. Đổi cho một lần chạy: `PLAN_RPM=20 dc up -d`. Số lần bị chặn: `dc exec redis redis-cli get rl:blocked`.

`/auth/*` bị `nginx` giới hạn 1 request/giây theo IP (burst 10).

### Phát lại tiến trình của một việc

```bash
curl -N localhost:8000/jobs/<X-Job-Id>/events -H "Authorization: Bearer <token>"
```

Việc sống 1 giờ. User khác hoặc việc đã hết hạn → 404.

### Lưu ý

- Bật lại hoặc build lại `api` mà `nginx` trả 502 hay không chuyển request tới: `dc restart nginx` (nginx chỉ phân giải tên `api` lúc khởi động).
- Mỗi stream SSE đang mở giữ một thread của bản `api` (pool 40 thread mỗi bản): khoảng 80 lượt lập lịch đồng thời là trần của cụm 2 `api`.
- `redis-cli flushdb` xoá cả queue và việc đang chạy; `planner` tự tạo lại consumer group.

## `places`, bản sao đọc, shard (T5)

Bốn Postgres: `pg-catalog` (users, destinations, places) có bản sao `pg-catalog-replica`; `pg-shard-0` và `pg-shard-1` giữ trips, itineraries, proposals, messages. Trip của User nằm ở shard `user_id % 2`. Đọc Place đi qua service `places`, service này đọc bản sao.

```bash
dc exec api uv run --no-dev python -m scripts.seed_users          # demo1/demo2@travility.vn, mật khẩu travility-demo; in shard của từng User
dc exec pg-shard-0 psql -U travility -c 'SELECT id, user_id FROM trips'
dc exec pg-catalog-replica psql -U travility -c "SELECT pg_is_in_recovery(), now() - pg_last_xact_replay_timestamp() AS tre"
dc logs places | grep -c "POST /search"                           # số lượt tìm Place đã đi qua service
```

### Tắt bản sao

`dc stop pg-catalog-replica` → không ai thấy gì: `places` đọc node chính, đo được vẫn khoảng 10 ms mỗi lượt đọc (`dc logs places` có dòng "bản sao pg-catalog không kết nối được, đọc node chính"). `dc start pg-catalog-replica` là bản sao tự đuổi kịp.

### Tắt một shard

`dc stop pg-shard-1` → User có `user_id` lẻ nhận 503 "Dữ liệu chuyến đi tạm không truy cập được" ở mọi request về Trip; User chẵn dùng bình thường; đăng nhập của cả hai vẫn chạy. Việc lập lịch đang xếp hàng của User shard chết nhận event `error`, worker chạy tiếp việc khác. Shard không có bản sao: bật lại bằng `dc start pg-shard-1`.

### Tắt `places`

`dc stop places` → lập lịch, Disruption → Proposal, khôi phục version báo "Dịch vụ địa điểm tạm không truy cập được". Danh sách Trip, mở Trip, ghim vẫn chạy (mỗi bản `api` giữ bản Destination đọc được gần nhất, nạp sẵn lúc khởi động). Km của Leg quay về ước tính chim bay × 1.3.

### Lưu ý

- Volume mới hoàn toàn: sau `dc down -v` phải chạy lại `import_places` và `seed_users`. Volume `travility-cluster_pgdata` của T2–T4 không còn được dùng; xoá bằng `docker volume rm travility-cluster_pgdata` nếu không cần dữ liệu cũ.
- `import_places` chạy từ máy ngoài, ghi vào `pg-catalog` qua `localhost:5432`; bản sao nhận theo sau vài mili giây.
- `trips.id` tự tăng theo từng shard nên hai User khác shard có thể cùng có Trip số 1. Không lẫn: shard chọn theo User trong JWT trước rồi mới tra id.
- Node treo mà không tắt hẳn (`docker pause`, đứt mạng) thì mỗi lần kết nối chờ tối đa 2 giây rồi mới chuyển sang node khác hoặc báo 503.
- Thêm shard thứ ba đòi chuyển dữ liệu (`user_id % N` đổi kết quả với hầu hết User): không làm; hướng giải là consistent hashing.
- `pg-catalog` chính chết: xem mục T6 "Tắt `pg-catalog`" (đăng nhập đọc bản sao, đăng ký 503, `api` vẫn khởi động lại được).

## Trang "Hệ thống", chế độ chỉ đọc, load test (T6)

### Trang "Hệ thống"

Nút 🖥 trên rail mở sơ đồ cụm theo tầng (cổng vào → API → lập lịch → dịch vụ → dữ liệu), tự làm mới mỗi 2 giây. Xanh = đang chạy, đỏ = đã chết, xám = không rõ (Redis chết nên không đọc được nhịp tim). Bản `api` vừa trả lời có viền vàng; shard chứa Trip của User đang đăng nhập có nhãn "shard của bạn"; bản sao hiện độ trễ.

- Node một bản (4 Postgres, `redis`, `llm-gateway`, `places`) được bản `api` đang trả lời dò ngay trong request, nên đổi màu ở lần làm mới kế tiếp.
- `api`, `planner`, `planner-agent` báo nhịp tim vào Redis mỗi 2 giây (sorted set `nodes`); im quá 6 giây là chết.
- Xem thẳng không cần app: `curl -s localhost:8000/system/status -H "Authorization: Bearer <token>" | python3 -m json.tool`.

**Node ma.** `dc up -d` có đổi biến môi trường hoặc `--build` tạo container mới với hostname mới; bản cũ vẫn nằm trong `nodes` và hiện đỏ tối đa 10 phút. Xoá ngay (bản đang sống tự hiện lại sau 2 giây):

```bash
dc exec redis redis-cli del nodes
```

### Bảng trình diễn

Đã chạy ngày 2026-10-02 trên cụm 15 container. Bật lại node bằng `dc start <service>`, riêng bản bị `docker kill` thì `dc up -d`.

| Kỹ thuật | Lệnh | Quan sát được |
|---|---|---|
| Phát hiện node | `dc stop places`, rồi `dc start places` | `places` đỏ ở lần làm mới kế tiếp (dưới 2 giây), xanh lại ngay khi bật |
| Load balancing | Để trang "Hệ thống" mở | Viền vàng đổi qua lại giữa hai bản `api`; 6 request liên tiếp chia 3 – 3 |
| Caching | Lập cùng một câu hai lần trên hai Trip mới | Lần đầu 8,5–11,6 giây, lần sau dưới 1 giây; ô "Cache LLM" tăng số trúng |
| Rate limit | Gửi 6 yêu cầu lập lịch trong một phút | Lần 6 trả 429 "Bạn gửi yêu cầu quá nhanh, chờ … giây"; ô "Rate limit" tăng 1 |
| Message queue | Gửi câu chưa từng gửi; `dc exec redis redis-cli xpending jobs planners - + 10`; `docker kill <id>` | Một `planner` đỏ; Chat hiện "Đang thử lại…" rồi ra lịch sau khoảng 63 giây; không sinh Trip trùng |
| Nối lại khi `api` chết | Gửi câu chưa từng gửi; `docker kill` bản `api` đang giữ luồng (xem dưới) | Chat không báo lỗi, không lặp dòng đã hiện, ra lịch; log nginx có `GET /jobs/<id>/events` 1 giây sau khi luồng đứt |
| Microservice | `dc stop places` | Lập lịch báo "Dịch vụ địa điểm tạm không truy cập được"; mở Trip cũ và đăng nhập vẫn 200 |
| Replication | `dc stop pg-catalog-replica` | Node đỏ; tìm Place vẫn 200 (đọc node chính); bật lại hiện "trễ 0 ms" |
| Sharding | `dc stop pg-shard-1`, đăng nhập `demo1` và `demo2` | User ở shard 1 nhận 503 "Dữ liệu chuyến đi tạm không truy cập được"; User shard 0 dùng bình thường |
| CAP | `dc stop pg-catalog` | Đăng ký 503 "chế độ chỉ đọc"; đăng nhập, danh sách Trip, lập lịch đều chạy (mục dưới) |
| Node treo | `docker pause travility-cluster-places-1` | Trang vẫn làm mới, mỗi lần chậm thêm 2 giây; `places` đỏ; `docker unpause` là xanh lại |
| Đa agent | `PLANNER_MODE=multi dc up -d`, `dc exec redis redis-cli del nodes` | `GET /system/status` trả `planner_mode: multi` (ô "Lập lịch" ghi "đa agent"); nhãn agent trong Chat: mục T4, lần này không chạy lại |

### Tắt `pg-catalog`

`dc stop pg-catalog` → dữ liệu chung ở chế độ chỉ đọc ([ADR-0008](adr/0008-cap-theo-loai-du-lieu.md)):

- Đăng ký: 503 "Hệ thống đang ở chế độ chỉ đọc, tạm chưa đăng ký được. Bạn thử lại sau nhé."
- Đăng nhập: đọc `pg-catalog-replica`, vẫn 200. Cả bản sao cũng chết thì 503 "Hệ thống tài khoản tạm không truy cập được".
- Danh sách Trip, mở Trip, lập lịch, sửa lịch: chạy bình thường vì Trip nằm ở shard và Place đọc từ bản sao.
- `dc restart api` vẫn lên; log có dòng "pg-catalog không kết nối được lúc khởi động: dữ liệu chung ở chế độ chỉ đọc".
- `import_places` và `seed_users` không chạy được cho tới khi `dc start pg-catalog`.

### Nối lại khi một bản `api` chết

Việc lập lịch chạy trong `planner`, không chết theo `api`. Khi luồng SSE đứt mà chưa có event kết thúc, client chờ 1 giây rồi gọi `GET /jobs/<X-Job-Id>/events`, tối đa 2 lần, và bỏ qua các event đã hiện. nginx bỏ bản `api` chết sau tối đa 2 giây (`proxy_connect_timeout`).

Tìm bản đang giữ luồng để tắt đúng bản:

```bash
for c in travility-cluster-api-1 travility-cluster-api-2; do docker logs --since 10s $c 2>&1 | grep -q 'POST /trips' && echo $c; done
docker kill <tên vừa in>
dc up -d          # bật lại bản đã kill
```

Bật lại một bản `api` hoặc `planner` trong lúc đang có việc lập lịch chạy thì bản đó chờ việc ấy xong mới sẵn sàng (đo được 14–39 giây): bước áp schema lúc khởi động cần khoá bảng trên shard mà transaction của việc đang giữ. Bản còn lại vẫn phục vụ trong lúc chờ.

### Load test

`scripts.loadtest` chạy từ máy ngoài, trỏ vào nginx. Bật cụm với `PLAN_RPM=0`. Script tự tạo User `loadtest1…N` (mật khẩu `travility-load`); bước này chậm vì nginx giới hạn `/auth/` ở 1 request mỗi giây, nên **đăng nhập không được đo**. Sau mỗi lần `dc up -d` đổi cấu hình: `dc restart nginx`.

```bash
# Ghi một lượt lập lịch rồi phát lại 20 lượt đồng thời (cũng tạo Trip cho 20 User)
PLAN_RPM=0 DEMO_TODAY=2026-10-02 GATEWAY_CACHE=on GATEWAY_CHAT_TTL=0 dc up -d
cd server && uv run python -m scripts.loadtest --label "ghi" --users 1 --plans 1 --rounds 0
PLAN_RPM=0 DEMO_TODAY=2026-10-02 GATEWAY_CACHE=replay dc up -d
uv run python -m scripts.loadtest --label "cache bật (replay)" --users 20 --plans 20 --rounds 0

# Đọc Trip: 2 bản api rồi 1 bản
uv run python -m scripts.loadtest --label "2 bản api" --users 20 --rounds 25 --concurrency 50
PLAN_RPM=0 DEMO_TODAY=2026-10-02 GATEWAY_CACHE=replay dc up -d --scale api=1
uv run python -m scripts.loadtest --label "1 bản api" --users 20 --rounds 25 --concurrency 50

# Cache tắt: 2 lượt lập lịch lần lượt, gọi provider thật
PLAN_RPM=0 GATEWAY_CACHE=off dc up -d
uv run python -m scripts.loadtest --label "cache tắt" --users 2 --plans 2 --sequential --rounds 0
```

Kết quả đo ngày 2026-10-02, MacBook Apple M5 Pro (Docker: 15 CPU, 8 GB), 37 Place Đà Lạt, model `gemini-3.5-flash-lite`:

| Cấu hình | Kịch bản | Lượt | Lỗi | p50 (ms) | p95 (ms) | Lượt/giây |
|---|---|---|---|---|---|---|
| cache tắt | lập lịch, lần lượt | 2 | 0 | 8503 | 11608 | 0,1 |
| cache bật (replay) | lập lịch, 20 lượt đồng thời | 20 | 0 | 540 | 936 | 19,8 |
| 1 bản api | danh sách Trip, 50 đồng thời | 500 | 0 | 174 | 244 | 273 |
| 2 bản api | danh sách Trip, 50 đồng thời | 500 | 0 | 167 | 246 | 277 |
| 1 bản api | mở Trip, 50 đồng thời | 500 | 0 | 236 | 837 | 154 |
| 2 bản api | mở Trip, 50 đồng thời | 500 | 0 | 209 | 794 | 164 |

- Bốn dòng đọc Trip là giá trị giữa của ba lần chạy; lượt/giây giữa ba lần lệch nhau tới 15%.
- **Cache:** hai dòng khác cỡ mẫu có chủ ý. Gemini free cho 15 lượt chat mỗi phút và một lần lập lịch tốn 5–8 lượt, nên "cache tắt" chỉ đo được 2 lượt lần lượt. Một lượt lập lịch từ 8,5–11,6 giây xuống còn khoảng 0,5 giây khi trúng cache.
- **Load balancing:** trên một laptop, 2 bản `api` không nhanh hơn 1 bản một cách có ý nghĩa (chênh 1–6%, nhỏ hơn độ lệch giữa các lần chạy). Hai bản chia nhau cùng một máy, và cả hai kịch bản đọc đều đi tiếp qua một bản `places` duy nhất và mở kết nối Postgres mới cho từng request; chưa đo riêng từng khâu để biết khâu nào là nút thắt. Lợi ích thấy được của 2 bản là chịu lỗi (mục "Nối lại khi một bản `api` chết"), không phải thông lượng.
- Mức đồng thời để ở 50: `nginx` trong cụm dùng `worker_connections` mặc định (512, mỗi request proxy tốn 2 kết nối), bắn 500 request cùng lúc thì khoảng 40% bị từ chối ngay ở nginx.

### Smoke test

```bash
./scripts/smoke_cluster.sh     # dựng cụm, kiểm 15 node sống, một lượt lập lịch ra Itinerary
```

## Lập lịch đa agent (T4)

`PLANNER_MODE=multi`: ba agent chuyên gia (`an-uong`, `tham-quan`, `cho-o`) tìm Place song song, agent tổng hợp xếp lịch. Chỉ áp cho lập lịch mới và "Lập lại". Mặc định là `single`.

```bash
PLANNER_MODE=multi dc up -d          # cụm: 3 bản planner-agent đọc stream agent_jobs
dc logs -f planner-agent             # mỗi role một dòng "agent <role> xong việc …"
dc exec redis redis-cli xlen agent_jobs
```

Chế độ một tiến trình: đặt `PLANNER_MODE=multi` trong `server/.env`. Không cần Redis; ba agent chạy bằng 3 thread.

Trong Chat, mỗi dòng tìm kiếm có nhãn agent: "Ăn uống · Đang tìm: …", "Tham quan · …", "Chỗ ở · …". Trip 1 ngày không có agent chỗ ở.

### Tắt agent giữa lúc lập lịch

1. `dc stop planner-agent`, rồi gửi một yêu cầu lập lịch chưa từng gửi.
2. Điều phối chờ tối đa 45 giây rồi chạy agent đơn; Chat hiện "Chuyển sang lập lịch thường…" kèm các dòng tìm kiếm của agent đơn, rồi ra lịch (đo được: khoảng 56 giây cho cả lượt).
3. `dc start planner-agent`.

Một agent báo lỗi thì chuyển ngay, không chờ 45 giây. Việc trong `agent_jobs` giao nhiều nhất một lần; việc xếp hàng quá 45 giây bị agent bỏ qua.

### Hạn mức provider

Gemini free cho 15 lượt chat mỗi phút cho mỗi model. Một lần lập lịch `multi` dùng trung bình 15 lượt (10–18), `single` trung bình 6 lượt (5–8), nên một lần `multi` đã xấp xỉ trần và hai lần trong cùng một phút chắc chắn vượt: agent nhận 429, điều phối quay về agent đơn, agent đơn cũng 429 và Chat báo "Không kết nối được AI". Cách xử lý:

- Demo và load test: ghi kịch bản một lần rồi chạy `GATEWAY_CACHE=replay` (mục "Ghi kịch bản demo"). Brief của agent tổng hợp gộp danh sách theo thứ tự role cố định nên phát lại trúng cache.
- Chạy thật: đặt `LLM_RPM=14` để gateway chờ thay vì lỗi; chờ lâu hơn 45 giây thì vẫn rơi về agent đơn.

Đã kiểm ngày 2026-10-01: ba User gửi ba yêu cầu đã ghi cùng lúc → cả ba ra lịch qua đa agent, không lượt nào trượt cache.

### So `single` với `multi`

```bash
docker compose up -d db redis
cd server && uv run python -m scripts.golden --mode both --rpm 14
```

8 prompt, gọi thẳng provider trong `.env`, đa agent chạy bằng thread. `--rpm 14` hãm theo hạn mức Gemini free; thời gian báo đã trừ phần chờ hạn mức.

Kết quả đo ngày 2026-10-01, model `gemini-3.5-flash-lite`, 37 Place Đà Lạt:

| Chế độ | Prompt | Itinerary hợp lệ | Conflict TB | Giây TB | Giây trung vị | Lượt LLM TB | Về dự phòng |
|---|---|---|---|---|---|---|---|
| single | 8 | 100% | 0,6 | 28,4 | 15,0 | 6,4 | 0 |
| multi | 8 | 100% | 1,1 | 21,9 | 19,5 | 15,1 | 1 |

- Trung bình của `single` bị một prompt kéo lên (127 giây, provider trả chậm một lượt); bảy prompt còn lại từ 9 đến 17 giây. So bằng trung vị thì `multi` chậm hơn khoảng 4,5 giây.
- `multi` tốn gấp 2,4 lần số lượt LLM và có nhiều Conflict hơn. Năm trong tám prompt `multi` bị hãm giữa chừng vì vượt 14 lượt mỗi phút; lần về dự phòng duy nhất là do chờ hạn mức quá 45 giây. Thời gian của các prompt bị hãm chỉ là xấp xỉ.
- Kết luận: trên dữ liệu và hạn mức hiện tại `multi` không hơn `single` ở chỉ số nào. Giữ `single` làm mặc định, kể cả cho demo; `multi` dùng để trình diễn agent chạy song song trên nhiều worker (chạy ở `replay`).
