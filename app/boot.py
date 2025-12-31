from pathlib import Path
import sys


def ensure_project_root_on_path() -> None:
    app_dir = Path(__file__).resolve().parent
    project_root = app_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
