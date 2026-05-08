<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`RequestAuth`](#requestauth)
      - [`SignedRequestAuth`](#signedrequestauth)
  - [Bid Request](#bid-request)
    - [Constructing the `RequestAuth`](#constructing-the-requestauth)
    - [`max_trusted_bid`](#max_trusted_bid)
  - [Proposer Preferences](#proposer-preferences)
  - [Validating a `SignedExecutionPayloadBid`](#validating-a-signedexecutionpayloadbid)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Receiving ExecutionPayloadBid](#receiving-executionpayloadbid)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Honest Validator

## Introduction

This document explains how a beacon-chain validator can participate in the
external block building market with the Builder-API post ePBS.

Validators request a [`SignedExecutionPayloadBid`][signed-execution-payload-bid]
from the external builder network to put it in their `SignedBeaconBlock`. The
external builder network broadcasts the
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope]
corresponding to the included bid to the PTC committee.

## Containers

### New Containers

#### `RequestAuth`

`RequestAuth` is used to authenticate requests to a builder. This is useful so
that other builders do not DDOS or run replay attacks on the builder.

```python
class RequestAuth(Container):
    builder_pubkey: BLSPubkey
    validator_pubkey: BLSPubkey
    slot: Slot
```

#### `SignedRequestAuth`

```python
class SignedRequestAuth(Container):
    message: RequestAuth
    signature: BLSSignature
```

## Bid Request

When calling [`getExecutionPayloadBid`][get-execution-payload-bid-api], the
validator MUST send the `X-Eth-Max-Trusted-Bid` header carrying a decimal
`uint64` (in Gwei) expressing the per-builder `max_trusted_bid` for this
request. See [`max_trusted_bid`](#max_trusted_bid). If the header is missing,
the builder will not serve a bid for the proposer.

The validator MAY additionally send a [`SignedRequestAuth`](#signedrequestauth)
as the request body to authenticate the request. The body MAY be encoded as JSON
(`Content-Type: application/json`) or SSZ
(`Content-Type: application/octet-stream`); when SSZ is used, the validator MUST
also send the `Eth-Consensus-Version` header. If the body is omitted, the
builder MAY still serve a bid.

### Constructing the `RequestAuth`

If the validator chooses to authenticate its request, it constructs a
`RequestAuth` with the following fields:

- `builder_pubkey`: The BLS public key of the builder the request is intended
  for.
- `validator_pubkey`: The BLS public key of the validator making the request.
- `slot`: The slot for which the bid is being requested.

The validator then constructs the `SignedRequestAuth` by signing the
`RequestAuth`, and sends it in the body of the
[`getExecutionPayloadBid`][get-execution-payload-bid-api] request. The signature
lets builders authenticate the requesting validator and discard requests from
other parties (e.g. DDOS or replay attempts from competing builders).

### `max_trusted_bid`

`max_trusted_bid` is the maximum value (in Gwei) that the proposer is willing to
accept as a trusted execution layer payment from this builder for this request.
A value of `0` means the proposer does not accept any trusted payments from this
builder, requiring all payments to go through the on-chain trustless payments
mechanism. A value of `MAX_TRUSTED_BID` means the proposer will accept any
trusted payment amount from the builder. Proposers may adjust this parameter
based on their level of trust in the builder's reliability and reputation.

The validator sends `max_trusted_bid` as a decimal `uint64` in the
`X-Eth-Max-Trusted-Bid` header. Note that `max_trusted_bid` is **not** covered
by the `RequestAuth` signature. The validator MUST remember the
`max_trusted_bid` value it sent for each request so it can validate the
resulting bid against the same value.

## Proposer Preferences

*Note*: Validator registrations (`ValidatorRegistrationV1`) are **deprecated**
in favor of [`ProposerPreferences`][proposer-preferences] from the consensus
specs.

General validator preferences are now communicated via the
[`proposer_preferences`][proposer-preferences-topic] gossip topic defined in the
[Gloas consensus specs][gloas-consensus-specs]. At the beginning of each epoch,
validators broadcast [`SignedProposerPreferences`][proposer-preferences]
messages for their proposal slots in the next epoch.

Builders SHOULD subscribe to this gossip topic to learn about proposer
preferences for upcoming slots.

Per-builder preferences (currently just `max_trusted_bid`) are not gossiped;
they are sent directly to the builder as a header on each
[`getExecutionPayloadBid`][get-execution-payload-bid-api] request. See
[`max_trusted_bid`](#max_trusted_bid).

## Validating a `SignedExecutionPayloadBid`

When the proposer receives a
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] from a builder, it
can validate the bid using `validate_bid`. It can discard the bid if the
conditions are not satisfied.

*Note*: `hash_tree_root`, `get_randao_mix`, and `get_current_epoch` are defined
in the [Gloas consensus specs][gloas-consensus-specs]. The predicates
[`is_active_builder`][is-active-builder],
[`can_builder_cover_bid`][can-builder-cover-bid], and
[`verify_execution_payload_bid_signature`][verify-execution-payload-bid-signature]
are also defined in the consensus specs.

```python
def validate_bid(
    state: BeaconState,
    proposer_preferences: ProposerPreferences,
    max_trusted_bid: uint64,
    signed_bid: SignedExecutionPayloadBid,
    fee_recipient: ExecutionAddress,
) -> bool:
    bid = signed_bid.message

    assert is_active_builder(state, bid.builder_index)
    assert bid.slot == state.slot
    assert bid.fee_recipient == fee_recipient
    # Bid can choose to extend on FULL or EMPTY.
    assert (
        bid.parent_block_hash == state.latest_execution_payload_bid.block_hash
        or bid.parent_block_hash == state.latest_block_hash
    )
    assert bid.parent_block_root == hash_tree_root(state.latest_block_header)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))
    assert bid.gas_limit <= proposer_preferences.gas_limit

    assert bid.execution_payment <= max_trusted_bid

    if bid.value > 0:
        assert can_builder_cover_bid(state, bid.builder_index, bid.value)

    return verify_execution_payload_bid_signature(state, signed_bid)
```

`max_trusted_bid` is the value the validator sent in the `X-Eth-Max-Trusted-Bid`
header of the corresponding
[`getExecutionPayloadBid`][get-execution-payload-bid-api] request. Validators
MUST validate each bid against the `max_trusted_bid` they sent for that request.

Note that, the fee recipient specified in `bid.fee_recipient` does not
necessarily correspond to the fee recipient of the execution payload. Even if a
builder pays the validator via execution layer payments, we require that the
bid's fee recipient matches the validators expected fee recipient and not the
builder's fee recipient.

## Block proposal

### Constructing the `BeaconBlockBody`

#### Receiving ExecutionPayloadBid

To obtain execution payloads for a given `slot`, a block proposer building a
block on top of a beacon `state` must take the following actions:

1. Call upstream builder software to get a
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] using the
   [`getExecutionPayloadBid`][get-execution-payload-bid-api] API call. The
   validator MUST include the `X-Eth-Max-Trusted-Bid` header on the request;
   otherwise the builder will not serve a bid. The validator MAY additionally
   send a `SignedRequestAuth` in the request body to authenticate the request.
2. Assemble a `SignedBeaconBlock` according to the process outlined in the
   [Gloas validator specs][gloas-validator-specs] but with the best
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] from the prior
   step.
3. The proposer returns the `SignedBeaconBlock` back to the upstream block
   building software via [`submitSignedBeaconBlock`][submit-signed-beacon-block]
   API call.
4. The upstream block building software constructs the corresponding
   [`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] and
   broadcasts it to the PTC committee.

[can-builder-cover-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#can_builder_cover_bid
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[gloas-validator-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal
[is-active-builder]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#is_active_builder
[proposer-preferences]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[proposer-preferences-topic]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-signed-beacon-block]: ./../../apis/builder/beacon_block.yaml
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#verify_execution_payload_bid_signature
