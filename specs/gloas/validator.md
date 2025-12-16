<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
    - [Block proposal](#block-proposal)
      - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
        - [ExecutionPayloadBid](#executionpayloadbid)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Honest Validator


## Introduction

This document explains how a beacon-chain validator can participate in the external block building market post ePBS. 

Validators request an `ExecutionPayloadBid` from the external builder network to put it in their `SignedBeaconBlock`. 
The external builder network broadcasts the `SignedExecutionPayloadEnvelope` corresponding to the bid to the PTC commitee. 

## Validator Registrations 

### Constructing the `ValidatorRegistrationV2`

To do this, the validator client assembles a [`ValidatorRegistrationV2`][validator-registration-v2] with the following
information:

* `fee_recipient`: an execution layer address where fees for the validator should go.
* `builder_pubkey`: the pubkey of the builder to which this registration is being sent to.
* `gas_limit`: the value a validator prefers for the execution block gas limit.
* `timestamp`: a recent timestamp later than any previously constructed `ValidatorRegistrationV1`.
  Builders use this timestamp as a form of anti-DoS and to sequence registrations.
* `pubkey`: the validator's public key. Used to identify the beacon chain validator and verify the wrapping signature.
* `can_accept_trusted_payment`: whether the proposer is willing to accept a trusted payment from the builder with pubkey 
  `builder_pubkey`.
* `proposal_epoch`: This is set to `get_current_epoch(state) + 1`.


### Validator Registration dissemination

This specification suggests validators re-submit registrations only if they will be proposing in the upcoming epoch(E+1). 
This is to avoid sending a lot of `ValidatorRegistrations` every epoch. This can potentially help reduce the load 
Validators are expected to perform this check at every epoch boundary. Validators can send their registrations even though
they won't be proposing in the upcoming epoch.

```python
def is_next_epoch_proposer(state: BeaconState, validator_index: ValidatorIndex) -> bool:
    """
    Check if ``validator_index`` is scheduled to propose in the next epoch.
    """
    next_epoch_proposers = state.proposer_lookahead[SLOTS_PER_EPOCH:]
    return validator_index in next_epoch_proposers
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