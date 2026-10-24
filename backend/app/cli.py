"""Command Line Interface for running the pipeline (Milestone B2).

Usage:
  python -m app.cli run --mode sample|final [--output <path>]
  python -m app.cli eval [--predictions <path>] [--sample-output <path>]
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List

from backend.app.config import config
from backend.app.ingest.loader import DataLoader, DatasetBundle
from backend.app.ingest.identity import IdentityResolver
from backend.app.extract.evidence_repo import EvidenceRepository
from backend.app.state.reconstruct import StateReconstructor
from backend.app.policy.decide import DecisionEngine
from backend.app.output.writer import OutputWriter, StepItem, CaseOutput
from backend.app.output.validator import OutputValidator
from backend.app.evaluate.metrics import Evaluator, FullEvaluationReport
import pandas as pd


def generate_conforming_placeholder_steps(
    case_id: str,
    status: str,
    default_evidence_id: str = "evidence_54",
) -> List[StepItem]:
    """Generate spec-conforming steps for placeholder output."""
    if status == "NOT_APPLICABLE":
        return []

    if status == "COMPLETE":
        return [
            StepItem(
                step_no=1,
                phase="VERIFICATION",
                system_id="account_service",
                resource_id=f"account_{case_id.split('_')[-1] if '_' in case_id else '001'}",
                operation="VERIFY_RECORD_ABSENT",
                state="ABSENT",
                evidence_id=default_evidence_id,
            )
        ]

    res_id = f"account_{case_id.split('_')[-1] if '_' in case_id else '001'}"
    return [
        StepItem(
            step_no=1,
            phase="FINDING",
            system_id="account_service",
            resource_id=res_id,
            operation="REPORT_REMAINING_RECORD",
            state="PRESENT",
            evidence_id=default_evidence_id,
        ),
        StepItem(
            step_no=2,
            phase="REMEDIATION",
            system_id="account_service",
            resource_id=res_id,
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="",
        ),
        StepItem(
            step_no=3,
            phase="VERIFICATION",
            system_id="account_service",
            resource_id=res_id,
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="",
        ),
    ]


def run_pipeline(mode: str, output_path: Path, dataset_dir: Path = Path("dataset")):
    """Run pipeline in sample or final mode, validating output conformance."""
    print(f"=== Running Ghost Data Pipeline (Mode: {mode.upper()}) ===")
    start_time = time.time()

    # 1. Ingest dataset files
    print(f"Loading dataset files from {dataset_dir} for mode '{mode}'...")
    bundle: DatasetBundle = DataLoader.load_dataset(dataset_dir=dataset_dir, mode=mode)
    print(f"Loaded {len(bundle.requests)} requests, {len(bundle.identities)} identities, {len(bundle.evidence_manifest)} evidence files.")

    default_ev_id = bundle.evidence_manifest[0].file_id if bundle.evidence_manifest else "evidence_01"

    # 2. Initialize Identity Resolver and Evidence Repository
    print("Initializing IdentityResolver and EvidenceRepository...")
    identities_df = pd.read_csv(dataset_dir / "user_identities.csv")
    audit_log_df = pd.read_csv(dataset_dir / "user_audit_log.csv")
    ev_manifest_df = pd.read_csv(dataset_dir / "evidence_files.csv")
    sys_activity_df = pd.read_csv(dataset_dir / "system_activity.csv")

    resolver = IdentityResolver(identities_df, audit_log_df)
    repo = EvidenceRepository(ev_manifest_df, base_dir=dataset_dir)
    reconstructor = StateReconstructor(evidence_repo=repo, system_activity_df=sys_activity_df)

    # 3. Reconstruct and decide each case
    print(f"Reconstructing deletion states across {len(bundle.requests)} cases...")
    rows: List[CaseOutput] = []
    for req in bundle.requests:
        ident = resolver.resolve(req.email)
        state = reconstructor.reconstruct_case(req, ident)
        decision = DecisionEngine.decide(state)
        step_items = [
            StepItem(
                step_no=s.step_no,
                phase=s.phase,
                system_id=s.system_id,
                resource_id=s.resource_id,
                operation=s.operation,
                state=s.state,
                evidence_id=s.evidence_id,
            )
            for s in state.final_steps
        ]
        rows.append(CaseOutput(case_id=req.case_id, deletion_status=decision.deletion_status, steps_json=step_items))

    # 4. Write output.csv
    print(f"Writing {len(rows)} rows to {output_path}...")
    OutputWriter.write(rows, output_path)

    # 5. Run OutputValidator
    print(f"Validating {output_path}...")
    val_report = OutputValidator.validate_or_raise(
        output_path=output_path,
        expected_case_count=len(bundle.requests),
        valid_evidence_ids=bundle.valid_citation_ids,
    )
    print(f" Validation PASSED: All {len(val_report.checks)} spec conformance checks passed.")

    # 6. If sample mode, run evaluation harness and generate report
    if mode == "sample":
        sample_out = dataset_dir / "sample_output.csv"
        if sample_out.exists():
            print(f"\n--- Running Evaluation against {sample_out} ---")
            report = Evaluator.evaluate(
                predictions_path=output_path,
                sample_output_path=sample_out,
            )
            report_path = Evaluator.write_markdown_report(report)
            print(f"Case Accuracy: {report.case_accuracy * 100:.2f}% (Tune: {report.tune_score * 100:.2f}%, Holdout: {report.holdout_score * 100:.2f}%)")
            print(f"Step F1: {report.step_metrics.f1:.4f} (Precision: {report.step_metrics.precision:.4f}, Recall: {report.step_metrics.recall:.4f})")
            print(f"Exact Sequence Accuracy: {report.sequence_metrics.exact_sequence_match_rate * 100:.2f}% (LCS ratio: {report.sequence_metrics.average_lcs_ratio:.4f})")
            print(f"Report written to: {report_path}")

    elapsed = time.time() - start_time
    print(f"=== Successfully Completed in {elapsed:.2f}s ===")


def run_evaluation_cli(
    predictions_path: Path,
    sample_output_path: Path,
    report_output_path: Path = Path("evaluation/evaluation_report.md"),
):
    """Run standalone evaluation command."""
    print(f"Evaluating {predictions_path} against {sample_output_path}...")
    report = Evaluator.evaluate(
        predictions_path=predictions_path,
        sample_output_path=sample_output_path,
    )
    report_path = Evaluator.write_markdown_report(report, report_output_path)
    print(f"Case Accuracy: {report.case_accuracy * 100:.2f}%")
    print(f"Step-level F1: {report.step_metrics.f1:.4f}")
    print(f"Sequence Accuracy: {report.sequence_metrics.exact_sequence_match_rate * 100:.2f}%")
    print(f"Evaluation report generated: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Pipeline CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # run command
    run_parser = subparsers.add_parser("run", help="Run the pipeline")
    run_parser.add_argument("--mode", choices=["sample", "final"], default="sample", help="Run mode (sample|final)")
    run_parser.add_argument("--output", type=Path, default=Path("output.csv"), help="Output CSV path")
    run_parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"), help="Path to dataset directory")

    # eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluate predictions against sample_output.csv")
    eval_parser.add_argument("--predictions", type=Path, default=Path("output.csv"), help="Path to predictions CSV")
    eval_parser.add_argument("--sample-output", type=Path, default=Path("dataset/sample_output.csv"), help="Path to ground truth sample_output.csv")
    eval_parser.add_argument("--report", type=Path, default=Path("evaluation/evaluation_report.md"), help="Path for generated markdown report")

    args = parser.parse_args()

    if args.subcommand == "eval":
        run_evaluation_cli(
            predictions_path=args.predictions,
            sample_output_path=args.sample_output,
            report_output_path=args.report,
        )
    else:
        # Default to 'run'
        mode = getattr(args, "mode", "sample")
        out_path = getattr(args, "output", Path("output.csv"))
        dataset_dir = getattr(args, "dataset_dir", Path("dataset"))
        run_pipeline(mode=mode, output_path=out_path, dataset_dir=dataset_dir)


if __name__ == "__main__":
    main()
