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
- [Building](#building)
  - [Block scoring](#block-scoring)
- [Relaying](#relaying)
  - [Block scoring](#block-scoring-1)
  - [Bidding](#bidding)
  - [Revealing the `ExecutionPayload`](#revealing-the-executionpayload)
    - [Blinded block processing](#blinded-block-processing)

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

Builders provide bids as they have in prior forks, with a notable restriction to block scoring.

### Block scoring

Builders **MUST** not include the `amount`s from the consensus block's withdrawals when computing the `value` for their `BuilderBid`.

See [the section below on relay verification](#block-scoring-1) for the logic a builder's bid must satisfy.

## Relaying

Relays have a few additional duties to support the features in this upgrade.

### Block scoring

Relays **MUST** ensure the `value` in the `BuilderBid` corresponds to the payment delivered by the builder to the proposer, excluding any withdrawals.

Consider the following validation logic following definitions in the `consensus-specs`:

```python
def verify_bid_value(execution_payload: ExecutionPayload, fee_recipient: ExecutionAddress, bid_value: uint256, balance_difference: uint256):
    excluded_amount = sum([w.amount for w in execution_payload.withdrawals if w.address == fee_recipient])
    proposer_payment = balance_difference - excluded_amount
    assert proposer_payment == bid_value
```

`verify_bid_value` should execute completely, noting that assertion failures are errors.
The `execution_payload`, `fee_recipient`, and `bid_value` are all provided by the builder in their payload submission.
The `balance_difference` is computed by the relay during simulation of the `execution_payload` where
`balance_difference = post_state_balance - pre_state_balance`.
`pre_state_balance` is the ether amount at the `fee_recipient`’s address in the execution state before applying
the `execution_payload` and the `post_state_balance` is the same data after applying the `execution_payload`.

Any block submissions where `verify_bid_value` fails should be considered invalid and **MUST** not be served to proposers requesting bids.

### Bidding

After a relay has verified the execution payload (including any blobs) is correctly constructed, the relay **MUST** additionally return any `KZGCommitments` for those blobs
in the `SignedBuilderBid`.

### Revealing the `ExecutionPayload`

#### Blinded block processing

Relays verify signed blinded beacon blocks as before, with the additional requirement
that they must construct `BlobSidecar` objects with the KZG commitment inclusion
proof before gossiping the blobs alongside the unblinded block.

* NOTE: the [standard `beacon-apis` implemented by consensus clients](https://github.com/ethereum/beacon-APIs) will handle the construction of the `BlobSidecar`
object following the block broadcast endpoints defined there.
