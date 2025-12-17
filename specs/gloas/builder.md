<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
  - [Custom types](#custom-types)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`ValidatorRegistrationV2`](#validatorregistrationv2)
      - [`SignedValidatorRegistrationV2`](#signedvalidatorregistrationv2)
    - [`verify_registration_signature`](#verify_registration_signature)
  - [Validator Registration V2](#validator-registration-v2)
    - [`process_registration`](#process_registration)
  - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API.

## Custom types

| Name           | SSZ equivalent | Description            |
| -------------- | -------------- | ---------------------- |
| `BuilderIndex` | `uint64`       | Builder registry index |

## Containers

### New Containers

#### `ValidatorRegistrationV2`

```python
class ValidatorRegistrationV2(Container):
    builder_pubkey: BLSPubkey ## is this needed? 
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    timestamp: uint64
    pubkey: BLSPubkey
    can_accept_trusted_payment: bool
    proposal_epoch: Epoch
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
    pubkey = signed_registration.message.pubkey
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER)
    signing_root = compute_signing_root(signed_registration.message, domain)
    return bls.Verify(pubkey, signing_root, signed_registration.signature)
```

## Validator Registration V2

The second version of ValidatorRegistrations adds the following new fields:
* `builder_pubkey`: The pubkey of the builder to which this registration is being sent.
* `can_accept_trusted_payment`: This is a boolean which indicates that the validator is willing accept a trusted
  execution layer payment from the builder to which it is sending the registrations.
* `proposal_epoch`: The epoch at which this validator is proposing.

### `process_registration`

```python
def process_registration(state: BeaconState,
                         registration: SignedValidatorRegistrationV2,
                         registrations: Dict[BLSPubkey, ValidatorRegistrationV2],
                         current_timestamp: uint64):
    signature = registration.signature
    registration = registration.message
    pubkey = registration.pubkey
    builder_pubkey = registration.builder_pubkey

    # Verify BLS public key corresponds to a registered validator
    validator_pubkeys = [v.pubkey for v in state.validators]
    assert pubkey in validator_pubkeys

    index = ValidatorIndex(validator_pubkeys.index(pubkey))
    validator = state.validators[index]

    # [New in Gloas]
    builder_pubkeys = [b.pubkey for v in state.builders]
    assert builder_pubkey in builder_pubkeys 

    # Verify validator registration elibility
    assert is_eligible_for_registration(state, validator)

    # Verify timestamp is not too far in the future
    assert registration.timestamp <= current_timestamp + MAX_REGISTRATION_LOOKAHEAD

    # Verify timestamp is not less than the timestamp of the previous registration (if it exists)
    if registration.pubkey in registrations:
        prev_registration = registrations[registration.pubkey]
        assert registration.timestamp >= prev_registration.timestamp

    # Verify registration signature
    assert verify_registration_signature(state, registration)
```


## Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a `SignedExecutionPayloadBid` is documented in the 
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].

## Constructing a `SignedExecutionPayloadEnvelope`

The specification for a block builder to construct a `SignedExecutionPayloadEnvelope` is documented in the 
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].