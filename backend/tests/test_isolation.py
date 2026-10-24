"""Tests proving the prediction path NEVER reads sample_output.csv (Hard Rule 1)."""

import ast
from pathlib import Path
import pytest
from backend.app.ingest.loader import DataLoader


def test_dataloader_blocks_sample_output():
    """Verify DataLoader raises PermissionError if pointed at sample_output.csv."""
    with pytest.raises(PermissionError, match="Hard Rule 1 Violation"):
        DataLoader.load_cases(Path("challenge/sample_output.csv"))

    with pytest.raises(PermissionError, match="Hard Rule 1 Violation"):
        DataLoader.load_cases(Path("sample_output.csv"))


def test_codebase_isolation_audit():
    """
    Statically inspects all Python files in the prediction pipeline
    (ingest, extract, state, policy, output) to prove NONE of them load sample_output.csv.
    Only evaluate/ is permitted to touch sample_output.
    """
    app_dir = Path(__file__).resolve().parent.parent / "app"
    forbidden_dirs = ["ingest", "extract", "state", "policy", "output"]

    violations = []
    for d_name in forbidden_dirs:
        dir_path = app_dir / d_name
        for py_file in dir_path.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                # Check function call arguments for attempts to load/read sample_output
                if isinstance(node, ast.Call):
                    # Check for functions like open(), read_csv(), Path()
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in ["open", "read_csv", "load", "read_table"]:
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                if "sample_output" in arg.value.lower():
                                    violations.append(f"{py_file.name}:{node.lineno} calls {func_name} with '{arg.value}'")

    assert not violations, f"Hard Rule 1 violation! Prediction path loads sample_output: {violations}"

