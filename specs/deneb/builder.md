# Deneb -- Builder Specification

## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`BlobsBundle`](#blobsbundle)
    - [`ExecutionPayloadAndBlobsBundle`](#executionpayloadandblobsbundle)
  - [Extended containers](#extended-containers)
    - [`BuilderBid`](#builderbid)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
      - [`BlindedBeaconBlockBody`](#blindedbeaconblockbody)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This is the modification of the builder specification accompanying the Deneb upgrade.

## Containers

### New containers

#### `BlobsBundle`

```python
class BlobsBundle(Container):
  commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
  proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
  blobs: List[Blob, MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

#### `ExecutionPayloadAndBlobsBundle`

```python
class ExecutionPayloadAndBlobsBundle(Container):
    execution_payload: ExecutionPayload
    blobs_bundle: BlobsBundle
```

### Extended containers

#### `BuilderBid`

Note: `SignedBuilderBid` is updated indirectly.

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader # [Modified in Deneb]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]  # [New in Deneb]
    value: uint256
    pubkey: BLSPubkey
```

#### `ExecutionPayloadHeader`

See [`ExecutionPayloadHeader`](https://github.com/ethereum/consensus-specs/blob/dev/specs/deneb/beacon-chain.md#executionpayloadheader) in Deneb consensus specs.

##### `BlindedBeaconBlockBody`

Note: `BlindedBeaconBlock` and `SignedBlindedBeaconBlock` types are updated indirectly.

```python
class BlindedBeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: ExecutionPayloadHeader  # [Modified in Deneb]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]  # [New in Deneb]
```

## Building

Builders provide bids as the have in prior forks.

Relays have a few additional duties.

### Bidding

After a relay has verified the execution payload (including any blobs) is correctly constructed, the relay **MUST** additionally return any `KZGCommitments` for those blobs
in the `SignedBuilderBid`.

### Revealing the `ExecutionPayload`

#### Blinded block processing

Relays verify signed blinded beacon blocks as before, with the additional requirement
that they must construct `SignedBlobSidecar` objects with the KZG commitment inclusion
proof before gossiping the blobs alongside the unblinded block.
