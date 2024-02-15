import json
from datetime import datetime

#USDC Feb 13 06:00 from Aave Api : getRatesHistory 
target = 0.08444370944270256

# https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/services/RatesHistory.ts#L24
interval = 5 * 60

resolution_in_hours = 6
seconds_in_year = 31536000


# https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/services/RatesHistory.ts#L31
def get_start_timestamp(ref_timestamp: int):
    quotient = ref_timestamp // interval
    return quotient * interval


# https://github.com/aave/aave-js/blob/4edcc76b133fe6c060f3604ccd081114cc059920/src/helpers/pool-math.ts#L171
def calculate_average_rate(
    index0: int,
    index1: int,
    timestamp0: int,
    timestamp1: int,
):
    average_rate = int(index1) / int(index0)
    average_rate -= 1
    average_rate /= (timestamp1 - timestamp0)
    average_rate *= seconds_in_year

    return average_rate


# https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/services/RatesHistory.ts#L86
def get_rates_between(to_data: dict, from_data: dict, current_ts: int):
    rates = []

    liq_rate = calculate_average_rate(
                index0=from_data['liquidityIndex'],
                index1=to_data['liquidityIndex'],
                timestamp0=from_data['timestamp'],
                timestamp1=to_data['timestamp']
            )
    
    timestamp = current_ts
    while timestamp <= to_data['timestamp']:
        rates.append(
            {
                'timestamp': timestamp,
                'liquidityRate': liq_rate,
                'timestamp0': from_data['timestamp'],
                'timestamp1': to_data['timestamp'],
                'index0': str(from_data['liquidityIndex']),
                'index1': str(to_data['liquidityIndex'])
            }
        )
        timestamp += interval

    return rates


# https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/services/RatesHistory.ts#L123
def get_rates_api_method(start_ts: int, reserve_data: list):
    final_rates = []
    current_ts = start_ts
    for i in range(len(reserve_data) - 1):
        if reserve_data[i + 1]['timestamp'] <= current_ts:
            pass
        else:
            from_data = reserve_data[i]
            to_data = None
            for d in reserve_data[i:]:
                if d['timestamp'] >= current_ts + interval:
                    to_data = d
                    break
            if not to_data:
                break
            
            rates = get_rates_between(to_data=to_data, from_data=from_data, current_ts=current_ts)

            if len(rates):
                for rate in rates:
                    final_rates.append(rate)
                current_ts = rates[-1]['timestamp']
            
            current_ts += interval

    return final_rates


def calc_window(rates: list, save_file: str):
    window = []
    window_data = []
    for rate in rates:
        date = datetime.fromtimestamp(rate['timestamp'])

        # https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/repositories/mongodb/domains/Rate.ts#L94
        period = (date.hour // resolution_in_hours) * resolution_in_hours

        if date.day == 13 and period == 6:
            window.append(rate['liquidityRate'])
            window_data.append(rate)

    with open(save_file, "w") as file:
        json.dump(window_data, file)

    return window


if __name__ == "__main__":

    # data pulled from https://api.thegraph.com/subgraphs/name/aave/protocol-v3/
    # see graph_querys.txt for source
    with open("data/graph_data.json", "r") as file:
        graph_data_d = json.load(file)

    # Api removes duplicate timestamps
    # https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/services/RatesHistory.ts#L169
    seen_ts = set()
    new = []
    for data in graph_data_d['data']['reserveParamsHistoryItems']:
        if data['timestamp'] not in seen_ts:
            new.append(data)
            seen_ts.add(data['timestamp'])

    start_ts = get_start_timestamp(new[0]['timestamp'])
    graph_api_method_rates = get_rates_api_method(start_ts=start_ts + interval, reserve_data=new)

    window = calc_window(rates=graph_api_method_rates, save_file="results/api_window.json")

    print("replicate graph api")
    print(f"sample size {len(window)}")
    avg = sum(window) / len(window)
    print(f"calc average: {avg}")
    # print(round(avg * 100, 2))
    print(f"target      : {target}") 
    print("-------")

    # data pulled directly from snapshotter, see get_data.py.
    with open("data/data3.json", "r") as file:
        snap_data = json.load(file)

    start_key = 'block' + str(snap_data[0]["chainHeightRange"]['begin'])
    last_update_ts = snap_data[0]["lastUpdateTimestamp"][start_key]

    # collect blocks where liquidityIndex updates, expected to be 1 to 1 with graph data
    filtered_data = []
    for data in snap_data:
        for key, timestamp in data["lastUpdateTimestamp"].items():
            if timestamp != last_update_ts:
                filtered_data.append({
                    'timestamp': timestamp,
                    'liquidityIndex': data["liquidityIndex"][key]
                })
                last_update_ts = timestamp

    start_ts = get_start_timestamp(filtered_data[0]['timestamp'])
    snap_api_method_rates = get_rates_api_method(start_ts=start_ts + interval, reserve_data=filtered_data)

    window = calc_window(rates=snap_api_method_rates, save_file="results/snap_window.json")

    print("replicate snapshotter")
    print(f"sample size {len(window)}")
    avg = sum(window) / len(window)
    print(f"calc average: {avg}")
    # print(round(avg * 100, 2))
    print(f"target      : {target}") 
    print("-------")


    # calc a direct liquidity rate simple average for comparison
    # Not 1 to 1 with rates between indices method, but gives a good estimate.
    simple_avgs = []
    for i in range(0, len(snap_data)):
        rate = sum(snap_data[i]['liquidityRate'].values()) / 10
        simple_avgs.append({
                    'liquidityRate': rate / 1e27,
                    'timestamp': snap_data[i]['timestamp']
                })
    
    window = calc_window(rates=simple_avgs, save_file="results/simple_avg_window.json")

    print("simple rate average")
    print(f"sample size {len(window)}")
    avg = sum(window) / len(window)
    print(f"calc average: {avg}")
    print(f"target      : {target}")
    print("-------")