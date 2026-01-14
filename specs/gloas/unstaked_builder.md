<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Gloas - Unstaked Builder Specification](#gloas---unstaked-builder-specification)
  - [Introduction](#introduction)
  - [Flow Overview](#flow-overview)
  - [Constants](#constants)
  - [Containers](#containers)
    - [Modified Containers](#modified-containers)
      - [`BuilderBid`](#builderbid)
      - [`SignedBuilderBid`](#signedbuilderbid)
    - [New Containers](#new-containers)
      - [`BlindedExecutionPayloadEnvelope`](#blindedexecutionpayloadenvelope)
      - [`SignedBlindedExecutionPayloadEnvelope`](#signedblindedexecutionpayloadenvelope)
      - [`BlockAndBlindedEnvelope`](#blockandblindedenvelope)
  - [Builder Behaviour](#builder-behaviour)
    - [Constructing a `SignedBuilderBid`](#constructing-a-signedbuilderbid)
    - [Processing `submitBlockAndEnvelope`](#processing-submitblockandenvelope)
    - [`verify_blinded_envelope_signature`](#verify_blinded_envelope_signature)
    - [`process_block_and_envelope`](#process_block_and_envelope)
  - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Unstaked Builder Specification

## Introduction

This document specifies the behaviour for unstaked builders interacting with
validators through the Builder-API in Gloas. Unlike staked builders who have
collateral on the beacon chain, unstaked builders operate through a relay-like
mechanism where they provide full block contents to validators.

The key difference from the staked builder flow is that unstaked builders use
`BUILDER_INDEX_SELF_BUILD` as their builder index in the
`SignedExecutionPayloadBid`, indicating that the proposer is effectively
self-building with the unstaked builder's block contents.

## Flow Overview

The unstaked builder interaction follows these steps:

1. **Validator queries bid**: The validator calls the
   [`getBuilderBid`][get-builder-bid-api] API to get a `SignedBuilderBid`
   containing the execution payload header, blob KZG commitments, execution
   requests, and a `SignedExecutionPayloadBid`.

2. **Validator constructs block**: Upon receiving the bid, the validator:

   - Assembles a `SignedBeaconBlock` with the `ExecutionPayloadBid` from the
     builder
   - Constructs a `SignedBlindedExecutionPayloadEnvelope` using the
     `beacon_block_root` of the `SignedBeaconBlock`

3. **Validator submits to builder**: The validator returns both the
   `SignedBlindedExecutionPayloadEnvelope` and `SignedBeaconBlock` to the
   builder via the [`submitBlockAndEnvelope`][submit-block-and-envelope-api]
   API.

4. **Builder broadcasts envelope**: The builder constructs the full
   `SignedExecutionPayloadEnvelope` (unblinding the blinded version) and
   broadcasts it to the PTC committee via the `execution_payload_envelope`
   gossip topic.

## Constants

| Name | Value | | ----------------------------------------- |
------------------ | | `BUILDER_INDEX_SELF_BUILD` | `2**64 - 1` |

## Containers

### Modified Containers

#### `BuilderBid`

`SignedBuilderBid` is indirectly updated through `BuilderBid`. The `value` and
`pubkey` fields have been removed since they are absorbed by the
`SignedExecutionPayloadBid`.

*Note*: The `builder_index` in the `SignedExecutionPayloadBid` MUST be set to
`BUILDER_INDEX_SELF_BUILD` for unstaked builders.

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests
    bid: SignedExecutionPayloadBid  # [New in Gloas]
```

#### `SignedBuilderBid`

```python
class SignedBuilderBid(Container):
    message: BuilderBid
    signature: BLSSignature
```

### New Containers

#### `BlindedExecutionPayloadEnvelope`

The `BlindedExecutionPayloadEnvelope` contains the roots of the execution
payload components rather than the full data. This allows the validator to
commit to the envelope without having access to the full execution payload.

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

#### `SignedBlindedExecutionPayloadEnvelope`

```python
class SignedBlindedExecutionPayloadEnvelope(Container):
    message: BlindedExecutionPayloadEnvelope
    signature: BLSSignature
```

#### `BlockAndBlindedEnvelope`

Container for submitting both the signed beacon block and blinded envelope
together.

```python
class BlockAndBlindedEnvelope(Container):
    signed_beacon_block: SignedBeaconBlock
    signed_blinded_envelope: SignedBlindedExecutionPayloadEnvelope
```

## Builder Behaviour

### Constructing a `SignedBuilderBid`

When a builder receives a request for a bid via the
[`getBuilderBid`][get-builder-bid-api] API, it MUST construct a
`SignedBuilderBid` with the following:

1. **header**: The `ExecutionPayloadHeader` for the block being built
2. **blob_kzg_commitments**: The KZG commitments for any blobs attached to the
   execution payload
3. **execution_requests**: The execution layer requests (deposits, withdrawals,
   etc.)
4. **bid**: A `SignedExecutionPayloadBid` where:
   - `builder_index` MUST be set to `BUILDER_INDEX_SELF_BUILD`
   - Other fields follow the [Gloas consensus specs][gloas-builder-specs]

The builder signs the `BuilderBid` message using its BLS private key.

### Processing `submitBlockAndEnvelope`

When a builder receives a `BlockAndBlindedEnvelope` via the
[`submitBlockAndEnvelope`][submit-block-and-envelope-api] API, it MUST:

1. **Validate the signed beacon block**: Verify the block signature and ensure
   the `ExecutionPayloadBid` in the block body matches the bid previously
   provided

2. **Validate the blinded envelope**: Verify that:

   - The `beacon_block_root` matches
     `hash_tree_root(signed_beacon_block.message)`
   - The `payload_root` matches the execution payload the builder constructed
   - The `execution_requests_root` matches the execution requests
   - The `blob_kzg_commitments_root` matches the commitments
   - The signature is valid from the proposer

3. **Construct the full envelope**: Create a `SignedExecutionPayloadEnvelope`
   by:

   - Unblinding the payload root with the actual execution payload
   - Including the full execution requests and blob commitments
   - Copying the `beacon_block_root`, `slot`, `builder_index`, and `state_root`
   - Signing with the builder's key

4. **Broadcast**: Broadcast the `SignedExecutionPayloadEnvelope` to the PTC
   committee via the `execution_payload_envelope` gossip topic

### `verify_blinded_envelope_signature`

*Note*: `compute_domain` and `compute_signing_root` are defined in the
[Gloas consensus specs][gloas-consensus-specs].

```python
def verify_blinded_envelope_signature(
    state: BeaconState,
    signed_envelope: SignedBlindedExecutionPayloadEnvelope,
    proposer_index: ValidatorIndex,
) -> bool:
    validator = state.validators[proposer_index]
    pubkey = validator.pubkey
    domain = compute_domain(DOMAIN_BEACON_PROPOSER)
    signing_root = compute_signing_root(signed_envelope.message, domain)
    return bls.Verify(pubkey, signing_root, signed_envelope.signature)
```

### `process_block_and_envelope`

```python
def process_block_and_envelope(
    state: BeaconState,
    builder_bid: BuilderBid,
    block_and_envelope: BlockAndBlindedEnvelope,
    execution_payload: ExecutionPayload,
    execution_requests: ExecutionRequests,
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
) -> SignedExecutionPayloadEnvelope:
    signed_block = block_and_envelope.signed_beacon_block
    signed_blinded_envelope = block_and_envelope.signed_blinded_envelope
    blinded_envelope = signed_blinded_envelope.message

    block = signed_block.message
    proposer_index = block.proposer_index

    # Verify beacon block root matches
    beacon_block_root = hash_tree_root(block)
    assert blinded_envelope.beacon_block_root == beacon_block_root

    # Verify the bid in the block matches our bid
    assert block.body.signed_execution_payload_bid == builder_bid.bid

    # Verify payload root matches
    assert blinded_envelope.payload_root == hash_tree_root(execution_payload)

    # Verify execution requests root matches
    assert blinded_envelope.execution_requests_root == hash_tree_root(
        execution_requests
    )

    # Verify blob commitments root matches
    assert blinded_envelope.blob_kzg_commitments_root == hash_tree_root(
        blob_kzg_commitments
    )

    # Verify slot matches
    assert blinded_envelope.slot == block.slot

    # Verify builder index is self-build
    assert blinded_envelope.builder_index == BUILDER_INDEX_SELF_BUILD

    # Verify blinded envelope signature
    assert verify_blinded_envelope_signature(
        state, signed_blinded_envelope, proposer_index
    )

    # Construct the full execution payload envelope
    envelope = ExecutionPayloadEnvelope(
        payload=execution_payload,
        execution_requests=execution_requests,
        builder_index=BUILDER_INDEX_SELF_BUILD,
        beacon_block_root=beacon_block_root,
        blob_kzg_commitments=blob_kzg_commitments,
        state_root=blinded_envelope.state_root,
    )

    # Sign and return
    return sign_execution_payload_envelope(envelope)
```

## Constructing a `SignedExecutionPayloadEnvelope`

After receiving and validating the `BlockAndBlindedEnvelope`, the builder
constructs a `SignedExecutionPayloadEnvelope` by unblinding the
`BlindedExecutionPayloadEnvelope` with the actual execution payload data.

The specification for constructing a `SignedExecutionPayloadEnvelope` is
documented in the [Gloas consensus specs][gloas-builder-specs].

The builder MUST broadcast the `SignedExecutionPayloadEnvelope` to the PTC
committee via the `execution_payload_envelope` gossip topic.

[get-builder-bid-api]: ./../../apis/builder/builder_bid.yaml
[gloas-builder-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md
[gloas-consensus-specs]: https://github.com/ethereum/consensus-specs/blob/master/specs/gloas
[submit-block-and-envelope-api]: ./../../apis/builder/block_and_envelope.yaml
