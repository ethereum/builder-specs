# Builder Specification

This document specifies the behaviour of external block builders not already
covered in the corresponding API schema.

## Structures

### SSZ Objects

Consider the following definitions supplementary to the definitions in
[`consensus-specs`][consensus-specs].

##### `ValidatorRegistrationV1`

```python
class ValidatorRegistrationV1(Container):
    feeRecipient: Bytes20
    gasLimit: uint64
    timestamp: uint64
    pubkey: BLSPubkey
```

##### `BuilderBidV1`

```python
class BuilderBidV1(Container):
    header: ExecutionPayloadHeader
    value: uint256
    pubkey: BLSPubkey
```

###### `BlindedBeaconBlock`

```python
class BlindedBeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BlindedBeaconBlockBody
```

###### `BlindedBeaconBlockBody`

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
    execution_payload_header: ExecutionPayloadHeader
```

## Routines

### Signing

All signature operations should follow the [standard BLS operations][bls]
interface defined in `consensus-specs`.

There are two types of data to sign over in the Builder API:
* In-protocol messages, e.g. [`BlindedBeaconBlock`](#blindedbeaconblock), which
  should compute the signing root using [`compute_signing_root`][compute-root]
  and use the domain specified for beacon block proposals.
* Builder API messages, e.g. validator registration, which should compute the
  signing root using [`compute_signing_root`][compute-root] and the domain
  `DomainType('0xXXXXXXXX')` (TODO: get a proper domain).

As `compute_signing_root` takes `SSZObject` as input, client software should
convert in-protocol messages to their SSZ representation to compute the signing
root and Builder API messages to the SSZ representations defined
[above](#sszobjects).

[consensus-specs]: https://github.com/ethereum/consensus-specs
[bls]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#bls-signatures
[compute-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_signing_root
