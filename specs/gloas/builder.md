<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
  - [Constants](#constants)
  - [Bidding](#bidding)
  - [Builder Preferences](#builder-preferences)
    - [`max_execution_payment`](#max_execution_payment)
  - [Per-request Validator Inputs](#per-request-validator-inputs)
  - [Proposer Preferences (Deprecation of Validator Registrations)](#proposer-preferences-deprecation-of-validator-registrations)
  - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
    - [Signing](#signing)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API post ePBS. It
describes how builders consume per-request inputs from validators and construct
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] and
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] objects.

## Constants

| Name                          | Value                      |
| ----------------------------- | -------------------------- |
| `MAX_EXECUTION_PAYMENT`       | `2**64 - 1`                |
| `MAX_BUILDER_AUTH_DATA_SIZE`  | `4096`                     |
| `DOMAIN_BUILDER_REQUEST_AUTH` | `DomainType('0x0B000001')` |

## Bidding

In Gloas, Execution payloads are built for a specific `slot`, `parent_hash`,
`validator_index` along with the `parent_root` tuple corresponding to a unique
beacon block serving as the parent.

This is because with ePBS, the beacon block and execution payload are decoupled.
The `parent_hash` could be associated with a different beacon block as that of
`parent_root`.

We update `is_eligible_for_bid` below. *Note*: `hash_tree_root` and
`get_beacon_proposer_index` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

```python
def is_eligible_for_bid(
    state: BeaconState,
    # [Removed in Gloas]
    # registrations: Dict[BLSPubkey, ValidatorRegistrationV1]
    # [New in Gloas]
    proposer_preferences: Dict[ValidatorIndex, ProposerPreferences],
    slot: Slot,
    parent_hash: Hash32,
    # [New in Gloas]
    parent_root: Root,
    pubkey: BLSPubkey,
):
    # Verify slot
    assert slot == state.slot

    # Verify proposer pubkey matches the expected proposer for this slot
    validator_index = get_beacon_proposer_index(state)
    assert state.validators[validator_index].pubkey == pubkey

    # Verify the proposer is active
    assert is_active_validator(
        state.validators[validator_index], get_current_epoch(state)
    )

    # Verify that proposer preferences have been received via the gossip topic
    # [New in Gloas:EIP7732]
    assert validator_index in proposer_preferences.keys()

    # Verify parent hash. The proposer could build on the FULL parent block or on the EMPTY parent block based on
    # their view of the chain.
    # [New in Gloas:EIP7732]
    assert (
        parent_hash == state.latest_execution_payload_bid.block_hash
        or parent_hash == state.latest_block_hash
    )

    # Verify parent root
    # [New in Gloas:EIP7732]
    assert parent_root == hash_tree_root(state.latest_block_header)
```

## Builder Preferences

Validators MAY communicate their per-builder preferences ahead of the bid
request by calling the
[`submitBuilderPreferences`][submit-builder-preferences-api] API in the epoch
prior to the epoch in which they will be proposing, as determined from
`state.proposer_lookahead`. The proposer is identified by the `proposer_pubkey`
path parameter, and the builder receives a `BuilderPreferencesRequest` object
containing:

- `preferences`: A `BuilderPreferences` with:
  - `max_execution_payment`: The maximum execution layer payment the proposer
    will accept from this builder (in Gwei).
- `auth`: A `SignedBuilderRequestAuth` authenticating the request.
  `auth.message.slot` is the proposal slot the preferences apply to. The builder
  MUST verify the BLS signature against the `proposer_pubkey` path parameter and
  MUST check that `auth.message.data` matches the value it agreed with the
  proposer, so that an unauthenticated or replayed request cannot skew a
  proposer's preferences away from the value the proposer chose. If the
  signature fails to verify, the builder MUST return a 401 response; if the
  `auth.message.data` check fails, the builder MUST return a 400 response. The
  builder MUST also reject, with a 400 response, preferences whose
  `auth.message.slot` has already passed, so that a replayed request cannot roll
  preferences back to a stale value.

The builder SHOULD store the preferences per proposer per `auth.message.slot`
and MUST honor the `max_execution_payment` cap in any bid it serves for that
slot. Without preferences stored for the requested slot it MAY serve a bid with
any `execution_payment`. The proposer's locally configured per-builder limits
are the backstop: the proposer values a bid at its `value` plus
`min(execution_payment, max_execution_payment)`, so payment above the cap adds
nothing to the bid's chances.

### `max_execution_payment`

`max_execution_payment` is the maximum value (in Gwei) that a proposer is
willing to accept as an execution layer payment from this builder. A value of
`0` indicates that the proposer does not accept any execution payments from the
builder, requiring all payments to use the on-chain trustless payments
mechanism. A value of `MAX_EXECUTION_PAYMENT` indicates that the proposer will
accept any execution layer payment amount from the builder. Proposers may adjust
this parameter based on their level of trust in the builder's reliability and
reputation.

## Per-request Validator Inputs

Validators communicate per-request inputs to a builder on each
[`getExecutionPayloadBid`][get-execution-payload-bid-api] call:

- A [`SignedBuilderRequestAuth`][signed-request-auth] in the request body
  authenticating the requesting validator. The body is required and MAY be
  encoded as JSON (`Content-Type: application/json`) or SSZ
  (`Content-Type: application/octet-stream`); `BuilderRequestAuth` is
  fork-versioned, so the `Eth-Consensus-Version` header is required.
- A required `Date-Milliseconds` header with the Unix timestamp in milliseconds
  at which the request was sent, and a required `X-Timeout-Ms` header with the
  proposer's timeout for the request, measured from `Date-Milliseconds`. The
  timestamp lets the builder estimate the transit delay from proposer to
  builder; the builder MUST respond by `Date-Milliseconds` plus `X-Timeout-Ms`,
  and the proposer discards later responses.

The `Eth-Consensus-Version` header is required on every request that carries a
body, naming the fork of the body's type. The builder MUST return a 400 response
when the header is absent or names a fork it does not recognize.

The proposer's `max_execution_payment` is communicated exclusively via the
[`submitBuilderPreferences`][submit-builder-preferences-api] endpoint. A bid
MUST honor the `max_execution_payment` cap from stored preferences; without them
the builder MAY serve a bid with any `execution_payment`.

Builders MUST verify the `SignedBuilderRequestAuth` signature against the
`proposer_pubkey` path parameter, and MUST check that `auth.message.data`
matches the value they agreed with the proposer and that `auth.message.slot`
matches the proposal `slot` path parameter (see
[Constructing the `BuilderRequestAuth`][constructing-builder-request-auth]). The
signature is verified with [`verify_builder_request_auth_signature`](#signing).
If the signature fails to verify, the builder MUST return a 401 response; if the
`auth.message.data` or `auth.message.slot` check fails, the builder MUST return
a 400 response. A missing or malformed body is an invalid request and the
builder MUST return a 400 response.

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
`max_execution_payment` from the proposer's stored `BuilderPreferences`. Without
stored preferences the builder MAY set any `bid.execution_payment`; when valuing
the bid, the proposer counts the payment at no more than its locally configured
cap.

*Note*: `bid.value` and `bid.execution_payment` are not mutually exclusive. A
builder MAY set both fields on a single bid; in that case the builder is
committing to pay the proposer the sum of the two. `bid.value` is deducted from
the builder's staked collateral on-chain even when `bid.execution_payment` is
also set.

### Signing

All signature operations follow the [standard BLS operations][bls] interface
defined in `consensus-specs`.

The [`SignedBuilderRequestAuth`][signed-request-auth] is an out-of-protocol
Builder API message, specific to this API and analogous to the now-deprecated
`ValidatorRegistrationV1`. It is signed and verified under
`DOMAIN_BUILDER_REQUEST_AUTH`. This domain MUST NOT be confused with
`DOMAIN_BEACON_BUILDER`, which is used for in-protocol builder messages defined
by the consensus specs.

Signing and verification compute the signing root with `compute_signing_root`
over the `BuilderRequestAuth` message, as shown below. A beacon node that
forwards a `SignedBuilderRequestAuth` MUST pass its `message` and `signature`
through unchanged, so a builder verifies exactly what the validator signed.

```python
def get_builder_request_auth_signature(
    request_auth: BuilderRequestAuth,
    privkey: int,
) -> BLSSignature:
    domain = compute_domain(DOMAIN_BUILDER_REQUEST_AUTH)
    signing_root = compute_signing_root(request_auth, domain)
    return bls.Sign(privkey, signing_root)


def verify_builder_request_auth_signature(
    signed_builder_request_auth: SignedBuilderRequestAuth,
    pubkey: BLSPubkey,
) -> bool:
    domain = compute_domain(DOMAIN_BUILDER_REQUEST_AUTH)
    signing_root = compute_signing_root(signed_builder_request_auth.message, domain)
    return bls.Verify(pubkey, signing_root, signed_builder_request_auth.signature)
```

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

[bls]: https://github.com/ethereum/consensus-specs/blob/master/specs/phase0/beacon-chain.md#bls-signatures
[constructing-builder-request-auth]: ./validator.md#constructing-the-builderrequestauth
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-builder-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[proposer-preferences]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md#new-proposerpreferences
[proposer-preferences-topic]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md#new-proposer_preferences
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[signed-request-auth]: ./validator.md#signedbuilderrequestauth
[submit-builder-preferences-api]: ./../../apis/builder/builder_preferences.yaml
