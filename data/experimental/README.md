# Experimental datasets

The [ranking experiment](ranking/README.md) is a separate POI/category weak-label task. It is not flood data and must not be described as human preference or planner-verified ranking evidence.

## Weak labels for public flood-report occurrence

> **Tóm tắt (Vietnamese Summary):**
> Tập tin `flood_training_weak_labels.csv` là sản phẩm dẫn xuất phục vụ mục đích nghiên cứu từ bộ dữ liệu báo cáo ngập lụt lịch sử TP.HCM. Mục tiêu dự đoán ở đây là **xác suất xuất hiện bản ghi báo cáo ngập lụt công khai** cho một địa danh cụ thể trong một tháng theo lịch, chứ **không phải** dự đoán tuyến đường đó có bị ngập nước vật lý hay không. File gồm 662 dòng cân bằng (331 quan sát dương bản + 331 giả định âm bản có trọng số sampling). Tuyệt đối không dùng file này để gán nhãn an toàn tuyến đường thực tế.

`flood_training_weak_labels.csv` is a research-only derivative of the public
HCMC historical flood-report dataset. Its target is whether that source contains
a flood-report record for a named location in a calendar month. The target is
not whether the road was physically flooded.

## Label construction

- `target_public_report_present = 1` (`documented_report`) when one or more
  source rows match the exact location name, location type, administrative-area
  key, year, and month.
- `target_public_report_present = 0` (`pseudo_no_matching_record`) for a
  sampled month with no matching source row, drawn from the same location-year
  group that has at least one reported month. These are weak pseudo-negatives.
  They do not mean the location was observed dry.
- The file is balanced by sampling as many pseudo-negative months as positive
  location-months within each eligible location-year. The fixed seed is
  recorded in each pseudo-negative row. `case_control_sampling_weight`
  records the inverse sampling fraction for the selected pseudo-negatives.
- Rows with a year-only report are not used to create monthly examples. The
  whole location-year is excluded from negative sampling when it has any such
  row, since its unknown month could overlap a would-be pseudo-negative.
- Rows whose exact `Date` conflicts with the source `Year` are excluded, and
  both affected location-years are excluded from negative sampling.
- `audit_*` columns preserve the source observations behind positive labels.
  They are for traceability and must not be used as model features.

The source has 425 observations. The current build excludes 63 rows with no
exact date and one row whose `Date` conflicts with `Year`. It also excludes
affected location-years from negative sampling. It retains 331 positive
location-months, samples 331 pseudo-negatives from 3,521 candidates, and
contains 662 rows in total. The source is based mainly on news reports, and
its spatial and temporal coverage depends on source availability and
reliability. Unreported months can contain real floods.

## Intended use and limits

This file can support an experiment about **public-report occurrence** and
labeling/sampling behavior. It cannot validate or train the project's
street/time flood-risk target as currently defined. It has no verified
no-flood observations, project `edge_id`, decision timestamp, or forecast
horizon. Do not pass it to the verified-label Flood Colab notebook or use a
model trained on it to mark a route safe or unsafe.

To run the separate experiment, open
[`notebooks/LocalExplorerAI_Flood_Report_Weak_Label_Experiment_Colab.ipynb`](../../notebooks/LocalExplorerAI_Flood_Report_Weak_Label_Experiment_Colab.ipynb)
in Google Colab and upload this CSV when prompted, or place it in Drive at
`MyDrive/LocalExplorerAI/dataset/experimental/flood_training_weak_labels.csv`.
The notebook writes a research-only artifact under
`MyDrive/LocalExplorerAI/models/flood-report-experiment/`; it is deliberately
not compatible with, and must not be copied into, `models/flood-risk/`.
The artifact supplied with this project is kept locally in
`models/flood-report-experiment/` and is not loaded by the API.

To regenerate it from the unchanged raw CSV, run from the repository root:

```powershell
node scripts/build_flood_report_weak_labels.mjs
```

The generator refuses to replace an existing output unless `--force` is
provided.

## Source and attribution

Hardy, Sebastien; Radziute, Gintarė (2026), *Historical database of urban
flooding in Ho Chi Minh City, Vietnam (2002–2026)*, DataSuds, DOI
[`10.23708/8Y16HU`](https://doi.org/10.23708/8Y16HU). The dataset landing page
states CC BY-NC 4.0, while the ReadMe included in the supplied ZIP states
CC BY 4.0. Follow the stricter non-commercial terms unless the authors or
repository clarify the discrepancy. Cite the dataset when reusing its records.
