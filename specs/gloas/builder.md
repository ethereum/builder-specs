<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
  - [Constants](#constants)
  - [Bidding](#bidding)
  - [Builder Preferences](#builder-preferences)
    - [`max_trusted_bid`](#max_trusted_bid)
  - [Per-request Validator Inputs](#per-request-validator-inputs)
  - [Proposer Preferences (Deprecation of Validator Registrations)](#proposer-preferences-deprecation-of-validator-registrations)
  - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API post ePBS. It
describes how builders consume per-request inputs from validators and construct
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] and
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] objects.

## Constants

| Name              | Value       |
| ----------------- | ----------- |
| `MAX_TRUSTED_BID` | `2**64 - 1` |

## Bidding

In Gloas, Execution payloads are built for a specific `slot`, `parent_hash`,
`validator_index` along with the `parent_root` tuple corresponding to a unique
beacon block serving as the parent.

This is because in Gloas with [EIP-7732], the execution payload and beacon
blocks are decoupled. The `parent_hash` could refer to a beacon block which is
an ancestor of the parent beacon block corresponding to the current beacon block
for which we are building the execution payload.

We update `is_eligible_for_bid` below. *Note*: `hash_tree_root` is defined in
the [Gloas consensus specs][gloas-consensus-specs].

```python
def is_eligible_for_bid(
    state: BeaconState,
    proposer_preferences: Dict[ValidatorIndex, ProposerPreferences],
    slot: Slot,
    parent_hash: Hash32,
    # [New in Gloas]
    parent_root: Root,
    # [New in Gloas]
    validator_index: ValidatorIndex,
):
    # Verify slot
    assert slot == state.slot

    assert validator_index in state.validators.keys()

    # Verify that proposer preferences have been received via the gossip topic
    assert validator_index in proposer_preferences.keys()

    # Verify parent hash. The proposer could build on the FULL parent block or on the EMPTY parent block based on
    # their view of the chain.
    # [Modified in Gloas:EIP7732]
    assert (
        parent_hash == state.latest_execution_payload_bid.block_hash
        or parent_hash == state.latest_block_hash
    )

    # Verify parent root
    # [Modified in Gloas:EIP7732]
    assert parent_root == hash_tree_root(state.latest_block_header)
```

## Builder Preferences

Validators MAY communicate their per-builder preferences ahead of the bid
request by calling the [`submitBuilderPreferences`][submit-builder-preferences-api]
API in the epoch prior to the epoch in which they will be proposing, as
determined from `state.lookahead`. The builder receives a `BuilderPreferencesRequest` object containing:

- `preferences`: A `BuilderPreferences` with:
  - `max_trusted_bid`: The maximum trusted execution layer payment the proposer
    will accept from this builder (in Gwei).
  - `validator_pubkey`: The BLS public key of the validator submitting these
    preferences.
- `auth`: A `SignedRequestAuth` authenticating the request. The builder MUST
  check that `auth.message.builder_pubkey` matches its own identity and MUST
  verify the BLS signature against `preferences.validator_pubkey`. If either
  check fails, the builder MUST return a 400 response.

The builder MUST store the preferences for each proposer and apply the
`max_trusted_bid` constraint when constructing bids. If no preferences have been
submitted for a proposer, the builder MUST treat the proposer's `max_trusted_bid`
as `0`.

### `max_trusted_bid`

`max_trusted_bid` is the maximum value (in Gwei) that a proposer is willing to
accept as a trusted execution layer payment from this builder. A value of `0`
indicates that the proposer does not accept any trusted payments from the
builder, requiring all payments to use the on-chain trustless payments mechanism.
A value of `MAX_TRUSTED_BID` indicates that the proposer will accept any trusted
payment amount from the builder. Proposers may adjust this parameter based on
their level of trust in the builder's reliability and reputation.

## Per-request Validator Inputs

Validators communicate per-request inputs to a builder on each
[`getExecutionPayloadBid`][get-execution-payload-bid-api] call:

- Optionally, the `X-Eth-Max-Trusted-Bid` header carrying a decimal `uint64`
  (in Gwei) with the proposer's `max_trusted_bid` for this request. MAY be
  omitted if the proposer has already submitted a `BuilderPreferencesRequest`
  to this builder. If a stored `BuilderPreferences` exists for the proposer,
  it takes precedence over this header.
- Optionally, a [`SignedRequestAuth`][signed-request-auth] in the request body
  used to authenticate the requesting validator. The body MAY be encoded as JSON
  (`Content-Type: application/json`) or SSZ
  (`Content-Type: application/octet-stream`); when SSZ is used, the
  `Eth-Consensus-Version` header MUST also be set.

The builder resolves `max_trusted_bid` in the following order of precedence:
1. Stored `BuilderPreferences` for the proposer, if previously submitted.
2. The `X-Eth-Max-Trusted-Bid` header, if present on this request.
3. `0`, if neither is available.

If the request body is present, builders MAY verify the `SignedRequestAuth`
signature against the validator pubkey resolved from the `proposer_index` path
parameter, and check that `builder_pubkey` matches their own identity and that
`slot` matches the requested slot. If verification fails, the builder MAY return
a 400 response.

If the request body is absent, the builder MAY still serve a bid.

## Proposer Preferences (Deprecation of Validator Registrations)

*Note*: `ValidatorRegistrationV1` is **deprecated** in favor of
[`ProposerPreferences`][proposer-preferences] from the consensus specs.

Builders SHOULD subscribe to the
[`proposer_preferences`][proposer-preferences-topic] gossip topic to learn about
a validator's general preferences. Validators broadcast these messages at the
beginning of each epoch for their proposal slots in the next epoch.

## Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] is documented in the
[Gloas consensus specs][gloas-builder-specs].

`bid.fee_recipient` MUST be set to the fee recipient from the proposer's
[`ProposerPreferences`][proposer-preferences], regardless of whether the builder
pays via `bid.execution_payment` or `bid.value`.

If the builder intends to pay the proposer via their staked collateral, they
MUST set `bid.value` to the amount they are committing to pay.

If the builder intends to pay the proposer via an execution layer payment, they
MUST set `bid.execution_payment`. This value MUST NOT exceed the
`max_trusted_bid` received in the `X-Eth-Max-Trusted-Bid` header of the
corresponding [`getExecutionPayloadBid`][get-execution-payload-bid-api] request.

*Note*: `bid.value` and `bid.execution_payment` are not mutually exclusive.
A builder MAY set both fields on a single bid; in that case the builder is
committing to pay the proposer the sum of the two. `bid.value` is deducted
from the builder's staked collateral on-chain even when
`bid.execution_payment` is also set.

## Constructing a `SignedExecutionPayloadEnvelope`

If the builder's [`SignedExecutionPayloadBid`][signed-execution-payload-bid] has
been accepted by the proposer and it has been included in its
`SignedBeaconBlock`, then the builder has to construct a
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope]
corresponding to the [`SignedExecutionPayloadBid`][signed-execution-payload-bid]
and it has to broadcast via the `execution_payload_envelope` gossip topic.

The specification for a block builder to construct a
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] is
documented in the [Gloas consensus specs][gloas-builder-specs].

[eip-7732]: https://eips.ethereum.org/EIPS/eip-7732
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[submit-builder-preferences-api]: ./../../apis/builder/builder_preferences.yaml
[gloas-builder-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[proposer-preferences]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[proposer-preferences-topic]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[signed-request-auth]: ./validator.md#signedrequestauth
