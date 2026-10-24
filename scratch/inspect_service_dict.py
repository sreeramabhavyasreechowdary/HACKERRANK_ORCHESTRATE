import json

with open("dataset/evidence/records/service_resource_export_20260915_114455.json", "r", encoding="utf-8") as f:
    data = json.load(f)

exports = data.get("service_exports", {})
for svc, recs in exports.items():
    print(f"Service: {svc} | type={type(recs)}")
    if isinstance(recs, dict):
        sample_k = list(recs.keys())[:2]
        print(f"  Keys ({len(recs)}): {sample_k}")
        for k in sample_k:
            print(f"    {k} -> {recs[k]}")
    elif isinstance(recs, list):
        print(f"  List ({len(recs)} items): {recs[:2]}")
