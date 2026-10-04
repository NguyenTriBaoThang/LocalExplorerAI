import json

data = json.load(open('scratch_all_sheets.json', encoding='utf-8'))['Sai_Gon']
with open('scratch_places_indexed.txt', 'w', encoding='utf-8') as f:
    for i, p in enumerate(data):
        f.write(f"{i:03d} | {p['kind']:10s} | {p['name']} | current_ext_id: {p['ext_id']}\n")

print(f"Indexed {len(data)} places.")
