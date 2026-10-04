import openpyxl
import json
from saigon_places_data_part1 import THAM_QUAN_PLACES, AN_UONG_PLACES
from saigon_places_data_part2 import CAFE_PLACES, GIAI_TRI_PLACES, CHO_O_PLACES

all_places = THAM_QUAN_PLACES + AN_UONG_PLACES + CAFE_PLACES + GIAI_TRI_PLACES + CHO_O_PLACES
print(f"Total enriched places: {len(all_places)}")

wb = openpyxl.load_workbook('Places/Sai_Gon_Places.xlsx')
sheet = wb['Sai_Gon']
headers = [c.value for c in sheet[1]]
orig_rows = list(sheet.iter_rows(values_only=True))[1:]

print(f"Total original rows: {len(orig_rows)}")
assert len(all_places) == len(orig_rows), f"Count mismatch: {len(all_places)} vs {len(orig_rows)}"

mismatches = []
for i, (orig, enriched) in enumerate(zip(orig_rows, all_places)):
    orig_name = orig[1]
    enr_name = enriched['name']
    if orig_name.strip() != enr_name.strip():
        mismatches.append((i, orig_name, enr_name))

if mismatches:
    print(f"Found {len(mismatches)} name mismatches:")
    for m in mismatches:
        print(f"Row {m[0]}: orig '{m[1]}' vs enriched '{m[2]}'")
else:
    print("All 177 place names match 100% perfectly in order!")
