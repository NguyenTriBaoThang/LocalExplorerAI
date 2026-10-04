# HCMC historical flood reports — raw source / Dữ liệu Báo cáo Ngập lụt Thô TP.HCM

> **Tóm tắt (Vietnamese Summary):**
> Thư mục này chứa tập dữ liệu thô các báo cáo ngập lụt tại TP. Hồ Chí Minh giai đoạn 2002–2026 được chuyển đổi sang chuẩn UTF-8 CSV từ bảng `Flood_event_locations.tab` của DataSuds. Dữ liệu bao gồm 425 quan trắc và 22 cột thuộc tính nguyên bản; không tự ý suy diễn nhãn, không tự tạo dữ liệu đường khô, và không tự gán `edge_id`. Tập tin này phục vụ lưu trữ nguồn gốc (traceability) và **chưa sẵn sàng** để nạp trực tiếp vào notebook huấn luyện mô hình Flood Colab nếu chưa có dữ liệu quan sát âm bản đối chứng.

`hcmc_flood_reports_2002_2026.csv` is a UTF-8 CSV conversion of the public
`Flood_event_locations.tab` table from the dataset below. The conversion
preserves its 22 source columns and 425 observation rows; it does not add
labels, infer dates, generate non-flood examples, or map observations to this
project's road-edge IDs.

`flood_training.csv` is an additional copy exported at the user's requested
filename. Its contents are still these same raw reports; the filename does
**not** mean it is ready for the Flood Colab notebook.

- Dataset: Hardy, Sebastien; Radziute, Gintaré (2026), *Historical database of
  urban flooding in Ho Chi Minh City, Vietnam (2002–2026)*, DataSuds, Version 1.
- DOI: <https://doi.org/10.23708/8Y16HU>
- Source file: <https://dataverse.ird.fr/api/access/datafile/50148?format=original>
- License: CC BY-NC 4.0. Attribution is required and use is restricted to
  non-commercial purposes; check the license before redistribution or use in a
  commercial product.
- Source file MD5 verified by `scripts/download_hcmc_flood_reports.py`:
  `39de82a4ff2401e527a6dc5be13b25f0`.

This is a collection of reported flood observations. It is **not** ready for
the Flood Colab training notebook: some source dates are blank, it contains no
verified no-flood observation windows, and it does not contain the project's
`edge_id` labels. Absence of a news report is not evidence that a road was dry.
Do not rename this raw file to `flood_training.csv` or upload it to the training
path without collecting and validating the missing evidence.

To download/convert the source again (requires internet access):

```powershell
python scripts/download_hcmc_flood_reports.py
```

To recreate the exact-name raw copy:

```powershell
python scripts/download_hcmc_flood_reports.py --output data/raw/flood_training.csv --force
```
