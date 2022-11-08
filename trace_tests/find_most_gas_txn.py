from pathlib import Path
import json
from collections import Counter

DATA_DIR = Path("/data_ssd/yangdong/node")
LOG_RANGE = list(range(21449, 21867))

dumped_logs = []
for logno in LOG_RANGE:
    with open(DATA_DIR / "receipts" / f"{logno // 100}" / f"{logno}.log") as f:
        for line in f:
            rec = json.loads(line)
            key = rec["transactionHash"]
            dumped_logs.append(key)
ct = Counter(dumped_logs)
print(ct.most_common(10))
