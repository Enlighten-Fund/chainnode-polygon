import requests

url = "https://eth-mainnet.alchemyapi.io/v2/demo"

payload = {
    "id": 1,
    "jsonrpc": "2.0",
    "method": "trace_transaction",
    "params": [
        "0x9493ba4917d95050e7656a6d1da0e6f92e922b27914e6d6105e90f9a29091098"
    ]
}
headers = {
    "accept": "application/json",
    "content-type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)