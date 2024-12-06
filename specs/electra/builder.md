# Electra -- Builder Specification

## Introduction

This is the modification of the builder specification accompanying the Electra upgrade.

The behavior defined by the specification is consistent with previous forks except for the changes to the types given below.

## Containers

### Extended containers

#### `BuilderBid`

Note: `SignedBuilderBid` is updated indirectly.

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: OpaqueExecutionRequests # [New in Electra]
    value: uint256
    pubkey: BLSPubkey
```

#### `BlindedBeaconBlockBody`

Note: `BlindedBeaconBlock` and `SignedBlindedBeaconBlock` types are updated indirectly.

```python
class BlindedBeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA] # [Modified in Electra:EIP7549]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA] # [Modified in Electra:EIP7549]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: ExecutionPayloadHeader
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: OpaqueExecutionRequests # [New in Electra]
```

### New Containers

### `OpaqueExecutionRequests`

```python
class OpaqueExecutionRequests(List[Bitvector]):
    pass
```

`OpaqueExecutionRequests` is simply a "type alias" for a `List[Bitvector]`, this type follows the encoding of execution
requests as explained in EIP-7865.  Specifically for Electra, the list should contain three elements, one for
each of the type-prefixed and byte-encoded `Deposit`, `Withdrawal` and `Consolidation` request lists.

Note that while each `Bitvector` appears as an arbitrary-length byte sequence, technically each entry is bound 
by the encoded length of each request type and the maximum amount of each request type allowed in a block.

## Building

Builders provide bids as they have in prior forks, with the addition of execution requests.

### Execution Requests

The actual payloads for each request type are generated as side-effects of block-building, see EIP-6110 for 
`Deposit`, EIP-7002 for `Withdrawal` and EIP-7251 for `Consolidation` requests.  

[execution-payload-and-blobs-bundle-deneb]: ../deneb/builder.md#executionpayloadandblobsbundle
