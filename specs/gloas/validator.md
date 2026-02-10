<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`SignedBuilderAuth`](#signedbuilderauth)
  - [Validator Registrations](#validator-registrations)
    - [Constructing the `ValidatorRegistrationV2`](#constructing-the-validatorregistrationv2)
    - [Validator Registration dissemination](#validator-registration-dissemination)
  - [Bid Authentication](#bid-authentication)
    - [Receiving the `SignedBuilderAuth`](#receiving-the-signedbuilderauth)
  - [Validating a `SignedExecutionPayloadBid`](#validating-a-signedexecutionpayloadbid)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Receiving ExecutionPayloadBid](#receiving-executionpayloadbid)
  - [Liveness failsafe](#liveness-failsafe)

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

## Validator Registrations

### Constructing the `ValidatorRegistrationV2`

To register their preferences, the validator client assembles a
[`ValidatorRegistrationV2`][validator-registration-v2] with the following
information:

- `fee_recipient`: An execution layer address where fees for the validator
  should go.
- `gas_limit`: The value a validator prefers for the execution block gas limit.
- `validator_index`: The validator's index. Used to identify the beacon chain
  validator and verify the wrapping signature.
- `max_trusted_bid`: The amount(in Gwei) the proposer is willing to accept as a
- `builder_pubkey`: The BLS public key of the builder that this registration is
  specifically for.
- `proposal_slot`: This is set to the slot in which the validator will be
  proposing. This can be looked up in `state.proposer_lookahead`.

### Validator Registration dissemination

This specification suggests validators re-submit registrations only if they will
be proposing in the upcoming epoch(E+1). This is such that we do not send too
many validator registrations all at once to builders. Validators run
`create_validator_registrations` at every epoch boundary to create validator
registrations for all the slots they will be proposing in the upcoming epoch.

```python
def create_validator_registrations(
    state: BeaconState,
    validator_index: ValidatorIndex,
    gas_limit: uint64,
    builder_preferences: BuilderPreferences,
    fee_recipient: ExecutionAddress,
) -> List[ValidatorRegistrationV2]:
    slots = get_upcoming_proposal_slots(state, validator_index)
    registrations: List[ValidatorRegistrationV2] = []

    for slot in slots:
        registrations.append(
            ValidatorRegistrationV2(
                fee_recipient=fee_recipient,
                gas_limit=gas_limit,
                validator_index=validator_index,
                builder_preferences=builder_preferences,
                proposal_slot=slot,
            )
        )

    return registrations
```

## Bid Authentication

### Receiving a `SignedBuilderAuth`

A [`SignedBuilderAuth`](builder.md#signedbuilderauth) is expected to be returned by a builder in response to
receiving a valid `SignedValidatorRegistrationV2` using the
[`registerValidatorV2`][register-validator-v2-api] API call

The validator includes the `SignedBuilderAuth.signature` in the request path to
get the bid in the [`getExecutionPayloadBid`][get-execution-payload-bid-api] API
call. This builder-specific signature helps avoid replay attacks, where a
builder could send the bid request to another builder to make them do
unnecessary work.

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
    state: BeaconState,
    reg: SignedValidatorRegistrationV2,
    signed_bid: SignedExecutionPayloadBid,
    fee_recipient: ExecutionAddress,
) -> bool:
    bid = signed_bid.message

    assert is_active_builder(state, bid.builder_index)
    assert bid.slot == state.slot
    assert bid.fee_recipient == fee_recipient
    assert bid.parent_block_hash == state.latest_block_hash
    assert bid.parent_block_root == hash_tree_root(state.latest_block_header)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))
    assert bid.gas_limit <= reg.message.gas_limit

    assert bid.execution_payment <= reg.message.builder_preferences.max_trusted_bid

    if bid.value > 0:
        assert can_builder_cover_bid(state, bid.builder_index, bid.value)

    return verify_execution_payload_bid_signature(state, signed_bid)
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

To obtain execution payloads for a given `slot`, a block proposer building a
block on top of a beacon `state` must take the following actions:

1. Call upstream builder software to get a
   [`SignedBuilderAuth`][signed-builder-auth] using the
   [`registerValidatorV2`][register-validator-v2-api] API call.
2. Call upstream builder software to get a
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] using the
   [`getExecutionPayloadBid`][get-execution-payload-bid-api] API call. The
   validator is required to send the `SignedBuilderAuth.signature` in the
   request path in order to authenticate the request to the builder.
3. Assemble a `SignedBeaconBlock` according to the process outlined in the
   [Gloas validator specs][gloas-validator-specs] but with the best
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] from the prior
   step.
4. The proposer returns the `SignedBeaconBlock` back to the upstream block
   building software via [`submitSignedBeaconBlock`][submit-signed-beacon-block]
   API call.
5. The upstream block building software constructs the
   [`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope]
   corresponding to the
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] and broadcasts it
   to the PTC committee.

## Liveness failsafe

When the circuit breaker condition is triggered for nodes, they *MUST* fallback
to receiving bids from the P2P [`execution_payload_bid`][execution-payload-bid]
topic and can also build blocks locally.

[can-builder-cover-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#can_builder_cover_bid
[execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/p2p-interface.md?plain=1#L321
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[gloas-validator-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal
[is-active-builder]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#is_active_builder
[register-validator-v2-api]: ./../../apis/builder/validators_v2.yaml
[signed-builder-auth]: ./builder.md#signedbuilderauth
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-signed-beacon-block]: ./../../apis/builder/beacon_block.yaml
[validator-registration-v2]: ./builder.md#validatorregistrationv2
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#verify_execution_payload_bid_signature
