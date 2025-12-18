<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
  - [Custom types](#custom-types)
  - [Predicates](#predicates)
    - [`is_active_builder`](#is_active_builder)
  - [Helper Functions](#helper-functions)
      - [`compute_epoch_at_slot`](#compute_epoch_at_slot)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`BuilderPreferences`](#builderpreferences)
      - [`ValidatorRegistrationV2`](#validatorregistrationv2)
      - [`SignedValidatorRegistrationV2`](#signedvalidatorregistrationv2)
    - [`verify_registration_signature`](#verify_registration_signature)
  - [Builder Preferences](#builder-preferences)
  - [Validator Registration V2](#validator-registration-v2)
    - [`process_registration_v2`](#process_registration_v2)
  - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API.

## Custom types

| Name | SSZ equivalent | Description | | -------------- | -------------- |
---------------------- | | `BuilderIndex` | `uint64` | Builder registry index |

## Predicates

### `is_active_builder`

```python
def is_active_builder(builder: Builder) -> bool:
    """
    Check if ``builder`` is active.
    """
    return builder.exit_epoch == FAR_FUTURE_EPOCH
```

## Helper Functions

#### `compute_epoch_at_slot`

```python
def compute_epoch_at_slot(slot: Slot) -> Epoch:
    """
    Return the epoch number at ``slot``.
    """
    return Epoch(slot // SLOTS_PER_EPOCH)
```

## Containers

### New Containers

#### `BuilderPreferences`

```python
class BuilderPreferences(Container):
    execution_payment_accepted: boolean
```

#### `ValidatorRegistrationV2`

```python
class ValidatorRegistrationV2(Container):
    builder_index: BuilderIndex 
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

### `verify_registration_signature`

```python
def verify_registration_signature(state: BeaconState, signed_registration: SignedValidatorRegistrationV2) -> bool:
    validator = state.validators[signed_registration.message.validator_index]
    pubkey = validator.pubkey
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER)
    signing_root = compute_signing_root(signed_registration.message, domain)
    return bls.Verify(pubkey, signing_root, signed_registration.signature)
```

## Builder Preferences

Using validator registrations, a proposer can express the preferences it has for
a builder. Currently, the only preference that is supported is:

- `execution_payment_accepted`: This is a boolean which indicates that the
  proposer is willing to accept a trusted execution layer payment from the
  builder.

## Validator Registration V2

The second version of ValidatorRegistrations adds the following new fields:

- `builder_index`: The index of the builder to which this registration is being
  sent.
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
completes without raising any assertions:

```python
def process_registration_v2(state: BeaconState,
                         registration: SignedValidatorRegistrationV2,
                         registrations: Dict[BLSPubkey, ValidatorRegistrationV2],
                         current_timestamp: uint64):
    signature = registration.signature
    registration = registration.message
    validator_index = registration.validator_index
    builder_index = registration.builder_index
    proposal_slot = registration.proposal_slot

    assert validator_index < len(state.validators)
    assert builder_index < len(state.builders)

    validator = state.validators[validator_index]
    builder = state.builders[builder_index]

    assert is_active_validator(validator, compute_epoch_at_slot(proposal_slot))
    assert is_active_builder(builder)

    # Verify validator registration elibility
    assert is_eligible_for_registration(state, validator)

    # Verify that the old registration's slot is earlier than the new registration's slot
    if registration.pubkey in registrations:
        prev_registration = registrations[validator_index]
        assert registration.proposal_slot >= prev_registration.proposal_slot

    # Verify registration signature
    assert verify_registration_signature(state, registration)
```

## Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a `SignedExecutionPayloadBid`
is documented in the
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].

## Constructing a `SignedExecutionPayloadEnvelope`

The specification for a block builder to construct a
`SignedExecutionPayloadEnvelope` is documented in the
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].
