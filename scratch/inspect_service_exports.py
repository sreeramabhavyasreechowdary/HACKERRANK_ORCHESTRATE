import json

with open("dataset/evidence/records/service_resource_export_20260915_114455.json", "r", encoding="utf-8") as f:
    data = json.load(f)

exports = data.get("service_exports", {})
print("Services in export:", list(exports.keys()))
for svc, recs in exports.items():
    print(f"  Service '{svc}': {len(recs)} records. First: {recs[0] if recs else None}")
