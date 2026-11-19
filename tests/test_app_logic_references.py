"""Keep every logic symbol used by the screen available in logic.py."""

import ast
from pathlib import Path

import logic


def test_every_app_logic_reference_exists_in_logic_module():
    project = Path(__file__).resolve().parents[1]
    app_tree = ast.parse((project / "app.py").read_text(encoding="utf-8"))
    logic_tree = ast.parse((project / "logic.py").read_text(encoding="utf-8"))

    app_references = {
        node.attr for node in ast.walk(app_tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "logic"
    }
    logic_definitions = set()
    for node in logic_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            logic_definitions.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            logic_definitions.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            logic_definitions.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )

    missing = sorted(app_references - logic_definitions)
    assert not missing, f"app.py uses names missing from logic.py: {missing}"
    assert all(hasattr(logic, name) for name in app_references), (
        f"app.py uses names not importable from logic.py: "
        f"{sorted(name for name in app_references if not hasattr(logic, name))}"
    )
