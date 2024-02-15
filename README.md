This repo contains a case study for aave average apr rate calculations showing the differences between the aave api subgraph results and the results from applying the same methods to data gathered from the blockchain.

Chain data was retrieved from a Powerloom snapshotter instance (get_data.py), and the subgraph data was retrieved from the first query in graph_queries.txt.

Run:
    python apr_example.py

This script targets the apr value for Feb 13 06:00 UTC on the current aave v3 dashboard.

# Differences Explanation:
    
The Aave v3 protocol [Subgraph](https://api.thegraph.com/subgraphs/name/aave/protocol-v3/) does not properly update the reserveParamsHistoryItems when an asset is Borrowed.

reserveParamsHistoryItems contains the data used for the aave api apr calculations: [Source](https://github.com/aave/aave-api/blob/70dde8a8119dfbdf33fd0708af18776a794a2b40/src/services/RatesHistory.ts#L55)

reserveParamsHistoryItems are updated in the subraph here via the saveReserve() function: [Source](https://github.com/aave/protocol-subgraphs/blob/bafc1d706e22ac6f0f260d178b1327d20a1b22c5/src/mapping/tokenization/tokenization-v3.ts#L92)

saveReserve() is called on supply and debt token mint/burn events which are emitted for all Borrow, Repay, Supply, and Withdraw events: [Source](https://github.com/aave/protocol-subgraphs/blob/bafc1d706e22ac6f0f260d178b1327d20a1b22c5/src/mapping/tokenization/tokenization-v3.ts#L412)

The updated reserve indices (the values used to compute apr) are emitted through ReserveDataUpdated events which are also emitted for all Borrow, Repay, Supply, and Withdraw events.

In the case of the Borrow event, the debt token is minted and the Mint event is emitted before ReserveDataUpdated. This causes the subgraph to update the reserveParamsHistoryItems for the asset before the ReserveDataUpdated event is parsed and applied to the underlying reserve data here: [Source](https://github.com/aave/protocol-subgraphs/blob/bafc1d706e22ac6f0f260d178b1327d20a1b22c5/src/mapping/lending-pool/v3.ts#L351)

So, when saveReserve() is called, the data that is saved is from the previous ReserveDataUpdated event instead of the new values: [Source](https://github.com/aave/protocol-subgraphs/blob/bafc1d706e22ac6f0f260d178b1327d20a1b22c5/src/mapping/tokenization/tokenization-v3.ts#L128)

We can show that this is the case with two subgraph queries:

Query 1 gets the reserveParamsHistoryItem for USDC at timestamp 1707804599: [Query Source](https://github.com/aave/aave-api/blob/master/src/repositories/subgraph/v2/reserveParamsHistoryItems.queries.ts)

    query MyQuery {
        reserveParamsHistoryItems(
            first: 1
            orderBy: timestamp
            where: {
            timestamp_gte: 1707804599
            reserve: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb480x2f39d218133afab8f2b819b1066c7e434ad94e9e"
            }
        ) {
            id
            reserve {
            id
            symbol
            pool {
                id
            }
            }
            liquidityIndex
            variableBorrowIndex
            utilizationRate
            stableBorrowRate
            timestamp
        }
    }

Which returns the liquidityIndex as: 
    
    "liquidityIndex": "1042138619579496895780693938"

We can get the block number and the transaction hash for the triggering tx via the reserveParamsHistoryItem's id value:

    "19217216:198:0xdc4a881eca3f4e0fb4d2ce0b02a00639d2bf90947fa45abf130b3cd0ea4256d6:591:591"

Showing the block to be: 19217216 and tx hash to be: 0xdc4a881eca3f4e0fb4d2ce0b02a00639d2bf90947fa45abf130b3cd0ea4256d6

The event logs ([Etherscan Tx](https://etherscan.io/tx/0xdc4a881eca3f4e0fb4d2ce0b02a00639d2bf90947fa45abf130b3cd0ea4256d6#eventlog)) show that the liquidityIndex should have been updated to: 

    "liquidityIndex": "1042138711865692808082240960":
    
Querying the reserve directly instead of the encompassing reserveParamsHistoryItem on block 19217216:

    query MyQuery {
        reserve(
            id: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb480x2f39d218133afab8f2b819b1066c7e434ad94e9e"
            block: {number: 19217216}
        ) {
            liquidityIndex
            lastUpdateTimestamp
        }
    }

Returns:

    {
        "data": {
            "reserve": {
            "liquidityIndex": "1042138711865692808082240960",
            "lastUpdateTimestamp": 1707804599
            }
        }
    }

Where we can see the correct liquidityIndex value and that the reserve was in fact updated at 1707804599, but the reserveParamsHistoryItems were saved before the reserve update occured.

Comparing the above Borrow Tx to a Supply Transaction ([Etherscan Tx](https://etherscan.io/tx/0x84f43f6e2026e245d360495ef392f6f4b3ad794adf2331d8080e29225b89c5f6#eventlog)), we can see that the ReserveDataUpdated event is emitted before the Mint event.

ReserveDataUpdated event is emitted on-chain when updateInterestRates() is called on the reserve: [Source](https://github.com/aave/aave-v3-core/blob/6070e82d962d9b12835c88e68210d0e63f08d035/contracts/protocol/libraries/logic/ReserveLogic.sol#L207)

When a Borrow transaction is executed, the mint happens before updateInterestRates() is called: [Source](https://github.com/aave/aave-v3-core/blob/6070e82d962d9b12835c88e68210d0e63f08d035/contracts/protocol/libraries/logic/BorrowLogic.sol#L126)

When a Supply transaction is executed, the mint happens after updateInterestRates() is called: [Source](https://github.com/aave/aave-v3-core/blob/6070e82d962d9b12835c88e68210d0e63f08d035/contracts/protocol/libraries/logic/SupplyLogic.sol#L65)


