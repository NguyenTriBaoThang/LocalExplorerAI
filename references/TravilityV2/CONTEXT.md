# Travility

Ứng dụng giúp người Việt lên kế hoạch du lịch trong nước: người dùng mô tả mong muốn, AI dựng lịch trình trên bản đồ và cùng người dùng chỉnh sửa.

## Language

**User** (Người dùng):
Người có tài khoản trong app; sở hữu các Trip của mình.
_Avoid_: Account, customer, member

**Traveler Profile** (Hồ sơ du lịch):
Preference, Pace và Travel Mode mặc định của một User, được chép vào mỗi Trip mới lúc tạo. Đổi Traveler Profile không làm thay đổi các Trip đã có.
_Avoid_: Settings, persona

**Destination** (Điểm đến):
Một thành phố hoặc vùng mà app có dữ liệu Place đầy đủ (vd. Đà Lạt, Đà Nẵng – Hội An). Mỗi Trip thuộc đúng một Destination.
_Avoid_: City, region, khu vực

**Trip** (Chuyến đi):
Mong muốn du lịch của người dùng — một Destination, số ngày (và ngày đi nếu có), số người, Budget, Preference, Pace, Travel Mode. Thuộc về đúng một User và mặc định chỉ User đó thấy. Ở giai đoạn chia sẻ trên mobile sau này, User có thể cấp quyền Guest xem phạm vi Itinerary được chia sẻ và gửi góp ý; Trip Chat, Traveler Profile và Trip khác vẫn riêng tư. Một Trip có nhiều phiên bản Itinerary.
_Avoid_: Plan, tour, request

**Organizer** (Người tổ chức):
User sở hữu Trip, chịu trách nhiệm chọn version và quyết định áp dụng góp ý. Trong giai đoạn 1 trên desktop, Organizer xuất PDF và nhập góp ý của nhóm trong Trip Chat; chia sẻ trực tiếp cho Guest trên mobile thuộc giai đoạn 2.
_Avoid_: Host, owner (owner là quan hệ sở hữu, không phải vai trò trong flow)

**GroupReview** (Góp ý nhóm):
Góp ý của thành viên về một version Itinerary cụ thể. Ở giai đoạn 1, Organizer nhập/tóm tắt góp ý trong Trip Chat; ở giai đoạn 2, Guest có thể gửi góp ý trên mobile. Chỉ Organizer quyết định có áp dụng bản xem trước để tạo version mới hay không.
_Avoid_: Vote, approval (Guest góp ý, không tự duyệt lịch)

**Guest** (Khách mời):
Người không sở hữu Trip, chỉ có quyền xem Itinerary được chia sẻ và gửi GroupReview khi mở lời mời hợp lệ trong app mobile native ở giai đoạn 2. Guest không xem Trip Chat, Traveler Profile hay Trip khác. Đây là kế hoạch chưa triển khai; không làm web app.
_Avoid_: User, member (Guest không phải User có tài khoản và không có quyền thành viên chung)

**Itinerary** (Lịch trình):
Một phương án cụ thể, bất biến, do AI tạo cho một Trip. Mỗi lần chỉnh sửa sinh ra một phiên bản Itinerary mới; phiên bản cũ được giữ để quay lại.
_Avoid_: Schedule, plan, lịch

**Conflict** (Xung đột):
Một điểm Itinerary không đáp ứng được mong muốn của Trip — vượt Budget, Stop ngoài giờ mở cửa của Place, thiếu Tag bắt buộc, Stop ngoài trời vào ngày dự báo mưa, không kịp di chuyển giữa hai Stop. Itinerary vẫn được tạo, kèm danh sách Conflict và gợi ý khắc phục.
_Avoid_: Error, warning, violation

**Revision** (Chỉnh sửa):
Một yêu cầu thay đổi bằng lời của người dùng trên Itinerary hiện tại, tạo ra phiên bản Itinerary kế tiếp. Chỉ những Stop liên quan đến yêu cầu được phép thay đổi.
_Avoid_: Edit, update, regenerate

**Pinned Stop** (Stop đã ghim):
Stop người dùng đánh dấu giữ nguyên; không Revision nào được thay đổi hay xoá nó.
_Avoid_: Locked, favorite, starred

**Place** (Địa điểm):
Một nơi có thật do nhóm thu thập và kiểm chứng — quán ăn, điểm tham quan, cafe, chỗ ở… Tồn tại độc lập với mọi Itinerary; AI chỉ được chọn Place có sẵn, không được tự nghĩ ra.
_Avoid_: POI, location, spot, điểm

**Stop** (Điểm dừng):
Một lần ghé một Place trong một Itinerary, vào một ngày và khung giờ cụ thể. Cùng một Place có thể xuất hiện ở nhiều Stop.
_Avoid_: Visit, activity, item

**Suggestion** (Gợi ý):
Một Place được đề xuất nhưng chưa nằm trong Itinerary (vd. từ ảnh cảm hứng hay câu hỏi "quanh đây có gì"). Chỉ trở thành Stop khi người dùng chấp nhận, qua một Revision.
_Avoid_: Recommendation, candidate, result

**Inspiration Photo** (Ảnh cảm hứng):
Ảnh người dùng đưa vào để diễn tả kiểu nơi họ muốn tới; app tìm các Place có cùng không khí và trả về dưới dạng Suggestion.
_Avoid_: Upload, image query

**Stay** (Chỗ ở):
Việc lưu trú tại một Place loại chỗ ở cho mọi đêm của một Itinerary; là điểm xuất phát và kết thúc của mỗi ngày. Không phải Stop. Loại chỗ ở (khách sạn, homestay, hostel, resort) được biểu diễn bằng Tag.
_Avoid_: Hotel, booking, lodging

**Leg** (Chặng):
Quãng di chuyển giữa hai điểm liên tiếp trong cùng một ngày (Stay → Stop, Stop → Stop, Stop → Stay).
_Avoid_: Route, segment, trip

**Travel Mode** (Phương tiện):
Cách di chuyển chính trong thành phố của một Trip — xe máy thuê (mặc định), taxi/Grab, xe máy riêng hoặc ô tô riêng. Xe riêng không tính tiền thuê. Leg quá ngắn luôn đi bộ bất kể Travel Mode.
_Avoid_: Transport, vehicle

**Origin** (Nơi xuất phát):
Thành phố người dùng đi từ đó tới Destination. Chỉ để hiển thị và gợi ý Arrival Mode; không tính tiền.
_Avoid_: Điểm đi, home

**Arrival / Departure** (Giờ đến / Giờ về):
Thời điểm tới Destination ngày 1 và rời Destination ngày cuối. Stop phải cách giờ đến ít nhất 60 phút và cách giờ về ít nhất 90 phút.
Người dùng có thể đặt thêm **giờ xong hoạt động ngày cuối** (vd bay 17:00 nhưng muốn xong lúc 13:00): Stop ngày cuối phải kết thúc trước mốc sớm hơn trong hai mốc này. Đây không phải giờ về.
_Avoid_: Check-in, check-out

**Arrival Mode** (Phương tiện đến):
Cách tới Destination — máy bay, xe khách, tàu, tự lái. Khác Travel Mode (đi lại trong thành phố). Chỉ dùng để chọn Hub.
_Avoid_: Transport

**Hub** (Điểm đến nơi):
Sân bay, bến xe hoặc ga của một Destination; điểm đầu ngày 1 và điểm cuối ngày cuối khi biết Arrival Mode.
_Avoid_: Terminal, station

**Pace** (Nhịp độ):
Mức dày đặc của mỗi ngày trong Trip — thong thả, vừa (mặc định) hoặc dày — quyết định số Stop và khung giờ hoạt động mỗi ngày.
_Avoid_: Intensity, tempo, mật độ

**Forecast** (Dự báo thời tiết):
Khả năng mưa dự kiến cho từng ngày của một Trip có ngày đi cụ thể: từ dịch vụ dự báo nếu ngày đi trong 16 ngày tới, từ mô hình mưa của nhóm nếu xa hơn. Trip không có ngày đi thì không có Forecast.
_Avoid_: Weather data

**Tag** (Nhãn):
Một đặc điểm thuộc bộ từ vựng cố định (vd. cafe-chill, an-chay, thien-nhien) gắn cho Place. Là ngôn ngữ chung giữa sở thích người dùng và dữ liệu Place.
_Avoid_: Category, label, vibe

**Preference** (Sở thích):
Những gì người dùng muốn hoặc không muốn trong một Trip, quy về ba nhóm Tag: bắt buộc, ưu tiên, tránh.
_Avoid_: Filter, taste, interest

**Reason** (Lý do chọn):
Lời giải thích vì sao một Stop được chọn, dẫn chiếu tới Preference/Tag mà Place đó đáp ứng.
_Avoid_: Explanation, note

**Budget** (Ngân sách):
Số tiền người dùng muốn chi cho một Trip, bao gồm ăn uống, vé tham quan, Stay và chi phí các Leg trong thành phố. Không bao gồm di chuyển liên tỉnh đến/rời thành phố.
_Avoid_: Chi phí, price, cost (cost là số ước tính của Itinerary, không phải Budget)

**Intent** (Mục đích):
Lý do lớn khiến người dùng chọn chuyến đi, gom nhiều Tag lại: ẩm thực, thiên nhiên, văn hoá, thư giãn, vui chơi. Bảng ánh xạ Tag → Intent nằm trong code. Trọng số Intent của Trip suy ra từ Preference (Tag bắt buộc nặng hơn Tag ưu tiên).
_Avoid_: Goal, purpose, category

**Intent Retention** (Mức giữ mục đích):
Tỉ lệ có trọng số các Intent của Trip mà Itinerary còn đáp ứng (có ít nhất một Stop thuộc Intent đó). Là chỉ số sản phẩm, không phải xác suất hài lòng.
_Avoid_: Score, match %, độ phù hợp

**Disruption** (Sự cố):
Một thay đổi làm Itinerary hiện tại không còn phù hợp: Place đóng cửa, người dùng không thích một Stop, mưa một ngày, hoặc trễ giờ. Do người dùng báo; app không tự đổi lịch.
_Avoid_: Event, incident, lỗi

**Job** (Việc):
Một yêu cầu cần gọi LLM (lập lịch, lập lại, followup) được `api` đẩy vào hàng đợi và một worker xử lý. Người dùng không thấy Job; họ chỉ thấy tiến trình của nó trong chat.
_Avoid_: Task, request, message

**Agent chuyên gia**:
Một agent AI chỉ lo một loại Place khi lập lịch — ăn uống, tham quan, hoặc chỗ ở — và trả về danh sách ngắn. Agent tổng hợp xếp các danh sách đó thành Itinerary.
_Avoid_: Sub-agent, bot, worker (worker là tiến trình chạy agent)

**Shard**:
Một database chứa Trip, Itinerary, tin nhắn và Proposal của một phần User. Mỗi User thuộc đúng một Shard, xác định từ mã User.
_Avoid_: Partition, node, phân vùng

**Proposal** (Phương án):
Một Itinerary ứng viên do code tạo từ một Disruption, kèm số liệu so sánh với bản hiện tại và lý do. Chưa phải phiên bản Itinerary; chỉ thành phiên bản mới khi người dùng áp dụng.
_Avoid_: Alternative, draft, suggestion (Suggestion là Place, Proposal là cả Itinerary)
