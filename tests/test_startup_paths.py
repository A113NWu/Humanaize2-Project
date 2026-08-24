from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "humanaize2.sh").read_text(encoding="utf-8")
MAIN = (ROOT / "src/core/main.py").read_text(encoding="utf-8")


def test_shell_uses_project_model_dir_fallback():
    assert 'MODEL_DIR="$MAIN_DIR/model"' in SCRIPT


def test_main_resolves_model_dirs_in_both_names():
    assert '"model", "models"' in MAIN
