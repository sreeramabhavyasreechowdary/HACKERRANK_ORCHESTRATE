import json

with open("dataset/evidence/records/service_resource_export_20260915_114455.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Type:", type(data))
if isinstance(data, dict):
    print("Keys:", list(data.keys()))
    records = data.get("records", [])
    print("Total records:", len(records))
    for r in records[:5]:
        print(r)
