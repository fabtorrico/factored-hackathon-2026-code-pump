import json
import hashlib
from pathlib import Path
from typing import Any
import random

from app.ml.labels import IncidentLabel

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'evaluation' / 'incident_understanding'
DATA_DIR.mkdir(parents=True, exist_ok=True)
SEED = 42
random.seed(SEED)

FAMILIES: list[dict[str, Any]] = []
fam_idx = 0
