<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`BuilderPreferences`](#builderpreferences)
      - [`ValidatorRegistrationV2`](#validatorregistrationv2)
      - [`SignedValidatorRegistrationV2`](#signedvalidatorregistrationv2)
    - [`verify_registration_v2_signature`](#verify_registration_v2_signature)
  - [Bidding](#bidding)
  - [Builder Preferences](#builder-preferences)
  - [Validator Registration V2](#validator-registration-v2)
    - [`process_registration_v2`](#process_registration_v2)
  - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API post ePBS. It
describes how builders interact with validators through
\[`ValidatorRegistrationV2`\][validator-registration-v2] and construct
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] and
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] objects.

## Containers

### New Containers

#### `BuilderPreferences`

```python
class BuilderPreferences(Container):
    max_trusted_bid: uint64
```

#### `ValidatorRegistrationV2`

```python
class ValidatorRegistrationV2(Container):
    validator_index: ValidatorIndex
    fee_recipient: ExecutionAddress
    proposal_slot: Slot
    gas_limit: uint64
    builder_preferences: BuilderPreferences
```

#### `SignedValidatorRegistrationV2`

```python
class SignedValidatorRegistrationV2(Container):
    message: ValidatorRegistrationV2
    signature: BLSSignature
```

### `verify_registration_v2_signature`

*Note*: `compute_domain` and `compute_signing_root` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

```python
def verify_registration_v2_signature(state: BeaconState, signed_registration: SignedValidatorRegistrationV2) -> bool:
    validator = state.validators[signed_registration.message.validator_index]
    pubkey = validator.pubkey
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER)
    signing_root = compute_signing_root(signed_registration.message, domain)
    return bls.Verify(pubkey, signing_root, signed_registration.signature)
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
def is_eligible_for_bid(state: BeaconState,
                        registrations: Dict[ValidatorIndex, ValidatorRegistrationV2],
                        slot: Slot,
                        parent_hash: Hash32,
                        # [New in Gloas]
                        parent_root: Root,
                        # [New in Gloas]
                        validator_index: ValidatorIndex):
    # Verify slot
    assert slot == state.slot

    assert validator_index in state.validator.keys()

    assert validator_index in registrations.keys()

    # Verify parent hash
    # [Modified in Gloas:EIP7732]
    assert parent_hash == state.latest_block_hash

    # Verify parent root
    # [Modified in Gloas:EIP7732]
    assert parent_root == hash_tree_root(state.latest_block_header)
```

## Builder Preferences

Using validator registrations, a proposer can express the preferences it has for
a builder. Currently, the only preference that is supported is:

- `max_trusted_bid`: Specifies the maximum value (in Gwei) that a proposer is
  willing to accept as a trusted execution layer payment from the builder. A
  value of `0` indicates that the proposer does not accept any trusted payments
  from the builder, requiring all payments to be cryptographically verifiable
  on-chain. A value of `UINT64_MAX` indicates that the proposer will accept any
  trusted payment amount from the builder. Proposers may adjust this parameter
  based on their level of trust in the builder's reliability and reputation.

## Validator Registration V2

The second version of ValidatorRegistrations adds the following new fields:

- `validator_index`: The index of the validator selected to propose a block at
  slot `proposal_slot`
- `builder_preferences`: This is a struct which contains the per builder
  preferences the proposer has.
- `proposal_slot`: The slot at which this validator is proposing.

The following fields are removed:

- `pubkey`: This is the pubkey of the validator which has now been replaced with
  `validator_index`.
- `timestamp`: A new validator registration will be sent by the validator to the
  builder in the epoch prior to one where they will be proposing.

### `process_registration_v2`

A `validator_registration_v2` is considered valid if the following function
completes without raising any assertions.

```python
def process_registration_v2(state: BeaconState,
                         registration: SignedValidatorRegistrationV2,
                         registrations: Dict[ValidatorIndex, ValidatorRegistrationV2],
                         current_timestamp: uint64):
    signature = registration.signature
    registration = registration.message
    validator_index = registration.validator_index
    proposal_slot = registration.proposal_slot

    validator = state.validators[validator_index]

    # Verify validator registration eligibility
    assert is_eligible_for_registration(state, validator)

    # Verify that the old registration's proposal slot is earlier than the new registration's proposal slot
    if validator_index in registrations.keys():
        prev_registration = registrations[validator_index]
        assert registration.proposal_slot >= prev_registration.proposal_slot

    # Verify registration signature
    assert verify_registration_v2_signature(state, registration)
```

## Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a
[`SignedExecutionPayloadBid`][signed-execution-payload-bid] is documented in the
[Gloas consensus specs][gloas-builder-specs].

## Constructing a `SignedExecutionPayloadEnvelope`

If the builder's [`SignedExecutionPayloadBid`][signed-execution-payload-bid] has
been accepted by the proposer and it has been included in it's
`SignedBeaconBlock`, then the builder has to construct a
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope]
corresponding to the [`SignedExecutionPayloadBid`][signed-execution-payload-bid]
and it has to broadcast it to the PTC committee via the
`execution_payload_envelope` gossip topic.

The specification for a block builder to construct a
[`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] is
documented in the [Gloas consensus specs][gloas-builder-specs].

[eip-7732]: https://eips.ethereum.org/EIPS/eip-7732
[gloas-builder-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
