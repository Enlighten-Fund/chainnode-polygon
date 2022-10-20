import requests
from collections import Counter
def main():
    verify_limit, num_verified = 100, 0
    txn_num_dist = Counter()
    URL = "https://polygon-mainnet.infura.io/v3/295cce92179b4be498665b1b16dfee34"
    with open("/home/yangdong/seqno.txt") as f:
        for line in f:
            record = line.split()
            assert len(record) >= 2, line
            if len(record) <= 3:
                continue
            block_num, time, txn_num, *txns = record
            block_num, txn_num = int(block_num), int(txn_num)
            assert len(txns) == txn_num, line
            payload = {
                "jsonrpc": "2.0",
                "method":"eth_getBlockTransactionCountByNumber",
                "params": [hex(block_num)],
                "id": block_num,
            }
            response = requests.post(URL, json=payload).json()
            assert response["jsonrpc"] == "2.0", f"{response}"
            assert int(response["id"]) == block_num, f"{response}"
            assert int(response["result"], 16) == int(txn_num), f"correct answer {response}, my answer {txn_num}"

            for txn in txns:
                payload = {
                    "jsonrpc": "2.0",
                    "method":"eth_getTransactionByHash",
                    "params": [txn],
                    "id": "1",
                }
                response = requests.post(URL, json=payload).json()
                assert response["jsonrpc"] == "2.0", f"{response}"
                assert int(response["result"]["blockNumber"], 16) == block_num, f"correct answer {int(response['result']['blockNumber'], 16)}, my answer {block_num}"
                print(f"  OK. txn {txn} is in block {block_num}.")
            num_verified += 1
            txn_num_dist[txn_num] += 1
            print("Block", block_num, ": Correct", txn_num, "txns", num_verified, "verified")
            if num_verified >= verify_limit:
                break
    verify_limit, num_verified = 100, 0
    with open("/home/yangdong/events.txt") as f:
        for line in f:
            if line.strip() == "":
                continue
            l, r = line.strip().split("[")
            hsh, cnt = l.split()
            cnt = int(cnt)
            assert r[-1] == ']'
            nums = r[:-1].split()
            bloom = "0x"
            for x in nums:
                bloom += hex(int(x) // 16)[2:] + hex(int(x) % 16)[2:]
            payload = {
                "jsonrpc": "2.0",
                "method":"eth_getTransactionReceipt",
                "params": [hsh],
                "id": "1",
            }
            print("My bloom:", bloom, "my log count:", cnt)
            response = requests.post(URL, json=payload).json()
            response = response["result"]
            assert len(response["logs"]) == cnt, f"Cnt mismatch: expect {len(response['logs'])}"
            assert response["logsBloom"] == bloom, f"Bloom mismatch: expect {response['logsBloom']}"
            num_verified += 1
            print(f"OK, {num_verified} verified")
            if num_verified >= verify_limit:
                break
if __name__ == "__main__":
    main()
