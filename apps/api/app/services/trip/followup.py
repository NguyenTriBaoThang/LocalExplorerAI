"""Tin nhắn tiếp theo trên Trip đã có lịch trình: trả lời, sửa bằng thao tác, hoặc xin lập lại (#22)."""
from app.services.trip.domain import Trip

CHANGEABLE = ("days", "start_date", "budget", "travelers", "required_tags", "preferred_tags", "avoided_tags", "pace",
              "travel_mode", "arrival_mode", "arrival_time", "departure_time", "last_day_end")


def changed_trip(trip: Trip, changes: dict) -> Trip:
    """Trip sau khi áp changes (chỉ trường CHANGEABLE); ValidationError nếu giá trị sai."""
    return Trip.model_validate(trip.model_dump() | {k: v for k, v in changes.items() if k in CHANGEABLE})
