<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`RequestAuth`](#requestauth)
      - [`SignedRequestAuth`](#signedrequestauth)
  - [Bid Authentication](#bid-authentication)
    - [Constructing the `RequestAuth`](#constructing-the-requestauth)
  - [Proposer Preferences](#proposer-preferences)
  - [Builder Preferences](#builder-preferences)
    - [Constructing the `BuilderPreferences`](#constructing-the-builderpreferences)
    - [Builder Preferences dissemination](#builder-preferences-dissemination)
  - [Validating a `SignedExecutionPayloadBid`](#validating-a-signedexecutionpayloadbid)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Receiving ExecutionPayloadBid](#receiving-executionpayloadbid)
  - [Liveness failsafe](#liveness-failsafe)

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
    slot: Slot
```

#### `SignedRequestAuth`

```python
class SignedRequestAuth(Container):
    message: RequestAuth
    signature: BLSSignature
```

## Bid Authentication

### Constructing the `RequestAuth`

To construct the `RequestAuth`, we need to fill the following information:

- `builder_pubkey`: The BLS public key of the builder the request is intended
  for.
- `slot`: The slot for which the bid is being requested.

The validator constructs the `SignedRequestAuth` by signing the `RequestAuth`.
It sends the `SignedRequestAuth` in the request body along with the request to
get the bid in the [`getExecutionPayloadBid`][get-execution-payload-bid-api] API
call.

## Proposer Preferences

*Note*: Validator registrations (`ValidatorRegistrationV1`) are **deprecated**
in favour of [`ProposerPreferences`][proposer-preferences] from the consensus
specs.

General validator preferences are now communicated via the
[`proposer_preferences`][proposer-preferences-topic] gossip topic defined in the
[Gloas consensus specs][gloas-consensus-specs]. At the beginning of each epoch,
validators broadcast [`SignedProposerPreferences`][proposer-preferences]
messages for their proposal slots in the next epoch containing:

- `fee_recipient`: An execution layer address where fees for the validator
  should go.
- `gas_limit`: The value a validator prefers for the execution block gas limit.
- `validator_index`: The validator's index.
- `proposal_slot`: The slot in which the validator will be proposing. This can
  be looked up in `state.proposer_lookahead`.

Builders SHOULD subscribe to this gossip topic to learn about proposer
preferences for upcoming slots.

## Builder Preferences

For per-builder preferences that cannot be communicated via a global gossip
topic, validators send [`SignedBuilderPreferences`][builder-preferences]
directly to the builder via the
[`submitBuilderPreferences`][submit-builder-preferences-api] API call.

### Constructing the `BuilderPreferences`

To construct the `BuilderPreferences`, the validator client assembles a
[`BuilderPreferences`][builder-preferences] with the following information:

- `builder_pubkey`: The BLS public key of the builder that these preferences are
  intended for.
- `slot`: The proposal slot of the validator. This can be looked up in
  `state.proposer_lookahead`.
- `max_trusted_bid`: The amount (in Gwei) the proposer is willing to accept as a
  trusted execution layer payment from the builder.

### Builder Preferences dissemination

Validators send builder preferences to each builder they wish to interact with
for their upcoming proposal slots. Validators run `create_builder_preferences`
in the epoch prior to the epoch in which the validator will become a proposer,
using the `proposer_lookahead` in the beacon state to determine their proposal
slots.

```python
def create_builder_preferences(
    builder_pubkey: BLSPubkey,
    slot: Slot,
    max_trusted_bid: uint64,
) -> BuilderPreferences:
    return BuilderPreferences(
        builder_pubkey=builder_pubkey,
        slot=slot,
        max_trusted_bid=max_trusted_bid,
    )
```

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
    builder_preferences: BuilderPreferences,
    signed_bid: SignedExecutionPayloadBid,
    fee_recipient: ExecutionAddress,
) -> bool:
    bid = signed_bid.message

    assert is_active_builder(state, bid.builder_index)
    assert bid.slot == state.slot
    assert bid.fee_recipient == fee_recipient
    assert bid.parent_block_hash == state.latest_block_hash
    assert bid.parent_block_root == hash_tree_root(state.latest_block_header)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))
    assert bid.gas_limit <= proposer_preferences.gas_limit

    assert bid.execution_payment <= builder_preferences.max_trusted_bid

    if bid.value > 0:
        assert can_builder_cover_bid(state, bid.builder_index, bid.value)

    return verify_execution_payload_bid_signature(state, signed_bid)
```

Note that, the fee recipient specified in `bid.fee_recipient` does not
necessarily correspond to the fee recipient of the execution payload. Even if a
builder pays the validator via execution layer payments, we require that the
bid's fee recipient matches the validators expected fee recipient and not the
builder's fee recipient.

To express per-builder preferences we need validators to remember which builder
preferences they have sent to each builder, so that they can validate whether
the bid conforms to the preferences expressed by the validators.

## Block proposal

### Constructing the `BeaconBlockBody`

#### Receiving ExecutionPayloadBid

To obtain execution payloads for a given `slot`, a block proposer building a
block on top of a beacon `state` must take the following actions:

1. Call upstream builder software to get a
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] using the
   [`getExecutionPayloadBid`][get-execution-payload-bid-api] API call. The
   validator is required to send the `SignedRequestAuth` in the request body in
   order to authenticate the request to the builder.
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

## Liveness failsafe

When the circuit breaker condition is triggered for nodes, they *MUST* fallback
to receiving bids from the P2P [`execution_payload_bid`][execution-payload-bid]
topic and can also build blocks locally.

[builder-preferences]: ./builder.md#builderpreferences
[can-builder-cover-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#can_builder_cover_bid
[execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md?plain=1#L321
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[gloas-validator-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal
[is-active-builder]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#is_active_builder
[proposer-preferences]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[proposer-preferences-topic]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-builder-preferences-api]: ./../../apis/builder/preferences.yaml
[submit-signed-beacon-block]: ./../../apis/builder/beacon_block.yaml
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#verify_execution_payload_bid_signature
