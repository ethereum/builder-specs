# Gloas - Bid Scoring

## Overview

This document specifies how a validator selects the best execution payload bid
from among bids received over the p2p network, bids received via the offchain
builder API, and a locally built block.

Bids from the two sources are scored differently because offchain bids carry an
`execution_payment` component that is conditionally trusted up to the
`max_trusted_bid` the validator expressed for that request.

`min_bid` from `GlobalPreferences` applies equally to both p2p and offchain
bids. There is no separate threshold per source.

## Scoring

### P2P Bids

P2P bids are scored solely by `bid.value`, the on-chain collateral commitment.
`bid.execution_payment` is ignored for p2p bids because there is no per-request
`max_trusted_bid` negotiation over gossip.

A p2p bid is eligible only if `bid.value > min_bid`.

```python
def select_best_p2p_bid(
    bids: List[SignedExecutionPayloadBid],
    min_bid: uint64,
) -> Optional[SignedExecutionPayloadBid]:
    eligible = [b for b in bids if b.message.value > min_bid]
    if not eligible:
        return None
    return max(eligible, key=lambda b: b.message.value)
```

### Offchain (Builder API) Bids

For bids received via the offchain builder API, the total bid score accounts for
both the on-chain collateral commitment and the trusted execution layer payment,
capped at the `max_trusted_bid` the validator advertised for that request:

```
bid_score = bid.value + min(bid.execution_payment, max_trusted_bid)
```

A bid is eligible only if `bid_score > min_bid`, the same threshold applied to
p2p bids.

```python
def score_offchain_bid(
    bid: ExecutionPayloadBid,
    max_trusted_bid: uint64,
) -> uint64:
    return bid.value + min(bid.execution_payment, max_trusted_bid)

def select_best_offchain_bid(
    bids: List[Tuple[SignedExecutionPayloadBid, uint64]],
    min_bid: uint64,
) -> Optional[SignedExecutionPayloadBid]:
    """
    `bids` is a list of (signed_bid, max_trusted_bid) pairs, where
    max_trusted_bid is the value sent in the X-Eth-Max-Trusted-Bid header of
    the corresponding getExecutionPayloadBid request.
    """
    eligible = [
        (b, score_offchain_bid(b.message, max_trusted_bid))
        for b, max_trusted_bid in bids
        if score_offchain_bid(b.message, max_trusted_bid) > min_bid
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda pair: pair[1])[0]
```

### Selecting the Best Bid

Once the best p2p bid and best offchain bid are identified, the validator
compares them against the locally built block using `local_block_boost`.

`local_block_boost` is a multiplier (in basis points, where `10000 = 100%`)
applied to the local block value before comparison. A value of `10000` means no
boost; a value of `11000` means the local block must be beaten by at least 10%
for an external bid to be preferred.

```python
def select_best_bid(
    local_block_value: uint64,
    best_p2p_bid: Optional[SignedExecutionPayloadBid],
    best_offchain_bid: Optional[SignedExecutionPayloadBid],
    max_trusted_bid_for_offchain: uint64,
    global_preferences: GlobalPreferences,
) -> Optional[SignedExecutionPayloadBid]:
    boosted_local = local_block_value * global_preferences.local_block_boost // 10000

    best_external: Optional[SignedExecutionPayloadBid] = None
    best_external_score: uint64 = 0

    if best_p2p_bid is not None:
        p2p_score = best_p2p_bid.message.value
        if p2p_score > best_external_score:
            best_external = best_p2p_bid
            best_external_score = p2p_score

    if best_offchain_bid is not None:
        offchain_score = score_offchain_bid(best_offchain_bid.message, max_trusted_bid_for_offchain)
        if offchain_score > best_external_score:
            best_external = best_offchain_bid
            best_external_score = offchain_score

    if best_external is not None and best_external_score > boosted_local:
        return best_external

    return None  # fall back to local block
```

Returning `None` indicates the validator should propose its locally built block.
