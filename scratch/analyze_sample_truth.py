import pandas as pd
import json

df_req = pd.read_csv("dataset/sample_deletion_requests.csv")
df_out = pd.read_csv("dataset/sample_output.csv")
df_ident = pd.read_csv("dataset/user_identities.csv")
df_audit = pd.read_csv("dataset/user_audit_log.csv")
df_act = pd.read_csv("dataset/system_activity.csv")

merged = pd.merge(df_req, df_out, on="case_id")
print("Total sample cases:", len(merged))

for idx, r in merged.iterrows():
    steps = json.loads(r["steps_json"])
    u_match = df_ident[df_ident["email"] == r["email"]]
    uid = u_match["user_id"].values[0] if len(u_match) > 0 else "unknown"
    print(f"\n[{r['case_id']}] email={r['email']} user_id={uid} reported={r['reported_status']} truth={r['deletion_status']} audit_at={r['audit_at']} (steps={len(steps)})")
    for s in steps:
        print(f"    [{s['step_no']}] {s['phase']} | {s['operation']} | {s['state']} | {s['system_id']}:{s['resource_id']} | ev='{s['evidence_id']}'")
