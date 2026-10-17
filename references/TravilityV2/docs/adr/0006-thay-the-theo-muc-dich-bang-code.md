# Thay thế theo mục đích bằng code, không bằng LLM

Khi có Disruption (đóng cửa, không thích, mưa, trễ giờ), phương án thay thế do code tìm: lấy ứng viên bằng embedding đã lưu của Place bị mất, lọc bằng các hàm trong `rules.py`, chấm điểm bằng hàm minh bạch, rồi dựng tối đa 3 Proposal qua `build_itinerary`. LLM không chọn phương án và không viết câu giải thích.

Lý do: cần phản hồi dưới 2 giây và chạy được khi mất mạng; kết quả phải xác định để test và để so với baseline B0/B1; hàm điểm cần một chỗ cắm cố định cho ranker ML; và số liệu trong giải thích không được do LLM tự đặt. Đánh đổi: engine chỉ thay từng Stop, không sắp xếp lại cả ngày. Những yêu cầu tự do như "bớt 500k" vẫn đi Revision bằng LLM.
