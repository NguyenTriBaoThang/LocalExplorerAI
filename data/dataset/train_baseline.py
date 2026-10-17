"""
Script huấn luyện Model mẫu (Baseline) cho Ranker và Flood Risk — LocalExploreAI
Sử dụng LightGBM và Scikit-Learn trên tập dữ liệu đã chuẩn hóa:
1. Ranker: Huấn luyện LambdaMART (LGBMRanker) với nhóm theo request_id
   - Đánh giá bằng NDCG@3, NDCG@5, NDCG@10
2. Flood Risk: Huấn luyện Gradient Boosting Classifier trên tập nhãn đã xác minh
   - Phân chia tập huấn luyện bằng GroupKFold theo group_id (tránh rò rỉ không gian)
   - Kiểm tra các ngưỡng kiểm định của pipeline:
     + Average Precision >= 0.50
     + Brier Score <= 0.20
     + Recall >= 0.80
"""

import sys
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, recall_score, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
import lightgbm as lgb

# Cấu hình UTF-8 cho console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def train_ranker_model():
    print("\n" + "=" * 60)
    print("[1] HUẤN LUYỆN MODEL RANKER (LambdaMART / LGBMRanker)")
    print("=" * 60)
    
    # 1. Đọc dữ liệu
    df_imp = pd.read_csv("ranker_impressions.csv")
    df_items = pd.read_csv("ranker_items.csv")
    
    # Nối với bảng thuộc tính POI/trải nghiệm
    df_merged = pd.merge(df_imp, df_items, on="item_key", how="left", suffixes=("", "_item"))
    
    # 2. Xây dựng nhãn mục tiêu (Relevance Grade):
    # - 0: Không tương tác
    # - 1: Đã click
    # - 2: Đã lưu (saved)
    # - 3: Đã tạo booking (booking_created)
    def calc_relevance(row):
        if row["booking_created"] == 1:
            return 3
        if row["saved"] == 1:
            return 2
        if row["clicked"] == 1:
            return 1
        return 0

    df_merged["relevance_grade"] = df_merged.apply(calc_relevance, axis=1)
    
    # 3. Tạo đặc trưng (Feature Engineering)
    df_merged["match_district"] = (df_merged["context_district"] == df_merged["district"]).astype(int)
    df_merged["is_viewable_num"] = (df_merged["was_viewable"] == "true").astype(int)
    df_merged["price_clean"] = pd.to_numeric(df_merged["price_vnd"], errors="coerce").fillna(0)
    df_merged["duration_clean"] = pd.to_numeric(df_merged["duration_min"], errors="coerce").fillna(60)
    df_merged["is_hands_on_num"] = (df_merged["is_hands_on"] == "true").astype(int)
    df_merged["is_indoor_num"] = (df_merged["is_indoor"] == "true").astype(int)
    df_merged["party_size_clean"] = pd.to_numeric(df_merged["party_size"], errors="coerce").fillna(1)
    
    feature_cols = [
        "position", "is_viewable_num", "match_district", "price_clean",
        "duration_clean", "is_hands_on_num", "is_indoor_num", "party_size_clean"
    ]
    
    # 4. Chia Train / Test theo danh sách request_id để giữ nguyên list ranking
    unique_requests = df_merged["request_id"].unique()
    np.random.seed(42)
    test_reqs = set(np.random.choice(unique_requests, size=int(len(unique_requests) * 0.25), replace=False))
    
    train_df = df_merged[~df_merged["request_id"].isin(test_reqs)].sort_values(by="request_id")
    test_df = df_merged[df_merged["request_id"].isin(test_reqs)].sort_values(by="request_id")
    
    X_train = train_df[feature_cols]
    y_train = train_df["relevance_grade"]
    groups_train = train_df.groupby("request_id").size().values
    
    X_test = test_df[feature_cols]
    y_test = test_df["relevance_grade"]
    groups_test = test_df.groupby("request_id").size().values
    
    print(f"- Số request huấn luyện: {len(groups_train)} ({len(train_df)} impressions)")
    print(f"- Số request kiểm thử:   {len(groups_test)} ({len(test_df)} impressions)")
    
    # 5. Khởi tạo và huấn luyện LGBMRanker
    ranker = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        eval_at=[3, 5, 10],
        n_estimators=60,
        learning_rate=0.08,
        random_state=42,
        verbose=-1
    )
    
    ranker.fit(
        X_train, y_train,
        group=groups_train,
        eval_set=[(X_test, y_test)],
        eval_group=[groups_test],
        callbacks=[lgb.log_evaluation(period=0)]
    )
    
    # 6. Đánh giá xếp hạng trên tập test
    test_df = test_df.copy()
    test_df["pred_score"] = ranker.predict(X_test)
    
    # Tính NDCG thủ công cho tập test
    def dcg_at_k(r, k):
        r = np.asarray(r, dtype=float)[:k]
        if r.size:
            return np.sum((2**r - 1) / np.log2(np.arange(2, r.size + 2)))
        return 0.0

    def ndcg_at_k(r, k):
        dcg_max = dcg_at_k(sorted(r, reverse=True), k)
        if not dcg_max:
            return 1.0
        return dcg_at_k(r, k) / dcg_max

    ndcg_3_list, ndcg_5_list = [], []
    for req_id, group in test_df.groupby("request_id"):
        # Sắp xếp theo điểm dự đoán giảm dần
        sorted_labels = group.sort_values(by="pred_score", ascending=False)["relevance_grade"].values
        ndcg_3_list.append(ndcg_at_k(sorted_labels, 3))
        ndcg_5_list.append(ndcg_at_k(sorted_labels, 5))
        
    print(f"\n=> KẾT QUẢ ĐÁNH GIÁ RANKER:")
    print(f"  * NDCG@3 trung bình: {np.mean(ndcg_3_list):.4f}")
    print(f"  * NDCG@5 trung bình: {np.mean(ndcg_5_list):.4f}")
    print("  * Top features quan trọng:")
    importances = pd.Series(ranker.feature_importances_, index=feature_cols).sort_values(ascending=False)
    for col, imp in importances.items():
        print(f"    - {col:18s}: {imp}")


def train_flood_risk_model():
    print("\n" + "=" * 60)
    print("[2] HUẤN LUYỆN MODEL FLOOD RISK (Gradient Boosting Classifier)")
    print("=" * 60)
    
    # 1. Đọc dữ liệu
    df_obs = pd.read_csv("flood_observations.csv")
    df_feat = pd.read_csv("flood_features.csv")
    
    # 2. Quy tắc nhãn: Chỉ dùng 2 trạng thái verified (verified_positive và verified_negative)
    valid_mask = df_obs["label_status"].isin(["verified_positive", "verified_negative"])
    df_valid_obs = df_obs[valid_mask].copy()
    
    print(f"- Tổng số quan sát: {len(df_obs)}")
    print(f"- Số mẫu đã xác minh hợp lệ (verified): {len(df_valid_obs)}")
    print(f"  + Dương tính (Ngập): {sum(df_valid_obs['label_flooded'] == 1)}")
    print(f"  + Âm tính (Không ngập): {sum(df_valid_obs['label_flooded'] == 0)}")
    
    # 3. Nối với tập đặc trưng
    data = pd.merge(df_valid_obs, df_feat, on="observation_id", how="inner")
    
    feature_cols = [
        "rainfall_last_1h_mm", "rainfall_last_3h_mm", "rainfall_last_6h_mm",
        "forecast_rain_next_3h_mm", "tide_level_m", "elevation_m",
        "slope_deg", "distance_to_canal_m", "drainage_capacity_score",
        "impervious_surface_ratio"
    ]
    
    X = data[feature_cols].copy()
    y = data["label_flooded"].astype(int).values
    groups = data["group_id"].values
    
    # 4. Phân chia tập huấn luyện theo group_id (GroupKFold) nhằm triệt tiêu rò rỉ địa lý
    gkf = GroupKFold(n_splits=5)
    
    ap_scores = []
    brier_scores = []
    recall_scores = []
    auc_scores = []
    
    fold = 1
    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        clf = lgb.LGBMClassifier(
            n_estimators=80,
            learning_rate=0.05,
            num_leaves=15,
            random_state=42 + fold,
            verbose=-1
        )
        clf.fit(X_train, y_train)
        
        y_prob = clf.predict_proba(X_test)[:, 1]
        
        # Ngưỡng quyết định cảnh báo rủi ro ngập (chọn 0.40 để tối ưu độ nhạy cảnh báo sớm)
        y_pred = (y_prob >= 0.40).astype(int)
        
        ap = average_precision_score(y_test, y_prob)
        brier = brier_score_loss(y_test, y_prob)
        rec = recall_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_prob)
        
        ap_scores.append(ap)
        brier_scores.append(brier)
        recall_scores.append(rec)
        auc_scores.append(auc)
        fold += 1
        
    mean_ap = np.mean(ap_scores)
    mean_brier = np.mean(brier_scores)
    mean_recall = np.mean(recall_scores)
    mean_auc = np.mean(auc_scores)
    
    print("\n" + "-" * 50)
    print("KẾT QUẢ ĐÁNH GIÁ FLOOD RISK (5-Fold Cross-Group Validation)")
    print("-" * 50)
    print(f"1. Average Precision (PR-AUC): {mean_ap:.4f}  | Ngưỡng pipeline: >= 0.50 -> {'ĐẠT' if mean_ap >= 0.50 else 'CHƯA ĐẠT'}")
    print(f"2. Brier Score (Độ sai lệch):   {mean_brier:.4f}  | Ngưỡng pipeline: <= 0.20 -> {'ĐẠT' if mean_brier <= 0.20 else 'CHƯA ĐẠT'}")
    print(f"3. Recall (Độ nhạy phát hiện): {mean_recall:.4f}  | Ngưỡng pipeline: >= 0.80 -> {'ĐẠT' if mean_recall >= 0.80 else 'CHƯA ĐẠT'}")
    print(f"4. ROC-AUC:                    {mean_auc:.4f}")
    
    # Feature importance
    print("\n* Trọng số đóng góp của các đặc trưng khí tượng/thủy văn/địa hình:")
    clf.fit(X, y)
    feat_imp = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    for col, imp in feat_imp.items():
        print(f"  - {col:26s}: {imp}")


def main():
    train_ranker_model()
    train_flood_risk_model()
    print("\n" + "=" * 60)
    print("[v] HOÀN TẤT HUẤN LUYỆN VÀ KIỂM CHỨNG TOÀN DIỆN!")
    print("=" * 60)

if __name__ == "__main__":
    main()
