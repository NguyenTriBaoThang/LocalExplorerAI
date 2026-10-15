# Đề xuất giải pháp Local Explorer AI cho MLAI Hackathon 2026 Track Tasco

**Tên giải pháp:** Local Explorer AI — Lớp trải nghiệm địa phương trên bản đồ  
**Track:** Xây dựng lớp ứng dụng cho bản đồ của người Việt — định hướng Tasco  
**Địa bàn demo:** Khu vực pilot Quận 1, TP. Hồ Chí Minh  
**Phiên bản:** 2.0 — cập nhật ngày 15/10/2026  
**Sản phẩm dự thi:** Working Web Demo và Pitch Deck

## 1. Tóm tắt giải pháp

Local Explorer AI bổ sung một lớp dữ liệu và ứng dụng chuyên đề du lịch địa phương lên bản đồ: thay vì chỉ tìm “địa điểm ở đâu”, người dùng có thể tìm “trải nghiệm nào phù hợp, có thể tham gia trong khung giờ của mình, đi theo tuyến nào và thông tin đó được xác nhận từ đâu”.

Du khách nhập nhu cầu bằng tiếng Việt, chọn điểm đi/đến và các ràng buộc. Hệ thống truy vấn trải nghiệm có dữ liệu phù hợp, kiểm tra thời gian hoạt động, thời lượng, ngân sách, sức chứa, điểm bắt buộc và chặng đường về; sau đó hiển thị kết quả trên bản đồ và lịch trình có nguồn dữ liệu. Nếu thông tin quan trọng chưa được xác nhận, giao diện phải nói rõ thay vì trình bày như sự thật.

Giải pháp phù hợp với định hướng Track Tasco vì tạo một lớp ứng dụng bản đồ có tính địa phương, có thể mở rộng sang hệ sinh thái di chuyển. VMap/T-Maps là nền bản đồ đích cần được kiểm chứng bằng SDK/API và quyền truy cập do Tasco hoặc Ban Tổ chức cấp. Repository hiện có giao diện bản đồ và adapter định tuyến Goong, nhưng chưa có bằng chứng đủ để tuyên bố đã tích hợp hoặc nghiệm thu VMap/T-Maps. Demo phải ghi đúng nhà cung cấp đang sử dụng.

## 2. Bài toán và nhu cầu

Bản đồ phổ thông giúp người dùng định vị và tìm đường, nhưng hành trình trải nghiệm địa phương còn cần biết:

- Địa điểm đó có hoạt động/trải nghiệm nào, hay chỉ là một POI để ghé thăm?
- Giá, thời lượng và giờ hoạt động lấy từ đâu, được xác nhận khi nào?
- Có slot phù hợp và đủ sức chứa cho nhóm không?
- Lịch trình có đáp ứng thời gian, ngân sách và điểm bắt buộc, kể cả chặng trở về không?
- Nếu ca bị hủy hoặc dữ liệu đã cũ, người dùng được cảnh báo và có phương án thay thế nào?

Một marker trên bản đồ không đồng nghĩa với một dịch vụ đang hoạt động hoặc còn chỗ tham gia. Sản phẩm tách địa điểm, trải nghiệm và slot; đồng thời cho biết nguồn và độ mới của thông tin.

### Người dùng mục tiêu

- **Du khách:** khách nội địa, khách lần đầu đến TP.HCM, nhóm bạn hoặc gia đình muốn khám phá văn hóa, ẩm thực và hoạt động địa phương mà không phải tự ghép nhiều ứng dụng.
- **Cơ sở/đối tác:** cơ sở nhỏ, nghệ nhân, đơn vị workshop và điểm trải nghiệm cần cập nhật thông tin, ca và sức chứa, đồng thời xác nhận yêu cầu.
- **Hệ sinh thái bản đồ Tasco:** đối tác có thể bổ sung lớp dữ liệu địa phương và tăng ngữ cảnh sử dụng bản đồ trong hành trình thực tế. Mức độ hợp tác và tích hợp cần được xác nhận, không mặc định đã có thỏa thuận.

## 3. Giá trị và điểm khác biệt

1. **POI → Experience → Slot:** phân biệt địa điểm vật lý với hoạt động cụ thể và ca tham gia.
2. **Lịch trình có ràng buộc:** planner kiểm tra tính khả thi trước; ranker không thể hợp thức hóa lựa chọn vi phạm giờ về, ngân sách, điểm khóa hoặc sức chứa.
3. **Nguồn và freshness nhìn thấy được:** thông tin có nguồn, thời điểm xác nhận và hạn dùng; dữ liệu thiếu căn cứ hiển thị pending/unknown.
4. **Bản địa hóa:** truy vấn tiếng Việt, văn hóa và hoạt động đặc thù tại TP.HCM.
5. **Phối hợp vai trò:** khách lập lịch, cơ sở cập nhật ca, quản trị viên kiểm duyệt nguồn và dữ liệu.

Local Explorer AI không định vị là một bản đồ tổng quát khác. Sản phẩm bổ sung một lớp trải nghiệm có thời gian, dịch vụ và bằng chứng dữ liệu lên nền bản đồ.

## 4. Luồng sản phẩm

### Luồng du khách

1. Nhập yêu cầu tự nhiên bằng tiếng Việt; hệ thống trích xuất nhóm khách, giờ, ngân sách, phương tiện, mục đích và địa điểm bắt buộc.
2. Xem lại, chỉnh sửa ràng buộc đã trích xuất; LLM không tự xác nhận giá hoặc chỗ trống.
3. Chọn điểm đi, điểm đến, ngày, phương tiện và điểm cần khóa.
4. Xem trải nghiệm có nguồn trên bản đồ; mở chi tiết để xem giá, thời lượng, giờ, slot, tình trạng xác nhận và dữ liệu còn thiếu.
5. Yêu cầu planner tạo lịch; planner kiểm tra tuyến giữa các điểm và chặng trở về trước deadline.
6. Lưu/chia sẻ lịch; nếu ca hỗ trợ, gửi yêu cầu giữ chỗ.
7. Khi slot thay đổi, nhận cảnh báo và xem phương án thay thế; khách quyết định có đổi lịch hay không.

### Luồng đối tác và quản trị

- Đối tác cập nhật slot/sức chứa hoặc xác nhận/từ chối yêu cầu.
- Quản trị viên rà soát nguồn, evidence theo trường, dữ liệu trùng và trạng thái duyệt.
- Trạng thái thay đổi và thông tin xác nhận được lưu để truy vết.

### Kịch bản trình diễn

Chọn một tình huống Quận 1 có dữ liệu đã được nhóm kiểm tra; nhập yêu cầu; khóa một điểm; tạo lịch đi-về; mở chi tiết xem nguồn và thời điểm xác nhận; sau đó mô phỏng hủy slot trong sandbox và hiển thị các phương án replan. Mọi dữ liệu synthetic/mock hoặc giao dịch sandbox phải được gắn nhãn trên giao diện và khi thuyết trình.

## 5. Phạm vi demo

### Ưu tiên cho Working Web Demo

- Một khu vực nhỏ có ranh pilot và ngày snapshot dữ liệu được ghi rõ.
- Tìm kiếm/khám phá địa điểm trên bản đồ và chi tiết có provenance.
- Tạo lịch theo điểm đi/đến, khung giờ, ngân sách, điểm khóa và thời gian quay về.
- Phân tách giao diện khách, đối tác và quản trị ở mức cần thiết cho kịch bản.
- Một luồng cập nhật/hủy slot và tư vấn phương án thay thế.
- Dùng sandbox hoặc kịch bản demo có nhãn nếu external service chưa sẵn sàng.

### Không cam kết trong demo

- Phủ hết địa điểm TP.HCM hoặc khẳng định 177 dòng workbook đã đủ evidence cho mọi trường.
- Gọi ETA là traffic thời gian thực nếu nhà cung cấp không đảm bảo điều đó.
- Giao dịch production, hoàn tiền tự động hoặc năng lực phục vụ thực khi chưa có kiểm thử staging/đối tác.
- Tuyên bố ranker đã học sở thích khách thật từ weak-label.
- Dự báo ngập đường từ dữ liệu lịch sử thiếu quan trắc âm và nhãn road-edge phù hợp.

## 6. Tích hợp bản đồ Tasco

Bản đồ là bề mặt tương tác chính để hiển thị lớp trải nghiệm, trạng thái dữ liệu, tuyến và điểm dừng. Adapter giúp thay đổi map/routing provider theo môi trường mà không trộn logic nhà cung cấp vào planner.

### Mục tiêu và điều kiện

- Đích tích hợp của bài dự thi là VMap/T-Maps của Tasco, theo API/SDK, quota và điều khoản sử dụng được cấp.
- Cần kiểm thử tải bản đồ, hiển thị marker/layer, geocoding hoặc tìm kiếm nếu API hỗ trợ, route đi-về, quota và timeout.
- Nếu được cấp quyền truy cập kịp thời, ưu tiên trình diễn lớp trải nghiệm trên nền Tasco.
- Nếu chưa được cấp, demo dùng nền bản đồ hiện tại và ghi rõ đó là provider đang chạy; Tasco được trình bày là đích tích hợp, không giả định đã kết nối.
- Không vẽ tuyến thủ công rồi gọi là route API; hiển thị provider và thời điểm/tuổi dữ liệu ETA.
- Credits/API Ban Tổ chức cung cấp chỉ dùng theo điều kiện chương trình; không đưa API key lên frontend, ảnh chụp pitch hoặc repository.

## 7. Chiến lược dữ liệu

Challenge Brief cho phép kết hợp dữ liệu nhóm tự thu thập, open data hợp pháp, dữ liệu địa lý, cộng đồng, API bên thứ ba và synthetic/mock đại diện. Local Explorer AI phân loại rõ từng nguồn, không trộn dữ liệu demo với catalog vận hành.

| Nguồn | Vai trò | Giới hạn cần công khai |
| --- | --- | --- |
| Workbook 177 địa điểm nhóm thu thập | Nguồn ban đầu để đối soát POI và phân loại | Số dòng không chứng minh mọi trường đã được xác minh; giá, giờ, hoạt động, ảnh và slot cần căn cứ riêng. |
| OpenStreetMap | Candidate vị trí, tên và tag địa lý | Ghi attribution và tuân thủ ODbL; không xác nhận venue hoạt động, giá hay chỗ trống. |
| Cơ sở/đối tác | Xác nhận trải nghiệm, giá, thời lượng, slot/capacity của chính cơ sở | Lưu người/tổ chức xác nhận, thời điểm, revision và hạn hiệu lực. |
| API bản đồ/định tuyến | Bản đồ, geocoding và ETA theo hợp đồng nhà cung cấp | Lưu provider, timestamp, lỗi/cache age; ETA không tự động có nghĩa là realtime. |
| Ảnh | Ảnh có nguồn và quyền sử dụng rõ theo từng file | Lưu trang nguồn, tác giả, license và credit; thiếu căn cứ thì dùng placeholder được ghi nhãn. |
| Synthetic/mock theo brief | Minh họa hủy ca, quá tải hoặc trạng thái tương lai | Gắn nhãn demo/test; tách khỏi catalog vận hành và không dùng làm bằng chứng chất lượng thật. |

Mỗi trường quan trọng cần có source, thời điểm quan sát/xác nhận, phạm vi xác nhận, revision và hạn dùng. Giá, giờ, sức chứa và slot cần freshness phù hợp với tốc độ thay đổi. Thiếu evidence thì để unknown/pending, không suy diễn thành verified.

## 8. AI và xử lý không gian

- **NLU tiếng Việt:** trích xuất ràng buộc thành dữ liệu có cấu trúc; người dùng xem và sửa được.
- **Planner:** logic quyết định feasibility, thời gian, ngân sách, điểm khóa, capacity và chặng về. Planner là thẩm quyền về tính hợp lệ của lịch.
- **Ranking:** rule baseline là mặc định dễ giải thích. Artifact XGBoost bootstrap hiện có dùng weak-label, chưa đủ căn cứ làm preference model production. Chỉ đánh giá ML trên nhãn độc lập/consented và split chống leakage.
- **Replanning/XAI:** đề xuất thay thế trên candidate mà solver đã lọc; đánh đổi lấy từ số liệu API, không bịa.
- **Fallback:** khi LLM hoặc dịch vụ ngoài lỗi, dùng form/rule fallback và nói rõ giới hạn.
- **Flood/GeoAI:** không làm thành tuyên bố cốt lõi của demo nếu thiếu dữ liệu quan trắc theo thời gian và road-edge labels. Đây là hướng nghiên cứu riêng.

## 9. Kiến trúc khả thi

1. **Web client:** chat, bản đồ/danh sách, chi tiết, planner và giao diện theo vai trò.
2. **API:** xác thực, catalog, staging, planner, ranking, booking và adapters.
3. **Data layer:** POI, experience, slot, source/evidence, trạng thái duyệt và lịch sử.
4. **Map/routing adapters:** chuẩn hóa provider theo môi trường và lưu provenance.
5. **AI components:** parser, rule baseline, giải thích và replan; đầu ra được kiểm tra schema và business rules.
6. **Operations:** log truy vết, kiểm soát lỗi/quota, backup và smoke tests.

Mô hình POI → Experience → Slot giúp hệ thống không nhầm “địa điểm có thật” với “dịch vụ có ca đang nhận khách”.

## 10. Tình trạng code và điều kiện trình diễn

Repository hiện có nền web React/TypeScript, API FastAPI, giao diện theo vai trò, chat với fallback, planner, bản đồ/routing adapter, import staging, luồng booking/slot và adapter/cấu hình cho một số dịch vụ ngoài. Đây là nền mã nguồn cho demo; không chứng minh service bên ngoài đã được staging-test.

Trước khi tuyên bố một chức năng là chạy thật, nhóm cần xác nhận:

- API/SDK Tasco/VMap/T-Maps, quyền truy cập và điều khoản;
- provider định tuyến đang hoạt động, trạng thái route và độ mới ETA;
- OAuth, LLM, email, payment sandbox và callback HTTPS nếu đưa vào demo;
- tập địa điểm nhỏ được kiểm tra, ảnh có license, slot được cơ sở xác nhận;
- database/migrations, tài khoản test theo role, log và bản build dự phòng.

Nếu một tích hợp chưa sẵn sàng, hãy tắt nó khỏi live demo hoặc ghi rõ sandbox/mock. Không suy ra tích hợp thành công từ việc có key/config hoặc giao diện hiển thị.

## 11. Tiêu chí demo đề xuất

Đây là mục tiêu cần đội khóa và đo trước khi pitch, không phải kết quả đã đạt:

| Chỉ số | Mục tiêu đề xuất | Cách kiểm tra |
| --- | --- | --- |
| Kịch bản planner | 5/5 kịch bản demo trả đúng trạng thái | Ghi input/output, có ít nhất một trường hợp không khả thi. |
| Hard-constraint violation | 0 trên test set đã định trước | Kiểm giờ, ngân sách, điểm khóa, capacity và chặng về. |
| Truy vết dữ liệu | 100% trường được gọi “đã xác nhận” trong demo có source và thời điểm tương ứng | Đối chiếu giao diện với evidence; phần còn lại ghi unknown/pending. |
| Minh bạch route | 100% màn hình route ghi provider chính xác, không tự gọi realtime | Kiểm tra cache, dữ liệu cũ, timeout và nhãn UI. |
| Rehearsal | Hoàn tất luồng chính bằng build cuối và tài khoản test | Chạy trên máy/mạng dự kiến; lưu checklist lỗi. |

Sau cuộc thi, pilot mới đo thời gian lập lịch, tỷ lệ khách chọn phương án, tỷ lệ provider xác nhận, độ stale, hủy ca và mức hài lòng. Thu thập hành vi cần consent và định nghĩa mẫu số.

## 12. Tác động và hướng mở rộng

### Tác động dự kiến

- Giúp khách khám phá hoạt động địa phương theo thời gian chứ không chỉ xem marker.
- Tạo kênh dữ liệu có cấu trúc cho cơ sở nhỏ và dịch vụ văn hóa.
- Tăng ngữ cảnh địa phương trên bản đồ Việt Nam và nối khám phá với hành trình di chuyển.
- Tạo quy trình cập nhật có provenance, phân biệt thông tin đáng tin với dữ liệu cũ/chưa rõ.

### Giả thuyết vận hành

Sau khi kiểm chứng nhu cầu, có thể thử công cụ quản lý cho cơ sở, phí giới thiệu/booking minh bạch, giải pháp B2B cho điểm đến hoặc lớp dữ liệu chuyên đề cho bản đồ. Đây là các giả thuyết kinh doanh, chưa phải doanh thu hay thỏa thuận đã có.

### Mở rộng

Bắt đầu ở pilot Quận 1. Chỉ mở rộng địa bàn khi quy trình xác nhận trường dữ liệu, cập nhật slot và hỗ trợ vận hành ổn định; không mở rộng chỉ bằng cách thêm POI chưa kiểm tra.

## 13. Kế hoạch thực hiện

Challenge Brief ghi mốc mở đăng ký 24/08, đóng đăng ký 15/09, kick-off 19/09 và chung kết 17/10/2026. Bản đề xuất lập ngày 15/10/2026 nên ưu tiên khóa demo trong hai ngày cuối; đội cần đối chiếu lịch chính thức của mình.

| Thời điểm | Việc cần làm | Đầu ra |
| --- | --- | --- |
| 15/10 | Chốt câu chuyện demo; kiểm tra integration thật; chọn dữ liệu nhỏ có căn cứ; chuẩn bị fallback có nhãn. | Demo scope, danh sách dữ liệu được phép trình bày, checklist lỗi. |
| 16/10 | Đóng băng tính năng; chạy lại 5 kịch bản, phân quyền, lịch đi-về và trạng thái slot; diễn tập pitch và dự phòng mạng. | Build trình diễn, pitch deck, phương án dự phòng. |
| 17/10 | Trình bày vấn đề → thao tác trên bản đồ → giá trị → dữ liệu/AI → kế hoạch tích hợp Tasco và mở rộng. | Working Web Demo và Pitch Deck theo yêu cầu cuộc thi. |

### Roadmap sau hackathon

| Giai đoạn | Trọng tâm | Cổng quyết định |
| --- | --- | --- |
| 0–30 ngày | Chốt quyền dùng map API; audit catalog Quận 1; phỏng vấn khách/cơ sở; hoàn thiện data policy. | Chỉ mở pilot khi có subset dữ liệu theo trường đủ nguồn và provider đồng ý. |
| 31–60 ngày | Onboard cơ sở; tạo experience/slot thật; kiểm thử booking sandbox, notification và replan. | End-to-end test và xử lý stale/error đạt tiêu chí nội bộ. |
| 61–90 ngày | Pilot giới hạn; đo usability, freshness, ETA/slot và tỷ lệ chuyển đổi. | Báo cáo số liệu, giới hạn và quyết định có mở rộng hay không. |

Mục tiêu số lượng POI, experience, slot và đối tác phải được đội xác nhận theo năng lực thực tế; số lượng không thay cho chất lượng bằng chứng.

## 14. Phân công nhóm đề xuất

Điền tên sau khi đội thống nhất; các vai trò dưới đây không giả định thành viên cụ thể.

| Vai trò | Trách nhiệm |
| --- | --- |
| Product/pitch lead | Người dùng, vấn đề, câu chuyện demo, điều phối mentor và pitch. |
| Frontend/map | Bản đồ, lớp hiển thị, tương tác và trạng thái nguồn. |
| Backend/planner | API, feasibility, routing adapter, booking/replan và test. |
| Data/AI | Catalog/provenance, NLU, baseline, đánh giá và giới hạn AI. |
| Demo/QA | Tài khoản test, dữ liệu, rehearsal, bản build dự phòng. |

Một người có thể kiêm nhiệm. Pitch cần nói rõ ai chịu trách nhiệm và không trình bày kinh nghiệm chưa có như thành tích.

## 15. Rủi ro và giảm thiểu

| Rủi ro | Ảnh hưởng | Giảm thiểu |
| --- | --- | --- |
| Chưa có SDK/API Tasco | Không chứng minh được tích hợp nền bản đồ đích | Xin sandbox/credits; nêu rõ adapter và trạng thái; không giả lập API/branding. |
| Thiếu bằng chứng cho giá, giờ, slot, ảnh | Gợi ý có thể gây hiểu nhầm | Thu hẹp tập demo; trường thiếu hiển thị pending; mock gắn nhãn. |
| API hoặc Internet lỗi | Demo gián đoạn | Chuẩn bị snapshot/video nếu được phép, có nhãn và fallback rõ. |
| ETA/slot cũ | Lịch sai hoặc khách không được phục vụ | Timestamp, TTL, stale warning và xác nhận provider. |
| Weak-label bị hiểu là sở thích thật | Tuyên bố AI thiếu căn cứ | Giữ baseline; không trình bày metric weak-label là hiệu quả với khách. |
| Payment/callback chưa staging | Rủi ro giao dịch | Chỉ dùng sandbox, không thu tiền thật trong demo. |
| Scope quá rộng | Demo thiếu ổn định | Chỉ trình diễn một journey Quận 1 và một kịch bản replan. |

## 16. Đối chiếu tiêu chí chấm điểm MLAI Hackathon

| Tiêu chí theo Challenge Brief | Điểm tối đa | Cách Local Explorer AI đáp ứng và bằng chứng cần chuẩn bị |
| --- | ---: | --- |
| Giải quyết vấn đề và tác động | 20 | Nêu rõ khách/cơ sở mục tiêu; demo giảm thao tác ghép lịch; chuẩn bị phỏng vấn hoặc ghi rõ giả định nếu chưa khảo sát. |
| Phù hợp với Việt Nam | 15 | Dữ liệu, ngôn ngữ và trải nghiệm TP.HCM; trình bày attribution, điều kiện dữ liệu và khả năng triển khai trong hạ tầng nội địa. |
| Sáng tạo và khác biệt | 20 | Lớp experience/slot và lịch trình theo deadline, không chỉ layer POI; cho thấy khác biệt qua demo. |
| Đổi mới dữ liệu và AI | 20 | Provenance/freshness; NLU tiếng Việt; planner/ranking; phân biệt minh bạch model baseline với weak-label. |
| Khả thi và sản phẩm thử nghiệm | 15 | Working Web Demo ổn định; luồng chính có thể chạy lại; trình bày tích hợp Tasco theo đúng trạng thái API thực. |
| Trình bày và UX | 10 | UI trực quan; demo 1 kịch bản xuyên suốt; pitch deck trả lời rõ vấn đề, sản phẩm, dữ liệu, AI và mở rộng. |

## 17. Pitch Deck đề xuất

1. Vấn đề và người dùng: bản đồ có POI nhưng không cho biết trải nghiệm nào tham gia được theo khung giờ.
2. Nhu cầu: khách/cơ sở mục tiêu và bằng chứng khảo sát; phân biệt dữ liệu khảo sát với giả định.
3. Giải pháp: Local Explorer AI như lớp experience/slot trên bản đồ.
4. Demo: câu lệnh tiếng Việt → điểm đi/đến → lịch khả thi → chi tiết có nguồn → replan.
5. Dữ liệu và AI: provenance, giấy phép, freshness; planner quyết định feasibility, AI hỗ trợ ngôn ngữ/xếp hạng/giải thích.
6. Tasco fit: lớp dữ liệu dùng trên bản đồ Việt Nam; trạng thái VMap/T-Maps thật và lộ trình tích hợp.
7. Khả thi, tác động và đo lường: trạng thái prototype, KPI demo/pilot, giới hạn và mô hình mở rộng.
8. Đội ngũ và đề nghị: phân công và API/mentor/credits/dữ liệu cần Ban Tổ chức/Tasco hỗ trợ.

## 18. Đề nghị hỗ trợ từ Tasco và Ban Tổ chức

- Tài liệu, sandbox và quyền truy cập phù hợp cho VMap/T-Maps SDK/API; hướng dẫn attribution, quota và điều kiện dùng trong demo.
- Mẫu tích hợp lớp marker/layer, deep link, geocoding và route API nếu chương trình cung cấp.
- Mentor hoặc kết nối cơ sở địa phương để kiểm tra cách cập nhật dữ liệu.
- Thông tin về credits và API/dữ liệu chương trình cấp, gồm thời hạn và điều khoản.

Challenge Brief cũng đề cập mentor từ Tasco/Mạng lưới AI, credits Codex và Goong.io, cùng API/dữ liệu Ban Tổ chức có thể cung cấp trong phạm vi Hackathon. Đội cần xác nhận quyền được cấp cụ thể trước khi lên kế hoạch phụ thuộc vào chúng.

## 19. Tuyên bố trung thực khi pitch

- Prototype chạy được không đồng nghĩa đã triển khai production.
- Có adapter/config không đồng nghĩa dịch vụ ngoài đã staging-test.
- 177 địa điểm là dữ liệu nhóm thu thập; trạng thái xác nhận phải xét theo từng trường, đặc biệt giá, giờ, slot, capacity và ảnh.
- Challenge Brief cho phép synthetic/mock trong một số trường hợp; nếu dùng, phải gắn nhãn và tách khỏi dữ liệu thật.
- Weak-label đo khả năng khớp quy tắc tạo nhãn, không chứng minh ranker hiểu sở thích du khách.
- Chỉ ghi “đã tích hợp Tasco/VMap/T-Maps” sau khi chạy và lưu kết quả kiểm thử API/SDK thực tế.

## Lời giới thiệu pitch

“Local Explorer AI biến bản đồ thành nơi du khách không chỉ thấy địa điểm mà còn tìm được trải nghiệm phù hợp với thời gian và hành trình của mình. Người dùng nói nhu cầu bằng tiếng Việt, chọn điểm đi và điểm về, rồi hệ thống kiểm tra giờ, ngân sách, slot và tuyến trước khi đề xuất lịch. Mỗi thông tin cho biết nguồn và độ mới; nội dung chưa xác nhận sẽ không bị trình bày như sự thật. Chúng tôi muốn đưa lớp trải nghiệm địa phương này lên bản đồ Việt Nam của Tasco, bắt đầu bằng pilot nhỏ tại Quận 1 và mở rộng khi dữ liệu, đối tác và tích hợp đã được kiểm chứng.”
