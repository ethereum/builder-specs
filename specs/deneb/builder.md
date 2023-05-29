# Deneb -- Builder Specification

## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`BlindedBlobsBundle`](#blindedblobsbundle)
    - [`BlindedBlobSidecar`](#blindedblobsidecar)
    - [`SignedBlindedBlobSidecar`](#signedblindedblobsidecar)
    - [`SignedBlindedBlockContents`](#signedblindedblockcontents)
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

#### `BlindedBlobsBundle`

```python
class BlindedBlobsBundle(Container):
    commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]
    proofs: List[KZGProof, MAX_BLOBS_PER_BLOCK]
    blob_roots: List[Root, MAX_BLOBS_PER_BLOCK]
```

#### `BlindedBlobSidecar`

```python
class BlindedBlobSidecar(Container):
    block_root: Root
    index: uint64
    slot: uint64
    block_parent_root: Root
    proposer_index: uint64
    blob_root: Root
    kzg_commitment: KZGCommitment
    kzg_proof: KZGProof
```

#### `SignedBlindedBlobSidecar`

```python
class SignedBlindedBlobSidecar(Container):
    message: BlindedBlobSidecar
    signature: BLSSignature
```

#### `SignedBlindedBlockContents`

```python
class SignedBlindedBlockContents(Container):
    signed_blinded_block: SignedBlindedBeaconBlock
    signed_blinded_blob_sidecars: List[SignedBlindedBlobSidecar, MAX_BLOBS_PER_BLOCK]
```

#### `BlobsBundle`

Same as [`BlobsBundle`](https://github.com/ethereum/consensus-specs/blob/dev/specs/deneb/validator.md#blobsbundle) in Deneb consensus specs.

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
    blinded_blobs: BlindedBlobsBundle  # [New in Deneb]
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
