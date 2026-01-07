<!-- START doctoc generated TOC please keep comment here to allow auto update -->

<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Electra -- Builder Specification](#electra----builder-specification)
  - [Introduction](#introduction)
  - [Containers](#containers)
    - [Extended containers](#extended-containers)
      - [`BuilderBid`](#builderbid)
      - [`BlindedBeaconBlockBody`](#blindedbeaconblockbody)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Electra -- Builder Specification

## Introduction

This is the modification of the builder specification accompanying the Electra
upgrade.

The behavior defined by the specification is consistent with previous forks
except for the changes to the types given below.

## Containers

### Extended containers

#### `BuilderBid`

Note: `SignedBuilderBid` is updated indirectly.

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests  # [New in Electra]
    value: uint256
    pubkey: BLSPubkey
```

#### `BlindedBeaconBlockBody`

Note: `BlindedBeaconBlock` and `SignedBlindedBeaconBlock` types are updated
indirectly.

```python
class BlindedBeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[
        AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA
    ]  # [Modified in Electra:EIP7549]
    attestations: List[
        Attestation, MAX_ATTESTATIONS_ELECTRA
    ]  # [Modified in Electra:EIP7549]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: ExecutionPayloadHeader
    bls_to_execution_changes: List[
        SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES
    ]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests  # [New in Electra]
```
