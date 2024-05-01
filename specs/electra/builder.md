# Electra -- Builder Specification

## Introduction

This is the modification of the builder specification accompanying the Electra upgrade.

## Containers

### Extended containers

#### `ExecutionPayloadAndBlobsBundle`

```python
class ExecutionPayloadAndBlobsBundle(Container):
    execution_payload: ExecutionPayload # [Modified in Electra]
    blobs_bundle: BlobsBundle
```

#### `BuilderBid`

Note: `SignedBuilderBid` is updated indirectly.

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader # [Modified in Electra]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    value: uint256
    pubkey: BLSPubkey
```

#### `ExecutionPayloadHeader`

See [`ExecutionPayloadHeader`](https://github.com/ethereum/consensus-specs/blob/dev/specs/electra/beacon-chain.md#executionpayloadheader) in Electra consensus specs.

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
    execution_payload_header: ExecutionPayloadHeader  # [Modified in Electra]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    consolidations: List[SignedConsolidation, MAX_CONSOLIDATIONS]  # [New in Electra]
```
