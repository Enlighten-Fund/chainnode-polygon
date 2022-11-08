from pathlib import Path
import json
from collections import Counter
from tqdm import tqdm

DATA_DIR = Path("/data_ssd/yangdong/node")
LOG_RANGE = list(range(80000, 85000))

dumped_logs = []
for logno in tqdm(LOG_RANGE):
    with open(DATA_DIR / "traces" / f"{logno // 100}" / f"{logno}.log") as f:
        for line in f:
            rec = json.loads(line)
            key = rec["type"]
            dumped_logs.append(key)
print(Counter(dumped_logs))