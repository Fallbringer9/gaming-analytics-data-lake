import ast
import sys
from pathlib import Path

AGENT_PACKAGE = "gaming_analytics_data_lake.agent"
AGENT_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "src" / Path(*AGENT_PACKAGE.split("."))
)


def test_core_imports_only_the_standard_library_and_inward_layers():
    domain = f"{AGENT_PACKAGE}.domain"
    allowed_by_path = {
        **{path: (domain,) for path in (AGENT_DIRECTORY / "domain").glob("*.py")},
        AGENT_DIRECTORY / "ports.py": (domain,),
        AGENT_DIRECTORY / "application.py": (domain, f"{AGENT_PACKAGE}.ports"),
    }
    for path, allowed in allowed_by_path.items():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports = [entry.name for entry in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, (
                    f"Use absolute imports in the core ({path}:{node.lineno})"
                )
                imports = [node.module or ""]
            else:
                continue

            for module in imports:
                assert module.split(".")[0] in sys.stdlib_module_names or any(
                    module == prefix or module.startswith(f"{prefix}.")
                    for prefix in allowed
                ), f"{path.name}:{node.lineno} has an outward dependency on {module}"
