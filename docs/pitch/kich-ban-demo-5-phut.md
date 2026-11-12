# Kịch bản demo 5 phút — AI Quote & Margin Copilot

> Dành cho người thuyết trình và người thao tác máy. Kịch bản này viết theo sản phẩm **khi hoàn thành đủ các module**. Những con số để trong `[ ]` phải lấy từ hệ thống lúc tổng duyệt, **không được tự đặt**.

## Chuẩn bị trước giờ demo

- [ ] Chạy `docker compose up`, sau đó chạy seed dữ liệu demo (công ty "Saigon Group Tours", bảng giá mẫu, tour mẫu).
- [ ] Mở sẵn 4 tab:
  1. Portal, đăng nhập bằng tài khoản operator, ở trang **Báo giá**.
  2. Zalo hoặc Telegram trên điện thoại, đã chiếu lên màn hình.
  3. Một tab ẩn danh để mở link báo giá như khách hàng.
  4. Trang **ROI**.
- [ ] Để sẵn file `bang-gia-nha-xe-2026.xlsx` (bảng giá NET mẫu) và `hoa-don-nha-xe.jpg` (hóa đơn mẫu) ngoài Desktop.
- [ ] Copy sẵn tin nhắn khách vào clipboard (xem Cảnh 2).
- [ ] Cổng VNPay ở chế độ sandbox; thử trước 1 lần thanh toán.
- [ ] **Phương án dự phòng:** quay sẵn video toàn bộ luồng. Nếu mạng hoặc LLM lỗi, chuyển sang video và tiếp tục nói.

## Phân vai

- **Người nói (A):** kể chuyện, nhìn giám khảo.
- **Người thao tác (B):** chỉ bấm, không nói. B làm theo câu nhắc in đậm của A.

---

## Cảnh 1 — Nỗi đau (0:00 – 0:40)

**Màn hình:** slide có 3 con số.

**A nói:**
> "Một công ty lữ hành nhỏ ở Sài Gòn nhận mỗi ngày vài chục tin nhắn hỏi giá tour đoàn. Mỗi báo giá, sales mất 45 phút đến 2 tiếng để tra giá xe, khách sạn, nhà hàng rồi cộng Excel. Trả lời chậm thì mất khách: đại lý mất 40–60% yêu cầu vì phản hồi sau 1–2 ngày. Còn khi đã chốt, khách đổi số người, nhà xe tăng giá, phụ thu lễ… lãi 25% có thể còn 5% mà không ai biết cho tới khi hóa đơn về.
> Hôm nay chúng em cho thấy AI xử lý toàn bộ chuyện đó trong vài phút."

---

## Cảnh 2 — Từ tin nhắn đến báo giá (0:40 – 2:10) ⭐ cảnh chính

**B:** chuyển sang điện thoại, gửi tin nhắn cho bot Zalo:
> *"Chào bên mình, công ty em 32 người muốn đi Củ Chi – Mekong 2 ngày 1 đêm, khởi hành 30/4, ngân sách tầm 2 triệu/người. Báo giá giúp em nhé."*

**A nói:** "Khách nhắn lúc nửa đêm cũng được. Bot nhận tin và trả lời ngay là đang soạn báo giá."

**B:** chuyển sang portal. Bản nháp vừa xuất hiện trong danh sách → **bấm mở**.

**A chỉ lần lượt từng phần trên màn hình:**
1. **AI đã hiểu yêu cầu:** 32 khách, 2 ngày, ngày đi 30/4, phân khúc công ty.
   > "Không có form nào cả. AI đọc tiếng Việt tự nhiên."
2. **Lịch trình:** lấy từ tour mẫu của công ty và đã được chỉnh lại; giờ giấc và quãng đường khả thi.
3. **Bảng giá vốn:**
   - xe được chọn **[xe 45 chỗ]**, HDV, 4 bữa, vé, **[16]** phòng;
   - có dòng phụ thu lễ 30/4 tô vàng.
   > "Từng đồng ở đây lấy từ bảng giá nhà cung cấp, tính bằng công thức. AI không đoán giá vốn."
4. **Ba mức giá:**
   - An toàn: **[giá] – [P]% chốt**
   - Cân bằng: **[giá] – [P]%**
   - Tối đa lãi: **[giá] – [P]%**

   > "Đây là phần AI định giá động. Mô hình học máy dự đoán khả năng khách chốt ở mỗi mức giá, dựa trên mùa, lễ, cỡ đoàn, thời điểm đặt. Hệ thống chọn mức có lãi kỳ vọng cao nhất, và không bao giờ thấp hơn sàn lãi của công ty."
5. **Biểu đồ đường giá** (B rê chuột).
   > "Giá càng cao thì xác suất chốt càng thấp. Điểm đỉnh là chỗ lãi kỳ vọng lớn nhất."

**B:** bấm **Cân bằng** → **Gửi khách**.

**A nói:** "Từ lúc khách nhắn đến lúc có báo giá: **[thời gian thực tế]**, thay vì 1–2 tiếng."

---

## Cảnh 3 — Khách chốt và đặt cọc (2:10 – 2:50)

**B:** mở link báo giá ở tab ẩn danh.

**A nói:** "Khách nhận một link: lịch trình, bản đồ, giá, có in ra PDF được."

**B:** bấm **Chấp nhận & đặt cọc** → VNPay sandbox → thanh toán thành công → quay về portal: trạng thái báo giá là **Đã cọc**.

**A nói:** "Khách đặt cọc thẳng cho công ty, không qua OTA nên không mất 20–25% hoa hồng."

---

## Cảnh 4 — Canh lỗ ngầm (2:50 – 3:50)

**A nói:** "Giờ đến chuyện hay xảy ra ngoài đời: nhà xe gửi bảng giá mới, tăng giá dịp lễ."

**B:** vào **Bảng giá** → upload `bang-gia-nha-xe-2026.xlsx`.

**A nói:** "AI đọc file Excel, hoặc thậm chí ảnh chụp bảng giá, và chuyển thành bảng có cấu trúc. Ô nào AI không chắc thì tô màu để người kiểm tra."

**B:** bấm **Duyệt** → quay lại báo giá vừa chốt → hiện **banner đỏ: lãi còn [x]%, dưới sàn [15]%**.

**A nói:** "Hệ thống tự tính lại mọi báo giá đang mở dùng nhà xe này và cảnh báo ngay, không phải đợi hóa đơn về mới biết lỗ."

**B:** mở **Gợi ý cứu lãi**.

**A đọc 2 phương án trên màn hình:**
> "[Đổi sang 2 xe 29 chỗ, tiết kiệm X đồng]. [Dùng nhà xe B, tiết kiệm Y đồng]. Mỗi con số là hệ thống tính lại thật, AI chỉ diễn giải."

**B:** bấm **Áp dụng** → lãi trở lại trên sàn.

---

## Cảnh 5 — Sau tour (3:50 – 4:20)

**B:** vào **Đối chiếu** → upload `hoa-don-nha-xe.jpg`.

**A nói:** "Sau tour, AI đọc hóa đơn thật và so với dự toán, chỉ ra khoản nào lệch và vì sao: đổi số khách, tăng giá, hay phát sinh ngoài kế hoạch. Quản lý nhìn dashboard là biết lãi thật từng đoàn."

---

## Cảnh 6 — Giá trị kinh doanh (4:20 – 5:00)

**B:** mở trang **ROI**.

**A nói (chỉ từng thẻ):**
> "Với dữ liệu demo:
> - thời gian phản hồi trung vị **[x phút]**;
> - tiết kiệm **[y giờ công]**;
> - lãi so với cách định giá cố định: **[+z%]** trên backtest;
> - hoa hồng OTA tránh được **[w triệu]**.
>
> Lưu ý, phần định giá được kiểm chứng trên dữ liệu giả lập mà chúng em công bố đầy đủ quy luật. Nó chứng minh phương pháp; với doanh nghiệp thật, mô hình sẽ học lại từ dữ liệu của chính họ.
>
> **AI Quote & Margin Copilot: báo giá trong vài phút, định giá có cơ sở, không còn lỗ ngầm.** Cảm ơn ban giám khảo."

---

## Nếu sự cố xảy ra

| Sự cố | Xử lý |
|---|---|
| Bot Zalo không nhận tin | B dán tin nhắn vào ô **Tạo báo giá** trên portal; A nói "sales cũng có thể dán tin trực tiếp". |
| LLM chậm hoặc lỗi | Mở báo giá đã tạo sẵn trước giờ demo; nếu cần, chuyển sang video dự phòng. |
| VNPay sandbox lỗi | Bỏ qua bước thanh toán; A nói "khách đặt cọc qua VNPay/MoMo" và chuyển sang Cảnh 4. |
| Upload file lỗi | Dùng bảng giá đã duyệt sẵn bản v2, bấm thẳng **Duyệt**. |
| Hết giờ | Bỏ Cảnh 5, nói 1 câu về đối chiếu hóa đơn trong Cảnh 6. |

## Câu hỏi giám khảo hay hỏi — trả lời ngắn

- **"Dữ liệu giả thì tin sao được?"** → Quy luật sinh dữ liệu công bố đầy đủ; bọn em kiểm chứng phương pháp bằng backtest; với khách thật thì huấn luyện lại trên lịch sử báo giá của họ.
- **"AI có bịa giá không?"** → Không. Giá vốn tính bằng công thức từ bảng giá đã duyệt; giá bán do mô hình và tối ưu quyết định; AI chỉ đọc hiểu và giải thích, có cơ chế chặn số lạ.
- **"Khác gì phần mềm báo giá hiện có?"** → Ba điểm: định giá theo xác suất chốt, canh lãi suốt vòng đời tour, và hợp bối cảnh Việt Nam (Zalo, VNPay/MoMo, lễ âm lịch).
- **"Ai trả tiền?"** → Công ty lữ hành trả phí thuê bao theo số người dùng; giá trị đo trực tiếp bằng giờ công tiết kiệm và lãi tăng.
