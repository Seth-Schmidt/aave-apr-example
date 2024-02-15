import json
import time
import requests

current = 1
end = 842

data_list = []

while current <= end:
    response = requests.get(f'http://localhost:8002/data/{current}/poolContract_total_supply:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48:aavev3/')
    data = response.json()
    data_list.append(data)
    current += 1
    time.sleep(0.1)

with open("data/data3.json", "w") as file:
    json.dump(data_list, file)

current = 1
end = 842

apr_list = []
while current <= end:
    response = requests.get(f'http://localhost:8002/data/{current}/aggregate_poolContract_6h_apr:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48:aavev3/')
    data = response.json()
    apr_list.append(data)
    current += 1
    time.sleep(0.1)

with open("data/aprdata3.json", "w") as file:
    json.dump(apr_list, file)
