<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
  - [Constants](#constants)
  - [Containers](#containers)
    - [New Containers](#new-containers)
    - [`BidRequestAuth`](#bidrequestauth)
    - [`SignedBidRequestAuth`](#signedbidrequestauth)
    - [`BlindedExecutionPayloadEnvelope`](#blindedexecutionpayloadenvelope)
    - [`SignedBlindedExecutionPayloadEnvelope`](#signedblindedexecutionpayloadenvelope)
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
      - [Receiving ExecutionPayloadBid from Unstaked Builder](#receiving-executionpayloadbid-from-unstaked-builder)
    - [`process_blinded_execution_payload`](#process_blinded_execution_payload)
    - [`construct_blinded_envelope`](#construct_blinded_envelope)

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

## Constants

| Name | Value | | ----------------------------------------- |
------------------ | | `MAX_SALT_BYTES` | `4096` |

## Containers

### New Containers

### `BidRequestAuth`

`BidRequestAuth` is used to authenticate requests to get the bid from a builder.
This is useful so that other builders do not DDOS the builder to get their
latest bid.

```python
class BidRequestAuth(Container):
    salt: ByteList[MAX_SALT_BYTES]
```

### `SignedBidRequestAuth`

```python
class SignedBidRequestAuth(Container):
    message: BidRequestAuth
    signature: BLSSignature
```

### `BlindedExecutionPayloadEnvelope`

```python
class BlindedExecutionPayloadEnvelope(Container):
    payload_root: Root
    execution_requests: ExecutionRequests
    builder_index: BuilderIndex
    beacon_block_root: Root
    slot: Slot
    blob_kzg_commitments_root: Root
    state_root: Root
```

### `SignedBlindedExecutionPayloadEnvelope`

```python
class SignedBlindedExecutionPayloadEnvelope(Container):
    message: BlindedExecutionPayloadEnvelope
    signature: BLSSignature
```

## Helper

### `get_proposer_slots_in_upcoming_epoch`

*Note*: `compute_start_slot_at_epoch` and `get_current_epoch` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

```python
def get_proposer_slots_in_upcoming_epoch(
    state: BeaconState, validator_index: ValidatorIndex
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

- `salt`: This is a 4kB salt which has to be specific to each whitelisted
  builder. The spec requires the proposer to set it to the URL provided by the
  whitelisted builder.

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
    slots = get_proposer_slots_in_upcoming_epoch(state, validator_index)
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
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] using the
   [`getExecutionPayloadBid`][get-execution-payload-bid-api] API call. The
   validator is required to send the `SignedBidRequestAuth` in the request body
   in order to authenticate the request to the builder.
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

#### Receiving ExecutionPayloadBid from Unstaked Builder

For unstaked builders, the flow is different. To obtain execution payloads from
an unstaked builder for a given `slot`, a block proposer building a block on top
of a beacon `state` must take the following actions:

1. Call the unstaked builder to get a [`SignedBuilderBid`][signed-builder-bid]
   using the [`getBuilderBid`][get-builder-bid-api] API call. The bid contains:

   - An `ExecutionPayloadHeader`
   - Blob KZG commitments
   - Execution requests
   - A `SignedExecutionPayloadBid` with `builder_index` set to
     `BUILDER_INDEX_SELF_BUILD`

2. Assemble a `SignedBeaconBlock` according to the process outlined in the
   [Gloas validator specs][gloas-validator-specs] using the
   [`SignedExecutionPayloadBid`][signed-execution-payload-bid] from the builder
   bid.

3. Construct a `SignedBlindedExecutionPayloadEnvelope` by:

   - Setting `beacon_block_root` to
     `hash_tree_root(signed_beacon_block.message)`
   - Setting `payload_root` to the root of the execution payload (from header)
   - Setting `execution_requests_root` to the root of execution requests
   - Setting `blob_kzg_commitments_root` to the root of blob commitments
   - Setting `builder_index` to `BUILDER_INDEX_SELF_BUILD`
   - Setting `slot` to the block's slot
   - Setting `state_root` to the post-state root
   - Signing with the proposer's key

4. Submit both the `SignedBeaconBlock` and
   `SignedBlindedExecutionPayloadEnvelope` to the unstaked builder via the
   [`submitBlockAndEnvelope`][submit-block-and-envelope-api] API call.

5. The unstaked builder constructs the full
   [`SignedExecutionPayloadEnvelope`][signed-execution-payload-envelope] by
   unblinding the envelope and broadcasts it to the PTC committee.

### `process_blinded_execution_payload`

```python
def process_blinded_execution_payload(
    state: BeaconState,
    header: ExecutionPayloadHeader,
    builder_bid: BuilderBid,
    blinded_envelope: SignedBlindedExecutionPayloadEnvelope,
) -> None:
    envelope = blinded_envelope.message

    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed bid
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.blob_kzg_commitments_root == hash_tree_root(
        builder_bid.blob_kzg_commitments
    )
    assert committed_bid.prev_randao == header.prev_randao

    # Verify consistency with expected withdrawals
    assert header.withdrawals_root == hash_tree_root(state.payload_expected_withdrawals)

    # Verify the gas_limit
    assert committed_bid.gas_limit == header.gas_limit
    # Verify the block hash
    assert committed_bid.block_hash == header.block_hash
    # Verify consistency of the parent hash with respect to the previous execution payload
    assert header.parent_hash == state.latest_block_hash
    # Verify timestamp
    assert header.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(builder_bid.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )
    # Verify the execution payload is valid
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment)
        for commitment in builder_bid.blob_kzg_commitments
    ]

    def for_ops(
        operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]
    ) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(builder_bid.execution_requests.deposits, process_deposit_request)
    for_ops(builder_bid.execution_requests.withdrawals, process_withdrawal_request)
    for_ops(builder_bid.execution_requests.consolidations, process_consolidation_request)

    # Queue the builder payment
    payment = state.builder_pending_payments[
        SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH
    ]
    amount = payment.withdrawal.amount
    if amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH] = (
        BuilderPendingPayment()
    )

    # Cache the execution payload hash
    state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = header.block_hash
```

### `construct_blinded_envelope`

*Note*: `hash_tree_root` and `compute_domain` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

```python
def construct_blinded_envelope(
    state: BeaconState,
    signed_block: SignedBeaconBlock,
    builder_bid: BuilderBid,
    privkey: int,
) -> SignedBlindedExecutionPayloadEnvelope:
    block = signed_block.message

    blinded_envelope = BlindedExecutionPayloadEnvelope(
        payload_root=hash_tree_root(builder_bid.header),
        execution_requests_root=hash_tree_root(builder_bid.execution_requests),
        builder_index=BUILDER_INDEX_SELF_BUILD,
        beacon_block_root=hash_tree_root(block),
        slot=block.slot,
        blob_kzg_commitments_root=hash_tree_root(builder_bid.blob_kzg_commitments),
    )

    process_blinded_execution_payload_envelope(
        state, builder_bid.header, builder_bid.requests, blinded_envelope
    )

    blinded_envelope.state_root = state.hash_tree_root()

    domain = compute_domain(DOMAIN_BEACON_PROPOSER)
    signing_root = compute_signing_root(blinded_envelope, domain)
    signature = bls.Sign(privkey, signing_root)

    return SignedBlindedExecutionPayloadEnvelope(
        message=blinded_envelope,
        signature=signature,
    )
```

The BeaconState passed to `construct_blinded_envelope` is the resulting state
after running `process_blinded_execution_payload`.

[can-builder-cover-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#can_builder_cover_bid
[get-builder-bid-api]: ./../../apis/builder/builder_bid.yaml
[get-execution-payload-bid-api]: ./../../apis/builder/execution_payload_bid.yaml
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[gloas-validator-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal
[is-active-builder]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#is_active_builder
[signed-builder-bid]: ./unstaked_builder.md#signedbuilderBid
[signed-execution-payload-bid]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadbid
[signed-execution-payload-envelope]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#signedexecutionpayloadenvelope
[submit-block-and-envelope-api]: ./../../apis/builder/block_and_envelope.yaml
[submit-signed-beacon-block]: ./../../apis/builder/beacon_block.yaml
[validator-registration-v2]: ./builder.md#validatorregistrationv2
[verify-execution-payload-bid-signature]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/beacon-chain.md#verify_execution_payload_bid_signature
