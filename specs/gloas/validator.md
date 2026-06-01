<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`RequestAuthV1`](#requestauthv1)
      - [`SignedRequestAuthV1`](#signedrequestauthv1)
      - [`BuilderPreferencesV1`](#builderpreferencesv1)
      - [`BuilderPreferencesRequestV1`](#builderpreferencesrequestv1)
  - [Submitting Builder Preferences](#submitting-builder-preferences)
    - [`max_execution_payment`](#max_execution_payment)
  - [Bid Request](#bid-request)
    - [Constructing the `RequestAuthV1`](#constructing-the-requestauthv1)
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

#### `RequestAuthV1`

`RequestAuthV1` is used to authenticate requests to a builder. This is useful so
that other builders do not DDOS or run replay attacks on the builder.

```python
class RequestAuthV1(Container):
    builder_url: ByteList[MAX_URL_SIZE]
    slot: Slot
```

#### `SignedRequestAuthV1`

```python
class SignedRequestAuthV1(Container):
    message: RequestAuthV1
    signature: BLSSignature
```

#### `BuilderPreferencesV1`

`BuilderPreferencesV1` communicates a proposer's per-builder preferences to a
specific builder ahead of the bid request.

```python
class BuilderPreferencesV1(Container):
    max_execution_payment: Gwei
```

#### `BuilderPreferencesRequestV1`

```python
class BuilderPreferencesRequestV1(Container):
    preferences: BuilderPreferencesV1
    auth: SignedRequestAuthV1
```

## Submitting Builder Preferences

The validator MAY submit its
[`BuilderPreferencesRequestV1`](#builderpreferencesrequestv1) to each builder
via the [`submitBuilderPreferences`][submit-builder-preferences-api] API call in
the epoch prior to the epoch in which they will be proposing, as determined from
`state.lookahead`. This ensures builders have the preferences before the bid
request arrives.

The validator constructs a `BuilderPreferencesV1` with:

- `max_execution_payment`: The maximum trusted execution layer payment the
  proposer will accept from this builder. See
  [`max_execution_payment`](#max_execution_payment).

The validator's BLS public key is passed as the `validator_pubkey` path
parameter in the [`submitBuilderPreferences`][submit-builder-preferences-api]
API call.

The validator then constructs a `BuilderPreferencesRequestV1` with the
`BuilderPreferencesV1` as `preferences` and a `SignedRequestAuthV1` as `auth`.
The `SignedRequestAuthV1` is constructed as described in
[Constructing the `RequestAuthV1`](#constructing-the-requestauthv1); its
`auth.message.builder_url` identifies the intended builder. The builder MUST
verify the `auth` signature against the `validator_pubkey` path parameter and
MUST reject the request with a 400 response if `auth.message.builder_url` does
not match its own URL.

If no preferences have been submitted, the builder MUST treat the proposer's
`max_execution_payment` as `0`.

### `max_execution_payment`

`max_execution_payment` is the maximum value (in Gwei) that the proposer is
willing to accept as a trusted execution layer payment from this builder. A
value of `0` means the proposer does not accept any execution payments from this
builder, requiring all payments to go through the on-chain trustless payments
mechanism. A value of `MAX_EXECUTION_PAYMENT` means the proposer will accept any
execution payment amount from the builder. Proposers may adjust this parameter
based on their level of trust in the builder's reliability and reputation.

`max_execution_payment` is communicated exclusively via the
[`submitBuilderPreferences`][submit-builder-preferences-api] endpoint. If no
`BuilderPreferencesV1` have been submitted to a builder, that builder MUST NOT
include an execution layer payment in its bid.

## Bid Request

When calling [`getExecutionPayloadBid`][get-execution-payload-bid-api], the
validator MAY send a [`SignedRequestAuthV1`](#signedrequestauthv1) as the
request body to authenticate the request. The body MAY be encoded as JSON
(`Content-Type: application/json`) or SSZ
(`Content-Type: application/octet-stream`); when SSZ is used, the validator MUST
also send the `Eth-Consensus-Version` header. If the body is omitted, the
builder MAY still serve a bid.

### Constructing the `RequestAuthV1`

If the validator chooses to authenticate its request, it constructs a
`RequestAuthV1` with the following fields:

- `builder_url`: The URL of the builder the request is intended for.
- `slot`: The slot for which the request is being sent.

The proposer's public key is already carried as a path parameter in the relevant
API request, so it does not need to be carried inside `RequestAuthV1`.

The validator then constructs the `SignedRequestAuthV1` by signing the
`RequestAuthV1`. The signature lets builders authenticate the requesting
validator and discard requests from other parties (e.g. DDOS or replay attempts
from competing builders).

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
    max_execution_payment: uint64,
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

    assert bid.execution_payment <= max_execution_payment

    if bid.value > 0:
        assert can_builder_cover_bid(state, bid.builder_index, bid.value)

    return verify_execution_payload_bid_signature(state, signed_bid)
```

`max_execution_payment` is the value from the `BuilderPreferencesV1` the
validator submitted to this builder via
[`submitBuilderPreferences`][submit-builder-preferences-api]. Validators MUST
validate each bid against the `max_execution_payment` they submitted for that
builder.

Note that the fee recipient specified in `bid.fee_recipient` does not
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
   validator MAY send a `SignedRequestAuthV1` in the request body to
   authenticate the request.
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
[submit-builder-preferences-api]: ./../../apis/builder/builder_preferences.yaml
[submit-signed-beacon-block]: ./../../apis/builder/beacon_block.yaml
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#verify_execution_payload_bid_signature
