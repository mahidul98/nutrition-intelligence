import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.perception.pipeline import analyze_image  # noqa: E402

path = Path(sys.argv[1])
print(analyze_image(path.read_bytes()).model_dump_json(indent=2))