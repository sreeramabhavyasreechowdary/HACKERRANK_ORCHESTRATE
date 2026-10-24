import pandas as pd

df_ev = pd.read_csv("dataset/evidence_files.csv")
for fid in ["evidence_51", "evidence_54", "evidence_92", "evidence_94", "evidence_03", "evidence_58", "evidence_59"]:
    m = df_ev[df_ev["file_id"] == fid]
    if len(m) > 0:
        row = m.iloc[0]
        print(f"[{fid}] path={row['file_path']} | origin={row['origin']} | captured_at={row['captured_at']}")
