import openpyxl
import json

wb = openpyxl.load_workbook('Places/Sai_Gon_Places.xlsx')
sheet = wb['Sai_Gon']

headers = [cell.value for cell in sheet[1]]
rows = list(sheet.iter_rows(values_only=True))[1:]

places = []
for r in rows:
    row_dict = dict(zip(headers, r))
    places.append(row_dict)

summary = {
    "total": len(places),
    "sample_first_3": places[:3],
    "kinds_distribution": {},
    "missing_or_nan_fields": {},
}

for p in places:
    k = str(p.get("kind"))
    summary["kinds_distribution"][k] = summary["kinds_distribution"].get(k, 0) + 1
    
    for col, val in p.items():
        if val is None or str(val).strip().lower() in ("", "nan", "none", "null"):
            summary["missing_or_nan_fields"][col] = summary["missing_or_nan_fields"].get(col, 0) + 1

with open("scratch_places_detail.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print("Saved scratch_places_detail.json")
