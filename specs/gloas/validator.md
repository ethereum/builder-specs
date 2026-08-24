<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`BuilderRequestAuth`](#builderrequestauth)
      - [`SignedBuilderRequestAuth`](#signedbuilderrequestauth)
      - [`BuilderPreferences`](#builderpreferences)
      - [`BuilderPreferencesRequest`](#builderpreferencesrequest)
  - [Submitting Builder Preferences](#submitting-builder-preferences)
    - [`max_execution_payment`](#max_execution_payment)
  - [Bid Request](#bid-request)
    - [Constructing the `BuilderRequestAuth`](#constructing-the-builderrequestauth)
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

#### `BuilderRequestAuth`

`BuilderRequestAuth` is used to authenticate requests to a builder. This is
useful so that other builders do not DDOS or run replay attacks on the builder.

```python
class BuilderRequestAuth(Container):
    data: ByteList[MAX_BUILDER_AUTH_DATA_SIZE]
    slot: Slot
```

#### `SignedBuilderRequestAuth`

```python
class SignedBuilderRequestAuth(Container):
    message: BuilderRequestAuth
    signature: BLSSignature
```

#### `BuilderPreferences`

`BuilderPreferences` communicates a proposer's per-builder preferences to a
specific builder ahead of the bid request.

```python
class BuilderPreferences(Container):
    max_execution_payment: Gwei
```

#### `BuilderPreferencesRequest`

```python
class BuilderPreferencesRequest(Container):
    preferences: BuilderPreferences
    auth: SignedBuilderRequestAuth
```

## Submitting Builder Preferences

The validator MAY submit its
[`BuilderPreferencesRequest`](#builderpreferencesrequest) to each builder via
the [`submitBuilderPreferences`][submit-builder-preferences-api] API call in the
epoch prior to the epoch in which they will be proposing, as determined from
`state.proposer_lookahead`. This ensures builders have the preferences before
the bid request arrives.

The validator constructs a `BuilderPreferences` with:

- `max_execution_payment`: The maximum execution layer payment the proposer will
  accept from this builder. See
  [`max_execution_payment`](#max_execution_payment).

The validator then constructs a `BuilderPreferencesRequest` with the
`BuilderPreferences` as `preferences` and a `SignedBuilderRequestAuth` as
`auth`, and submits it to the
[`submitBuilderPreferences`][submit-builder-preferences-api] endpoint for its
`proposer_pubkey`. The `SignedBuilderRequestAuth` is constructed as described in
[Constructing the `BuilderRequestAuth`](#constructing-the-builderrequestauth);
its `auth.message.data` is the authentication data the builder expects and its
`auth.message.slot` is the proposal slot the preferences apply to. The builder
MUST verify the `auth` signature against the `proposer_pubkey` path parameter,
returning a 401 response if it fails to verify, and MUST reject the request with
a 400 response if `auth.message.data` does not match the value it agreed with
the proposer. The builder MUST also reject, with a 400 response, a request whose
`auth.message.slot` has already passed, so that a replay cannot roll preferences
back to a stale value.

A builder MUST honor the `max_execution_payment` cap in any bid it serves for a
slot it has stored preferences for; without them it MAY serve a bid with any
`execution_payment`. The proposer's locally configured per-builder limits are
the backstop: the proposer values a bid at its `value` plus
`min(execution_payment, max_execution_payment)`, so payment above the cap adds
nothing to the bid's chances.

### `max_execution_payment`

`max_execution_payment` is the maximum value (in Gwei) that the proposer is
willing to accept as an execution layer payment from this builder. A value of
`0` means the proposer does not accept any execution payments from this builder,
requiring all payments to go through the on-chain trustless payments mechanism.
A value of `MAX_EXECUTION_PAYMENT` means the proposer will accept any execution
payment amount from the builder. Proposers may adjust this parameter based on
their level of trust in the builder's reliability and reputation.

`max_execution_payment` is communicated exclusively via the
[`submitBuilderPreferences`][submit-builder-preferences-api] endpoint.

## Bid Request

When calling [`getExecutionPayloadBid`][get-execution-payload-bid-api], the
validator MUST send a [`SignedBuilderRequestAuth`](#signedbuilderrequestauth) as
the request body to authenticate the request. The body MAY be encoded as JSON
(`Content-Type: application/json`) or SSZ
(`Content-Type: application/octet-stream`); `BuilderRequestAuth` is
fork-versioned, so the `Eth-Consensus-Version` header is required. Proposer
duties are known an epoch in advance, so the validator can sign the
`SignedBuilderRequestAuth` ahead of time, off the proposal hot path.

### Constructing the `BuilderRequestAuth`

The validator constructs a `BuilderRequestAuth` with the following fields:

- `data`: opaque authentication data agreed with the builder out of band whose
  meaning is left to the two parties. It is not tied to an endpoint, so one
  `SignedBuilderRequestAuth` can authenticate the proposer for both
  `getExecutionPayloadBid` and `submitBuilderPreferences`. When no value has
  been agreed out of band, the validator SHOULD use the UTF-8 bytes of the
  builder's own advertised URL, exactly as advertised. A zero-length `data` is
  invalid.
- `slot`: The proposal slot this request is authorized for, not the slot at
  which the request is signed or sent.

The proposer's public key is already carried as a path parameter in the relevant
API request, so it does not need to be carried inside `BuilderRequestAuth`.

The validator then constructs the `SignedBuilderRequestAuth` by signing the
`BuilderRequestAuth`. The signature lets builders authenticate the requesting
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
[`can_builder_cover_bid`][can-builder-cover-bid],
[`is_gas_limit_target_compatible`][is-gas-limit-target-compatible], and
[`verify_execution_payload_bid_signature`][verify-execution-payload-bid-signature]
are also defined in the consensus specs.

```python
def validate_bid(
    state: BeaconState,
    proposer_preferences: ProposerPreferences,
    parent_gas_limit: uint64,
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
    assert is_gas_limit_target_compatible(
        parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit
    )

    if bid.value > 0:
        assert can_builder_cover_bid(state, bid.builder_index, bid.value)

    return verify_execution_payload_bid_signature(state, signed_bid)
```

`parent_gas_limit` is the gas limit of the parent execution payload identified
by `bid.parent_block_hash`.

The validator's locally configured `max_execution_payment`, the same value it
submits via [`submitBuilderPreferences`][submit-builder-preferences-api] when it
submits preferences, is not a validity condition: it caps how much of
`bid.execution_payment` counts when the bid is valued, whether or not
preferences were submitted.

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
   validator signs a `SignedBuilderRequestAuth` and the beacon node sends it
   unchanged in the request body to authenticate the request.
2. Assemble a `SignedBeaconBlock` according to the process outlined in the
   [Gloas validator specs][gloas-validator-specs] but with the best
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] from the prior
   step.
3. The validator publishes the `SignedBeaconBlock` to its beacon node, which
   returns it to the upstream block building software via
   [`submitSignedBeaconBlock`][submit-signed-beacon-block] API call. The
   validator does not call builders directly.
4. The upstream block building software constructs the corresponding
   [`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] and
   broadcasts it to the PTC committee.

[can-builder-cover-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#new-can_builder_cover_bid
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[gloas-validator-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal
[is-active-builder]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#new-is_active_builder
[is-gas-limit-target-compatible]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md#new-is_gas_limit_target_compatible
[proposer-preferences]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md#new-proposerpreferences
[proposer-preferences-topic]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md#new-proposer_preferences
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-builder-preferences-api]: ./../../apis/builder/builder_preferences.yaml
[submit-signed-beacon-block]: ./../../apis/builder/beacon_blocks.yaml
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#new-verify_execution_payload_bid_signature
