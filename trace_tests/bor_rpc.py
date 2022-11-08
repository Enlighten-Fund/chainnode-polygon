import json
import requests
from random import randint


URL = "https://polygon-mainnet.infura.io/v3/295cce92179b4be498665b1b16dfee34"
rpcs = {}
def rpc(payload):
    if payload in rpcs:
        return rpcs[payload]
    x = randint(1, 1000000000)
    response = requests.post(URL, json=payload).json()
    assert response["jsonrpc"] == "2.0", f"{response}"
    assert int(response["id"]) == 1, f"{response}"

