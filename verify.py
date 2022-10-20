import requests
from collections import Counter
def main():
    verify_limit, num_verified = 10000, 0
    txn_num_dist = Counter()
    URL = "https://polygon-rpc.com/"
    last_block = None
    with open("/home/yangdong/seqno.txt") as f:
        for line in f:
            record = line.split()
            if len(record) < 2:
                print(line)
                continue
            block_num, time = int(record[0]), record[1]
            txn_num = None if len(record) <= 2 else int(record[2])
            if last_block is not None:
                assert block_num == last_block + 1, f"Block {block_num}: last block = {last_block}"
            last_block = block_num
            if txn_num is not None:
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
                num_verified += 1
                txn_num_dist[txn_num] += 1
                print("Block", block_num, ": Correct", txn_num, "txns")
            if num_verified >= verify_limit:
                print(txn_num_dist)
                exit(0)

if __name__ == "__main__":
    main()
