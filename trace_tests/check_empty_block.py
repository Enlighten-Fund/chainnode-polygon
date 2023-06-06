from pathlib import Path
import json
import requests
from tqdm import tqdm
import base64
from collections import Counter

PER_DIR = 100000
PER_FILE = 1000
FILE_PER_DIR = PER_DIR // PER_FILE

DATA_DIR = Path("/data_ssd/yangdong/node")
LOG_RANGE = list(range(13929, 13932))
URL = "http://localhost:8545"

total_txn, total_log = 0, 0
for logno in LOG_RANGE:
    unseen_txns = {}
    with open(DATA_DIR / "blocks" / f"{logno // FILE_PER_DIR}" / f"{logno}.log") as f:
        data = {}
        for line in f:
            rec = json.loads(line)
            data[rec["blockNumber"]] = rec

        for i in tqdm(range(PER_FILE)):
            blockno = logno * PER_FILE + i
            if blockno not in data:
                payload = {
                    "jsonrpc": "2.0",
                    "method":"eth_getBlockByNumber",
                    "params": [hex(blockno), True],
                    "id": blockno,
                }
                response = requests.post(URL, json=payload).json()
                assert response["jsonrpc"] == "2.0", f"{response}"
                assert int(response["id"]) == blockno, f"{response}"
                result = response["result"]
                print(f"Warning: block #{blockno} is missing")
                assert len(result["transactions"]) == 0 and result["gasUsed"] == "0x0", result
                continue
            if not (data[blockno]["gasUsed"] > 0 or blockno % 64 == 0):
                print(f"ERROR: Empty block not discarded {data[blockno]}")
            # assert data[blockno]["gasUsed"] > 0 or blockno % 64 == 0, f"Empty block not discarded {data[blockno]}"
        print(f"ok. Verified {PER_FILE} BLOCK info in {logno}.log")
