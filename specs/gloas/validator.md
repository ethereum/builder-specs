<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Validator Registrations](#validator-registrations)
    - [Constructing the `ValidatorRegistrationV2`](#constructing-the-validatorregistrationv2)
    - [Validator Registration dissemination](#validator-registration-dissemination)
  - [Block proposal](#block-proposal)
      - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
        - [ExecutionPayloadBid](#executionpayloadbid)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Honest Validator


## Introduction

This document explains how a beacon-chain validator can participate in the external block building market post ePBS. 

Validators request an `ExecutionPayloadBid` from the external builder network to put it in their `SignedBeaconBlock`. 
The external builder network broadcasts the `SignedExecutionPayloadEnvelope` corresponding to the bid to the PTC commitee. 

## Helper

### `get_proposer_slots_in_upcoming_epoch`

```python
def get_proposer_slots_in_upcoming_epoch(
    state: BeaconState, 
    validator_index: ValidatorIndex
) -> List[Slot]:
    """
    Return all slots where validator_index is the proposer within the lookahead window in the next epoch.
    """
    proposer_slots = []
    current_epoch_start_slot = compute_start_slot_at_epoch(get_current_epoch(state))
    next_epoch_proposer_lookahead = state.proposer_lookahead[SLOTS_PER_EPOCH:]
    
    for i, proposer_index in enumerate(next_epoch_proposer_lookahead):
        if proposer_index == validator_index:
            slot = current_epoch_start_slot + SLOTS_PER_EPOCH + i
            proposer_slots.append(slot)
    
    return proposer_slots
```

## Validator Registrations 

### Constructing the `ValidatorRegistrationV2`

To do this, the validator client assembles a [`ValidatorRegistrationV2`][validator-registration-v2] with the following
information:

* `fee_recipient`: an execution layer address where fees for the validator should go.
* `builder_index`: the index of the builder to which this registration is being sent to.
* `gas_limit`: the value a validator prefers for the execution block gas limit.
* `validator_index`: the validator's index. Used to identify the beacon chain validator and verify the wrapping signature.
* `execution_payment_accepted`: whether the proposer is willing to accept a trusted payment from the builder with index 
  `builder_index`.
* `proposal_slot`: This is set to the slot in which the validator will be proposing. This can be looked up in the `proposal_lookahead`.


### Validator Registration dissemination

This specification suggests validators re-submit registrations only if they will be proposing in the upcoming epoch(E+1). 
This is such that we don't send too many validator registrations all at once to builders. 
Validators run `create_validator_registrations` at every epoch boundary to create validator registrations for all the slots
they will be proposing in the upcoming epoch.

```python
def create_validator_registrations(state: BeaconState, validator_index: ValidatorIndex, gas_limit: uint64, builder_index: BuilderIndex, execution_payment_accepted: bool) -> List[ValidatorRegistrationV2]:
    slots = get_proposer_slots_in_lookahead(state, validator_index)
    registrations: List[ValidatorRegistrationsV2] = []

    for slot in slots:
      registrations.append(ValidatorRegistrationV2(
        fee_recipient=fee_recipient,
        builder_index=builder_index,
        gas_limit=gas_limit,
        validator_index=validator_index
        execution_payment_accepted=execution_payment_accepted,
        proposal_slot=slot
      ))

  return registrations
```
## Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayloadBid

To obtain an execution payload, a block proposer building a block on top of a beacon `state` in a given `slot` must take
the following actions:

1. Call upstream builder software to get an `ExecutionPayloadBid`.
2. Assemble a `SignedBeaconBlock` according to the process outlined in the [Gloas specs][https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal] but with
   the `ExecutionPayloadBid` from the prior step.
3. The proposer returns the `SignedBeaconBlock` back to the upstream block
   building software.
5. The upstream block building software constructs the `SignedExecutionPayloadEnvelope` from the
   `SignedBlindedExecutionPayloadEnvelope` and broadcasts it to the PTC commitee.