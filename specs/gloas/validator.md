<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`BidRequestAuth`](#bidrequestauth)
      - [`SignedBidRequestAuth`](#signedbidrequestauth)
  - [Helper](#helper)
    - [`get_proposer_slots_in_upcoming_epoch`](#get_proposer_slots_in_upcoming_epoch)
  - [Bid Authentication](#bid-authentication)
    - [Constructing the `BidRequestAuth`](#constructing-the-bidrequestauth)
  - [Validator Registrations](#validator-registrations)
    - [Constructing the `ValidatorRegistrationV2`](#constructing-the-validatorregistrationv2)
    - [Validator Registration dissemination](#validator-registration-dissemination)
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
corresponding to the bid to the PTC committee.

## Containers

### New Containers

#### `BidRequestAuth`

`BidRequestAuth` is used to authenticate requests to get the bid from a builder.
This is useful so that other builders don't DDOS the builder to get their latest
bid.

```python
class BidRequestAuth(Container):
  builder_index: BuilderIndex
  validator_index: ValidatorIndex
  proposer_slot: Slot
```

#### `SignedBidRequestAuth`

```python
class SignedBidRequestAuth(Container):
  message: BidRequestAuth
  signature: BLSSignature
```

## Helper

### `get_proposer_slots_in_upcoming_epoch`

*Note*: `compute_start_slot_at_epoch` and `get_current_epoch` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

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
    
    for offset, proposer_index in enumerate(next_epoch_proposer_lookahead):
        if proposer_index == validator_index:
            slot = current_epoch_start_slot + SLOTS_PER_EPOCH + offset
            proposer_slots.append(slot)
    
    return proposer_slots
```

## Bid Authentication

### Constructing the `BidRequestAuth`

To construct the `BidRequestAuth`, we need to fill the following information:

- `builder_index`: This builder index for which the validator is sending a
  request to get the bid.
- `validator_index`: The proposer's validator index.
- `proposal_slot`: The slot at which the proposer is building a block.

The validator constructs the `SignedBidRequestAuth` by signing the
`BidRequestAuth`. It sends the `SignedBidRequestAuth` in the request body along
with the request to get the bid in the
[`getExecutionPayloadBid`][get-execution-payload-bid-api] API call.

## Validator Registrations

### Constructing the `ValidatorRegistrationV2`

To do this, the validator client assembles a
[`ValidatorRegistrationV2`][validator-registration-v2] with the following
information:

- `fee_recipient`: An execution layer address where fees for the validator
  should go.
- `gas_limit`: The value a validator prefers for the execution block gas limit.
- `validator_index`: The validator's index. Used to identify the beacon chain
  validator and verify the wrapping signature.
- `max_trusted_bid`: The amount(in Gwei) the proposer is willing to accept as a
  trusted execution layer payment from the builder.
- `proposal_slot`: This is set to the slot in which the validator will be
  proposing. This can be looked up in `state.proposal_lookahead`.

### Validator Registration dissemination

This specification suggests validators re-submit registrations only if they will
be proposing in the upcoming epoch(E+1). This is such that we don't send too
many validator registrations all at once to builders. Validators run
`create_validator_registrations` at every epoch boundary to create validator
registrations for all the slots they will be proposing in the upcoming epoch.

```python
def create_validator_registrations(state: BeaconState, validator_index: ValidatorIndex, gas_limit: uint64, builder_preferences: BuilderPreferences) -> List[ValidatorRegistrationV2]:
    slots = get_proposer_slots_in_upcoming_epoch(state, validator_index)
    registrations: List[ValidatorRegistrationV2] = []

    for slot in slots:
        registrations.append(ValidatorRegistrationV2(
            fee_recipient=fee_recipient,
            gas_limit=gas_limit,
            validator_index=validator_index,
            builder_preferences=builder_preferences,
            proposal_slot=slot
        ))

    return registrations
```

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
    state: BeaconState, reg: SignedValidatorRegistrationV2, bid: SignedExecutionPayloadBid, bid_request_auth: SignedBidRequestAuth, fee_recipient: ExecutionAddress
) -> bool:
    bid = bid.message

    assert bid.builder_index == bid_request_auth.message.builder_index

    builder = state.builders[bid.builder_index]
    
    assert is_active_builder(state, builder)
    assert bid.slot == state.slot
    assert bid.fee_recipient == fee_recipient
    assert bid.parent_block_hash == state.latest_block_hash
    assert bid.parent_block_root == hash_tree_root(state.latest_block_header)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))

    assert bid.execution_payment <= reg.message.builder_preferences.max_trusted_bid

    if bid.value > 0:
        assert can_builder_cover_bid(state, bid.builder_index, signed_bid.value)

    return verify_execution_payload_bid_signature(state, bid)
```

Note that, the fee recipient specified in `bid.fee_recipient` does not
necessarily correspond to the fee recipient of the execution payload. Even if a
builder pays the validator via execution layer payments, we require that the
bid's fee recipient matches the validators expected fee recipient and not the
builder's fee recipient.

To express per-builder preferences we need validators to remember which
registration they have sent to the builder, so that they can validate whether
the bid conforms to the preferences expressed by the validators.

## Block proposal

### Constructing the `BeaconBlockBody`

#### Receiving ExecutionPayloadBid

To obtain an execution payload, a block proposer building a block on top of a
beacon `state` in a given `slot` must take the following actions:

1. Call upstream builder software to get a
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] using the
   [`getExecutionPayloadBid`][get-execution-payload-bid-api] API call. The
   validator is required to send the `SignedBidRequestAuth` in the request body
   in order to authenticate the request to the builder. If a builder has
   multiple builder indices associated with them, the validator will have to
   call the upstream builder software each time for each builder index.
2. Assemble a `SignedBeaconBlock` according to the process outlined in the
   [Gloas validator specs][gloas-validator-specs] but with the best
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] from the prior
   step.
3. The proposer returns the `SignedBeaconBlock` back to the upstream block
   building software via [`submitSignedBeaconBlock`][submit-signed-beacon-block]
   API call.
4. The upstream block building software constructs the
   [`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope]
   corresponding to the
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] and broadcasts it
   to the PTC committee.

[can-builder-cover-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#can_builder_cover_bid
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[gloas-validator-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal
[is-active-builder]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#is_active_builder
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-signed-beacon-block]: ./../../apis/builder/beacon_block.yaml
[validator-registration-v2]: ./builder.md#validatorregistrationv2
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#verify_execution_payload_bid_signature
