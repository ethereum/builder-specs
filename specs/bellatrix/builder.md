# Bellatrix -- Builder Specification

## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Constants](#constants)
  - [Domain types](#domain-types)
- [Containers](#containers)
  - [Independently Versioned](#independently-versioned)
    - [`ValidatorRegistrationV1`](#validatorregistrationv1)
    - [`SignedValidatorRegistrationV1`](#signedvalidatorregistrationv1)
  - [Fork Versioned](#fork-versioned)
    - [Bellatrix](#bellatrix)
      - [`BuilderBid`](#builderbid)
      - [`SignedBuilderBid`](#signedbuilderbid)
      - [`BlindedBeaconBlockBody`](#blindedbeaconblockbody)
      - [`BlindedBeaconBlock`](#blindedbeaconblock)
      - [`SignedBlindedBeaconBlock`](#signedblindedbeaconblock)
  - [Signing](#signing)
- [Endpoints](#endpoints)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Constants

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_APPLICATION_BUILDER` | `DomainType('0x00000001')` |

## Containers

Consider the following definitions supplementary to the definitions in
[`consensus-specs`][consensus-specs]. For information on how containers are
signed, see [Signing](#signing).

### Independently Versioned

Some objects can be updated independently of the `consensus-specs`, because
they originate solely from this specification. The objects are postfixed with
`VX` to denote their revision.

#### `ValidatorRegistrationV1`

```python
class ValidatorRegistrationV1(Container):
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    timestamp: uint64
    pubkey: BLSPubkey
```

#### `SignedValidatorRegistrationV1`

```python
class SignedValidatorRegistrationV1(Container):
    message: ValidatorRegistrationV1
    signature: BLSSignature
```

### Fork Versioned

Other objects are derivatives of `consensus-specs` types and depend on the
latest canonical fork. These objects are namespaced by their fork (e.g.
Bellatrix).

#### Bellatrix

##### `BuilderBid`

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader
    value: uint256
    pubkey: BLSPubkey
```

##### `SignedBuilderBid`

```python
class SignedBuilderBid(Container):
    message: BuilderBid
    signature: BLSSignature
```

##### `BlindedBeaconBlockBody`

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

##### `BlindedBeaconBlock`

```python
class BlindedBeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BlindedBeaconBlockBody
```

##### `SignedBlindedBeaconBlock`

```python
class SignedBlindedBeaconBlock(Container):
    message: BlindedBeaconBlock
    signature: BLSSignature
```

### Signing

All signature operations should follow the [standard BLS operations][bls]
interface defined in `consensus-specs`.

To assist in signing, we use a function from the [consensus specs][consensus-specs]: 
[`compute_domain`][compute-domain]

There are two types of data to sign over in the Builder API:
* In-protocol messages, e.g. [`BlindedBeaconBlock`](#blindedbeaconblock), which
  should compute the signing root using [`compute_signing_root`][compute-root]
  and use the domain specified for beacon block proposals.
* Builder API messages, e.g. validator registration and signed builder bid, which should compute the
  signing root using [`compute_signing_root`][compute-root] with domain given by
  `compute_domain(DOMAIN_APPLICATION_BUILDER, fork_version=None, genesis_validators_root=None)`.
As `compute_signing_root` takes `SSZObject` as input, client software should
convert in-protocol messages to their SSZ representation to compute the signing
root and Builder API messages to the SSZ representations defined
[above](#containers).

## Endpoints

Builder API endpoints are defined in `builder-oapi.yaml` in the root of the
repository. A rendered version can be viewed at
https://ethereum.github.io/builder-specs/.


[consensus-specs]: https://github.com/ethereum/consensus-specs
[bls]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#bls-signatures
[compute-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_signing_root
[compute-domain]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_domain
