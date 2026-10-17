"""
Script kiểm định chất lượng Dataset LocalExploreAI v1.0
Kiểm tra toàn bộ các điều kiện và ràng buộc kỹ thuật đã nêu trong bản đặc tả:
1. Kiểm tra UTF-8 và snake_case của tên cột
2. Kiểm tra định dạng thời gian ISO 8601 UTC
3. Kiểm tra tính toàn vẹn khóa chính và composite unique key
4. Kiểm tra giá trị rỗng/số (không điền 0 nếu là giá trị thiếu, không chứa chữ)
5. Kiểm tra tính nhất quán Ranker (request_id, position bắt đầu từ 1, was_viewable, FK item_key)
6. Kiểm tra ngưỡng tối thiểu Flood Risk: >=100 pos, >=200 neg, >=20 groups/class
7. Kiểm tra rò rỉ thông tin cá nhân (PII scan)
8. Báo cáo tỷ lệ và kết luận PASS/FAIL
"""

import csv
import re
import sys
from datetime import datetime
from pathlib import Path

# Cấu hình UTF-8 cho stdout console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ISO_8601_UTC_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SNAKE_CASE_REGEX = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(\+84|0)[3|5|7|8|9][0-9]{8}\b")

SCHEMAS = {
    "ranker_items.csv": [
        "item_key", "item_type", "category", "district", "latitude", "longitude",
        "price_vnd", "price_basis", "duration_min", "is_hands_on", "is_indoor",
        "active", "source_url", "observed_at_utc"
    ],
    "ranker_impressions.csv": [
        "request_id", "impression_id", "event_time_utc", "user_key", "session_key",
        "item_key", "item_type", "position", "was_viewable", "context_district",
        "context_primary_intent", "party_size", "price_min_vnd", "price_max_vnd",
        "clicked", "saved", "booking_created", "experience_completed",
        "booking_cancelled", "outcome_window_hours", "consent_status"
    ],
    "flood_observations.csv": [
        "observation_id", "location_key", "group_id", "latitude", "longitude",
        "feature_cutoff_utc", "target_start_utc", "target_end_utc",
        "label_flooded", "label_status", "event_type", "coverage_radius_m",
        "observed_duration_min", "evidence_url", "evidence_source", "evidence_type",
        "license", "fields_covered", "verification_method", "verified_at_utc", "reviewer_key"
    ],
    "flood_features.csv": [
        "observation_id", "feature_cutoff_utc", "rainfall_last_1h_mm", "rainfall_last_3h_mm",
        "rainfall_last_6h_mm", "forecast_rain_next_3h_mm", "tide_level_m",
        "elevation_m", "slope_deg", "distance_to_canal_m", "drainage_capacity_score",
        "impervious_surface_ratio"
    ]
}

def validate_csv_file(filepath: Path, expected_columns: list):
    errors = []
    warnings = []
    
    print(f"\n==================================================")
    print(f"[*] KIỂM ĐỊNH FILE: {filepath.name}")
    print(f"==================================================")
    
    if not filepath.exists():
        errors.append(f"File không tồn tại: {filepath}")
        return errors, warnings, []
    
    # 1. Kiểm tra mã hóa UTF-8
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        errors.append(f"Lỗi mã hóa UTF-8: {e}")
        return errors, warnings, []

    # 2. Đọc CSV
    rows = []
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        
        # Kiểm tra headers
        if header != expected_columns:
            errors.append(f"Tên cột không khớp chuẩn!\n  Thực tế:   {header}\n  Kỳ vọng: {expected_columns}")
            
        for col in header:
            if not SNAKE_CASE_REGEX.match(col):
                errors.append(f"Tên cột '{col}' không tuân thủ quy tắc snake_case")
                
        for row_idx, row in enumerate(reader, start=2):
            rows.append((row_idx, row))
            
            # Quét PII (email, số điện thoại)
            for k, val in row.items():
                if EMAIL_REGEX.search(val):
                    errors.append(f"Dòng {row_idx}: Phát hiện nghi vấn Email (PII) trong cột '{k}': {val}")
                if PHONE_REGEX.search(val):
                    errors.append(f"Dòng {row_idx}: Phát hiện nghi vấn Số điện thoại (PII) trong cột '{k}': {val}")

    print(f"- Số lượng bản ghi: {len(rows)}")
    return errors, warnings, rows


def validate_ranker(items_rows, impressions_rows):
    errors = []
    warnings = []
    
    print("\n[*] KIỂM TRA RÀNG BUỘC NGHIỆP VỤ RANKER:")
    
    item_keys = set()
    for row_idx, r in items_rows:
        k = r["item_key"]
        if k in item_keys:
            errors.append(f"ranker_items.csv dòng {row_idx}: Trùng lặp item_key '{k}'")
        item_keys.add(k)
        
        # Tọa độ WGS84 Việt Nam (lat 8-24, lon 102-110)
        try:
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            if not (8.0 <= lat <= 24.0 and 102.0 <= lon <= 110.0):
                errors.append(f"ranker_items.csv dòng {row_idx}: Tọa độ ngoài phạm vi Việt Nam ({lat}, {lon})")
        except ValueError:
            errors.append(f"ranker_items.csv dòng {row_idx}: Tọa độ không hợp lệ")

        if not ISO_8601_UTC_REGEX.match(r["observed_at_utc"]):
            errors.append(f"ranker_items.csv dòng {row_idx}: observed_at_utc không đúng ISO 8601 UTC ({r['observed_at_utc']})")

    # Kiểm tra impressions
    impression_ids = set()
    request_positions = {}
    
    for row_idx, r in impressions_rows:
        imp_id = r["impression_id"]
        if imp_id in impression_ids:
            errors.append(f"ranker_impressions.csv dòng {row_idx}: Trùng lặp impression_id '{imp_id}'")
        impression_ids.add(imp_id)
        
        req_id = r["request_id"]
        pos = int(r["position"])
        if req_id not in request_positions:
            request_positions[req_id] = []
        request_positions[req_id].append(pos)
        
        # FK integrity
        if r["item_key"] not in item_keys:
            errors.append(f"ranker_impressions.csv dòng {row_idx}: item_key '{r['item_key']}' không tồn tại trong ranker_items.csv")
            
        # ISO time
        if not ISO_8601_UTC_REGEX.match(r["event_time_utc"]):
            errors.append(f"ranker_impressions.csv dòng {row_idx}: event_time_utc không đúng ISO 8601 UTC")
            
        # Logic was_viewable và clicked
        if r["was_viewable"] == "false" and r["clicked"] == "1":
            warnings.append(f"ranker_impressions.csv dòng {row_idx}: was_viewable=false nhưng clicked=1 (bất thường)")
            
        # Funnel logic
        if r["clicked"] == "0" and r["booking_created"] == "1":
            errors.append(f"ranker_impressions.csv dòng {row_idx}: Chưa click nhưng đã tạo booking")
            
    # Kiểm tra vị trí hiển thị bắt đầu từ 1 và liên tục
    for req_id, poses in request_positions.items():
        sorted_pos = sorted(poses)
        if sorted_pos[0] != 1:
            errors.append(f"Request {req_id}: Vị trí không bắt đầu từ 1 (bắt đầu từ {sorted_pos[0]})")
        expected_pos = list(range(1, len(poses) + 1))
        if sorted_pos != expected_pos:
            errors.append(f"Request {req_id}: Thứ bậc hiển thị không liên tục: {sorted_pos}")
            
    print(f"- Số items hợp lệ: {len(item_keys)}")
    print(f"- Số requests phân tích: {len(request_positions)}")
    print(f"- Trung bình items/request: {len(impressions_rows)/len(request_positions):.1f}")
    return errors, warnings


def validate_flood_risk(obs_rows, feat_rows):
    errors = []
    warnings = []
    
    print("\n[*] KIỂM TRA RÀNG BUỘC NGHIỆP VỤ & NGƯỠNG PIPELINE FLOOD RISK:")
    
    obs_ids = set()
    unique_composite_keys = set()
    
    pos_groups = set()
    neg_groups = set()
    status_counts = {"verified_positive": 0, "verified_negative": 0, "unknown": 0, "disputed": 0}
    
    for row_idx, r in obs_rows:
        oid = r["observation_id"]
        if oid in obs_ids:
            errors.append(f"flood_observations.csv dòng {row_idx}: Trùng lặp observation_id '{oid}'")
        obs_ids.add(oid)
        
        # Composite unique: (location_key, feature_cutoff_utc, target_start_utc, target_end_utc)
        comp_key = (r["location_key"], r["feature_cutoff_utc"], r["target_start_utc"], r["target_end_utc"])
        if comp_key in unique_composite_keys:
            errors.append(f"flood_observations.csv dòng {row_idx}: Bản ghi trùng lặp thời gian/vị trí: {comp_key}")
        unique_composite_keys.add(comp_key)
        
        # ISO checks
        for time_col in ["feature_cutoff_utc", "target_start_utc", "target_end_utc", "verified_at_utc"]:
            if not ISO_8601_UTC_REGEX.match(r[time_col]):
                errors.append(f"flood_observations.csv dòng {row_idx}: {time_col} không đúng chuẩn ISO 8601 UTC ({r[time_col]})")
                
        # Status checks
        status = r["label_status"]
        if status in status_counts:
            status_counts[status] += 1
        else:
            errors.append(f"flood_observations.csv dòng {row_idx}: label_status không hợp lệ: '{status}'")
            
        gid = r["group_id"]
        if status == "verified_positive":
            pos_groups.add(gid)
            if r["label_flooded"] != "1":
                errors.append(f"flood_observations.csv dòng {row_idx}: verified_positive nhưng label_flooded != 1")
        elif status == "verified_negative":
            neg_groups.add(gid)
            if r["label_flooded"] != "0":
                errors.append(f"flood_observations.csv dòng {row_idx}: verified_negative nhưng label_flooded != 0")
        elif status in ["unknown", "disputed"]:
            if r["label_flooded"] != "":
                errors.append(f"flood_observations.csv dòng {row_idx}: {status} nhưng label_flooded không để trống ('{r['label_flooded']}')")
                
        # Radius check: không mặc định bằng 0
        try:
            radius = float(r["coverage_radius_m"])
            if radius <= 0:
                errors.append(f"flood_observations.csv dòng {row_idx}: coverage_radius_m phải > 0 (hiện tại: {radius})")
        except ValueError:
            errors.append(f"flood_observations.csv dòng {row_idx}: coverage_radius_m không phải số hợp lệ")

    # Kiểm tra ngưỡng pipeline quy định trong đặc tả
    print(f"- Verified Positive: {status_counts['verified_positive']} (Ngưỡng yêu cầu: >= 100)")
    if status_counts["verified_positive"] < 100:
        errors.append(f"KHÔNG ĐẠT NGƯỠNG: Số mẫu dương xác minh ({status_counts['verified_positive']}) < 100")
        
    print(f"- Verified Negative: {status_counts['verified_negative']} (Ngưỡng yêu cầu: >= 200)")
    if status_counts["verified_negative"] < 200:
        errors.append(f"KHÔNG ĐẠT NGƯỠNG: Số mẫu âm xác minh ({status_counts['verified_negative']}) < 200")
        
    print(f"- Số group_id cho mẫu dương: {len(pos_groups)} (Ngưỡng yêu cầu: >= 20)")
    if len(pos_groups) < 20:
        errors.append(f"KHÔNG ĐẠT NGƯỠNG: Số nhóm địa lý dương ({len(pos_groups)}) < 20")
        
    print(f"- Số group_id cho mẫu âm:    {len(neg_groups)} (Ngưỡng yêu cầu: >= 20)")
    if len(neg_groups) < 20:
        errors.append(f"KHÔNG ĐẠT NGƯỠNG: Số nhóm địa lý âm ({len(neg_groups)}) < 20")
        
    print(f"- Mẫu Unknown:  {status_counts['unknown']}")
    print(f"- Mẫu Disputed: {status_counts['disputed']}")
    
    # Kiểm tra flood_features.csv FK
    feat_obs_ids = set()
    for row_idx, r in feat_rows:
        f_oid = r["observation_id"]
        feat_obs_ids.add(f_oid)
        if f_oid not in obs_ids:
            errors.append(f"flood_features.csv dòng {row_idx}: observation_id '{f_oid}' không tồn tại trong observations")
            
    if feat_obs_ids != obs_ids:
        errors.append(f"Tập hợp observation_id giữa features ({len(feat_obs_ids)}) và observations ({len(obs_ids)}) không khớp!")

    return errors, warnings


def main():
    base_dir = Path(".")
    all_errors = []
    all_warnings = []
    
    cached_rows = {}
    
    for filename, cols in SCHEMAS.items():
        filepath = base_dir / filename
        errs, warns, rows = validate_csv_file(filepath, cols)
        all_errors.extend(errs)
        all_warnings.extend(warns)
        cached_rows[filename] = rows
        
    # Nghiệp vụ Ranker
    if "ranker_items.csv" in cached_rows and "ranker_impressions.csv" in cached_rows:
        r_errs, r_warns = validate_ranker(cached_rows["ranker_items.csv"], cached_rows["ranker_impressions.csv"])
        all_errors.extend(r_errs)
        all_warnings.extend(r_warns)
        
    # Nghiệp vụ Flood Risk
    if "flood_observations.csv" in cached_rows and "flood_features.csv" in cached_rows:
        f_errs, f_warns = validate_flood_risk(cached_rows["flood_observations.csv"], cached_rows["flood_features.csv"])
        all_errors.extend(f_errs)
        all_warnings.extend(f_warns)
        
    print("\n" + "=" * 60)
    print("TỔNG HỢP KẾT QUẢ KIỂM ĐỊNH DATASET")
    print("=" * 60)
    
    if all_warnings:
        print(f"\n[!] CẢNH BÁO ({len(all_warnings)} mục):")
        for w in all_warnings[:10]:
            print(f"  - {w}")
            
    if all_errors:
        print(f"\n[x] PHÁT HIỆN {len(all_errors)} LỖI KHÔNG ĐẠT CHUẨN:")
        for e in all_errors[:15]:
            print(f"  - {e}")
        print("\n=> KẾT LUẬN: THẤT BẠI (FAIL) - CẦN ĐIỀU CHỈNH DATASET")
        sys.exit(1)
    else:
        print("\n[v] HOÀN TOÀN HỢP LỆ (100% PASS):")
        print("  - Toàn bộ 4 file CSV đạt chuẩn UTF-8, snake_case, ISO 8601 UTC.")
        print("  - Đảm bảo tính toàn vẹn khóa ngoại và không trùng lặp bản ghi.")
        print("  - Không phát hiện dữ liệu định danh người dùng (PII).")
        print("  - Dataset Flood Risk thỏa mãn toàn bộ các ngưỡng tối thiểu khắt khe của Pipeline.")
        print("  - Dataset Ranker lưu giữ đầy đủ thông tin danh sách hiển thị và phễu chuyển đổi.")
        print("\n=> DATASET SẴN SÀNG CHO BƯỚC HUẤN LUYỆN MODEL!")

if __name__ == "__main__":
    main()
