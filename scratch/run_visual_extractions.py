import sys
from pathlib import Path
sys.path.insert(0, ".")
import pandas as pd
from backend.app.extract.vlm_extractor import MultimodalVLMExtractor

extractor = MultimodalVLMExtractor()
df = pd.read_csv("dataset/evidence_files.csv")
visual = df[df["file_path"].str.contains(r"\.(pdf|png|jpg|jpeg)$", regex=True, case=False)]
print(f"Extracting {len(visual)} visual evidence files...")
for _, row in visual.iterrows():
    fpath = Path("dataset") / row["file_path"]
    res = extractor.extract(fpath, row["file_id"])
    print(f"Extracted {row['file_id']} ({row['file_path']}): {len(res.observations)} obs, cached={res.is_cache_hit}, tokens_in={res.tokens_input}")

p = MultimodalVLMExtractor.generate_usage_report(total_requests=518)
print("Updated usage report:", p)
