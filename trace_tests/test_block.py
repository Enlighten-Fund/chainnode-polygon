from pathlib import Path
import json
import requests
from tqdm import tqdm
import base64
from collections import Counter

DATA_DIR = Path("/data_ssd/yangdong/node")
LOG_RANGE = list(range(30000, 30010)) + list(range(42200, 42210))
URL = "https://polygon-mainnet.infura.io/v3/295cce92179b4be498665b1b16dfee34"

for logno in LOG_RANGE:
    unseen_txns = {}
    # block_base_fee = {}
    with open(DATA_DIR / "blocks" / f"{logno // 100}" / f"{logno}.log") as f:
        for i in tqdm(range(100)):
            line = f.readline()
            rec = json.loads(line)
            blockno = logno * 100 + i
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
            # check all 10 dumped fields
            assert result["hash"] == rec["blockHash"]
            assert int(result["number"], 16) == blockno and blockno == rec["blockNumber"]
            assert int(result["difficulty"], 16) == rec["difficulty"]
            assert int(result["gasLimit"], 16) == rec["gasLimit"]
            assert int(result["gasUsed"], 16) == rec["gasUsed"]
            assert result["miner"] == rec["miner"]
            assert int(result["nonce"], 16) == rec["nonce"]
            assert result["parentHash"] == rec["parentHash"]
            assert int(result["size"], 16) == rec["size"]
            assert int(result["timestamp"], 16) == rec["timestamp"]
            
            for txn in result["transactions"]:
                unseen_txns[txn["hash"]] = txn
            # block_base_fee[blockno] = result["baseFeePerGas"]
        print(f"ok. Verified 100 BLOCK info in {logno}.log")
    txn_num = len(unseen_txns)
    with open(DATA_DIR / "transactions" / f"{logno // 100}" / f"{logno}.log") as f:
        ct = 0
        typ = []
        for line in tqdm(f):
            ct += 1
            rec = json.loads(line)
            txn = rec["transactionHash"]
            assert txn in unseen_txns, f"ERROR: txn not seen in any blocks: {txn}"
            result = unseen_txns.pop(txn)
            assert rec["accessList"] is None
            assert rec["blockHash"] == result["blockHash"]
            assert rec["blockNumber"] == int(result["blockNumber"], 16)
            assert "0x" + base64.b64decode(rec["data"]).hex() == result["input"]
            assert rec["from"] == result["from"]
            assert rec["gas"] == int(result["gas"], 16)
            # assert rec["gasUsed"] == int(result["gas"], 16)
            assert rec["nonce"] == int(result["nonce"], 16)
            # assert rec["status"] == 
            assert rec["to"] == result["to"]
            assert rec["transactionHash"] == result["hash"]
            assert rec["transactionIndex"] == int(result["transactionIndex"], 16)
            assert rec["type"] == int(result["type"], 16)
            assert rec["value"] == int(result["value"], 16)
            if rec["type"] in {0, 1}:
                # legacy.
                assert rec["gasTipCap"] == rec["gasFeeCap"] == rec["gasPrice"] == int(rec["effectiveGasPrice"], 16) == int(result["gasPrice"], 16)
            elif rec["type"] == 2:
                # EIP-1559
                assert rec["effectiveGasPrice"] == result["gasPrice"]
                assert rec["gasPrice"] == rec["gasFeeCap"] == int(result["maxFeePerGas"], 16)
                assert rec["gasTipCap"] == int(result["maxPriorityFeePerGas"], 16)
            else:
                assert False, f"Unseen transaction type {rec['type']}"
            typ.append(rec["type"])
        print(f"ok. Verified {ct} TRANSACTION info in {logno}.log. Txn types cnt: {Counter(typ)}")
    assert len(unseen_txns) == 0, f"ERROR: not all txns are covered: {unseen_txns.keys()}"
