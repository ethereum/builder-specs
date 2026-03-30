<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
  - [Constants](#constants)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`BuilderPreferences`](#builderpreferences)
      - [`SignedBuilderPreferences`](#signedbuilderpreferences)
    - [`verify_builder_preferences_signature`](#verify_builder_preferences_signature)
  - [Bidding](#bidding)
  - [Builder Preferences](#builder-preferences)
  - [Proposer Preferences (Deprecation of Validator Registrations)](#proposer-preferences-deprecation-of-validator-registrations)
    - [`process_builder_preferences`](#process_builder_preferences)
  - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API post ePBS. It
describes how builders interact with validators through
[`BuilderPreferences`](#builderpreferences) and construct
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] and
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] objects.

## Constants

| Name              | Value       |
| ----------------- | ----------- |
| `MAX_TRUSTED_BID` | `2**64 - 1` |

## Containers

### New Containers

#### `BuilderPreferences`

```python
class BuilderPreferences(Container):
    builder_pubkey: BLSPubkey
    validator_pubkey: BLSPubkey
    proposal_slot: Slot
    max_trusted_bid: uint64
```

#### `SignedBuilderPreferences`

```python
class SignedBuilderPreferences(Container):
    message: BuilderPreferences
    signature: BLSSignature
```

### `verify_builder_preferences_signature`

*Note*: `compute_domain` and `compute_signing_root` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

```python
def verify_builder_preferences_signature(
    signed_preferences: SignedBuilderPreferences,
) -> bool:
    pubkey = signed_preferences.message.validator_pubkey
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER)
    signing_root = compute_signing_root(signed_preferences.message, domain)
    return bls.Verify(pubkey, signing_root, signed_preferences.signature)
```

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

    # Verify parent hash
    # [Modified in Gloas:EIP7732]
    assert parent_hash == state.latest_block_hash

    # Verify parent root
    # [Modified in Gloas:EIP7732]
    assert parent_root == hash_tree_root(state.latest_block_header)
```

## Builder Preferences

Validators send per-builder preferences directly to the builder via the
[`submitBuilderPreferences`][submit-builder-preferences-api] API call. This
allows a proposer to express trust preferences for a specific builder.
Currently, the only preference that is supported is:

- `max_trusted_bid`: Specifies the maximum value (in Gwei) that a proposer is
  willing to accept as a trusted execution layer payment from the builder. A
  value of `0` indicates that the proposer does not accept any trusted payments
  from the builder, requiring all payments to use the on-chain trustless
  payments mechanism. A value of `MAX_TRUSTED_BID` indicates that the proposer
  will accept any trusted payment amount from the builder. Proposers may adjust
  this parameter based on their level of trust in the builder's reliability and
  reputation.

The `builder_pubkey` field identifies which builder the preferences are intended
for.

## Proposer Preferences (Deprecation of Validator Registrations)

*Note*: `ValidatorRegistrationV1` is **deprecated** in favour of
[`ProposerPreferences`][proposer-preferences] from the consensus specs.

Builders SHOULD subscribe to the
[`proposer_preferences`][proposer-preferences-topic] gossip topic to learn about
a validator's general preferences. Validators broadcast these messages at the
beginning of each epoch for their proposal slots in the next epoch.

For per-builder preferences (such as `max_trusted_bid`), validators send
[`SignedBuilderPreferences`](#signedbuilderpreferences) directly to the builder
via the [`submitBuilderPreferences`][submit-builder-preferences-api] API call.

### `process_builder_preferences`

A `BuilderPreferences` message is considered valid if the following function
completes without raising any assertions.

```python
def process_builder_preferences(
    state: BeaconState,
    proposer_preferences: ProposerPreferences,
    signed_preferences: SignedBuilderPreferences,
    builder_preferences: Dict[ValidatorIndex, BuilderPreferences],
):
    preferences = signed_preferences.message

    validator_index = ValidatorIndex(state.validators.index(preferences.validator_pubkey))
    validator = state.validators[validator_index]

    # Verify validator is eligible
    assert is_eligible_for_registration(state, validator)

    # Verify that proposer preferences have been received via the gossip topic
    assert proposer_preferences.validator_index == validator_index

    # Verify the builder_pubkey matches the builder receiving the preferences
    # (implementation specific check)

    # Verify builder preferences signature
    assert verify_builder_preferences_signature(
        signed_preferences,
    )
```

## Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] is documented in the
[Gloas consensus specs][gloas-builder-specs].

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
[gloas-builder-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[proposer-preferences]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[proposer-preferences-topic]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-builder-preferences-api]: ./../../apis/builder/preferences.yaml
