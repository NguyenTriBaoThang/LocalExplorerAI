class ExplanationService:
    friendly_reasons = {
        "INTENT_MATCH": "Phù hợp với mục đích chuyến đi bạn đã chọn.",
        "WITHIN_BUDGET": "Chi phí ước tính nằm trong ngân sách.",
        "SLOT_AVAILABLE": "Khung giờ phù hợp tại thời điểm lập lịch; đây chưa phải booking.",
        "CAPACITY_UNKNOWN": "Sức chứa chưa được xác nhận; cần liên hệ nhà cung cấp.",
        "MOCK_ROUTING": "Thời gian di chuyển là ước tính mô phỏng, không phải dữ liệu giao thông thực.",
        "GOONG_ROUTING": "Khoảng cách và thời lượng lấy từ Goong; ETA là ước tính, không phải giao thông thời gian thực.",
        "SIMULATED_DATA": "Địa điểm, giá và khung giờ trong bản demo là dữ liệu mô phỏng.",
        "VERIFIED_DATA": "Địa điểm, hoạt động và khung giờ có nguồn đã duyệt, còn hiệu lực tại thời điểm lập lịch.",
        "STALE_DATA": "Một phần bằng chứng dữ liệu đã cũ hoặc hết hạn; cần xác minh lại.",
        "UNVERIFIED_DATA": "Một phần dữ liệu chưa được xác minh nguồn.",
        "LOCKED_ACTIVITY": "Hoạt động bạn khóa đã được giữ lại.",
        "COMMUNITY_RATING_SIGNAL": "Điểm sao cộng đồng là tín hiệu phụ được làm trơn theo số lượt đánh giá; các ràng buộc khả thi vẫn được kiểm tra riêng.",
        "WEATHER_FORECAST_USED": "Dùng dự báo mưa theo ngày từ Open-Meteo để Ranker cân nhắc trải nghiệm trong nhà và ngoài trời.",
        "RAIN_FORECAST": "Dự báo có mưa; trải nghiệm trong nhà có thể được ưu tiên hơn.",
        "WEATHER_FORECAST_UNAVAILABLE": "Không lấy được dự báo cho ngày đi; thời tiết không được dùng để xếp hạng.",
    }

    def explain(self, reason_codes: list[str], preserved: list[str], lost: list[str]) -> dict:
        return {
            "preserved_intents": preserved,
            "lost_intents": lost,
            "reason_codes": reason_codes,
            "evidence_refs": [],
            "uncertainty": [self.friendly_reasons[code] for code in reason_codes if code in {"CAPACITY_UNKNOWN", "MOCK_ROUTING", "GOONG_ROUTING", "SIMULATED_DATA", "STALE_DATA", "UNVERIFIED_DATA", "RAIN_FORECAST", "WEATHER_FORECAST_UNAVAILABLE"}],
        }
