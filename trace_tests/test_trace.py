import json
import sys

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <geth> [<blockno> <txn_hash>]")
    exit(0)

output = []
with open(sys.argv[1]) as f:
    rec = json.load(f)
    def dfs(ct, path):
        output.append({
            "type": "call",
            "action": {
                "callType": ct["type"].lower(),
                "from": ct["from"],
                "to": ct["to"],
                "gas": ct["gas"],
                "input": ct["input"],
                "value": "0x" if ("value" not in ct or int(ct["value"], 16) == 0) else ct["value"],
            },
            "result": {
                "gasUsed": ct["gasUsed"],
                "output": ct["output"],
            },
            "subtraces": len(ct["calls"]) if "calls" in ct else 0,
            "traceAddress": path,
            "blockHash": None,
            "blockNumber": None,
            "transactionHash": None,
            "transactionPosition": None,
            "transactionTraceID": 0,
            "transactionLastTrace": 0
        })
        if "calls" in ct:
            for i, c in enumerate(ct["calls"]):
                dfs(c, path + [i])
    dfs(rec, [])
    for i, d in enumerate(output):
        d["transactionTraceID"] = i
    output[-1]["transactionLastTrace"] = 1


if len(sys.argv) == 4:
    blockno = int(sys.argv[2])
    txhash = sys.argv[3]
    with open(f"/home/yangdong/node/traces/{blockno//10000}/{blockno//100}.log") as f:
        traces = [json.loads(line) for line in f]
        txtraces = list(filter(lambda x: x["transactionHash"] == txhash, traces))
        assert len(txtraces) == len(output), f"Length differ: expect {len(output)}, get {len(txtraces)}"
        print(f"Number of traces: {len(output)}")
        # for tr in txtraces:
        #     print(tr)
        for dtrace, ctrace in zip(txtraces, output):
            ctrace["blockHash"] = dtrace["blockHash"]
            ctrace["blockNumber"] = dtrace["blockNumber"]
            ctrace["transactionHash"] = dtrace["transactionHash"]
            ctrace["transactionPosition"] = dtrace["transactionPosition"]
            assert ctrace == dtrace, f"Record differ\n{ctrace}\n{dtrace}"
print("OK")
