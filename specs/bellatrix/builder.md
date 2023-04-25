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

## Registration processing

### `process_registration`

```python
def process_registration(state: BeaconState,
                         registration: SignedValidatorRegistrationV1,
                         latest_registrations: Dict[ValidatorIndex, ValidatorRegistrationV1]):
    signature = registration.signature
    registration = registration.message

    # Verify BLS public key corresponds to a registered validator
    validator = get_validator_with_pubkey(state, registration.pubkey)
    assert validator is not None

    # Verify validator registration elibility
    index, validator = validator
    assert is_eligible_for_registration(state, validator)

    # Verify registration signature
    assert verify_registration_signature(state, registration)

    # If there exists a previous registration, then verify timestamp
    # TODO: define `MAX_REGISTRATION_LOOKAHEAD`
    prev_registration = latest_registrations[index]
    if prev_registration is not None:
        assert registration.timestamp > prev_registration.timestamp
        assert registration.timestamp < (compute_timestamp_at_slot(state, state.slot) + MAX_REGISTRATION_LOOKAHEAD)

    # Verify gas limit
    # TODO: define `MAX_GAS_LIMIT` (?)
    assert registration.gas_limit > 0 and registration.gas_limit < MAX_GAS_LIMIT

    # Cache registration
    latest_registrations[index] = registration
```

### `get_validator_with_pubkey`

```python
def get_validator_with_pubkey(state: BeaconState, pubkey: BLSPubkey) -> Optional[Tuple[ValidatorIndex, Validator]]:
    """
    Look up validator for ``pubkey``
    """

    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        return None

    index = ValidatorIndex(validator_pubkeys.index(pubkey))
    validator = state.validators[index]
    return index, validator

```

### `is_eligible_for_registration`

```python
def is_eligible_for_registration(state: BeaconState, validator: Validator) -> bool:
    """
    Check if ``validator`` is not slashed and is either active or pending
    """

    if validator.slashed:
        return False

    epoch = get_current_epoch(state)
    return is_active_validator(validator, epoch) or is_eligible_for_activation(state, validator) or is_eligible_for_activation_queue(validator)
```

### `verify_registration_signature`

```python
def verify_registration_signature(state: BeaconState, signed_registration: SignedValidatorRegistrationV1):
    pubkey = signed_registration.message.pubkey
    signing_root = compute_signing_root(signed_registration.message, get_domain(state, DOMAIN_APPLICATION_BUILDER))
    return bls.Verify(pubkey, signing_root, signed_registration.signature)
```

## Constructing the `ExecutionPayloadHeader`

Given the `slot`, `parent_hash`, and `pubkey`, the builder MUST return the header of the valid execution payload that is able to pay the `fee_recipient` for the registered `pubkey` the most.
If the builder has not processed a previous validator registration for `pubkey`, then the builder MUST return (the appropriate error code).
If the validator registered for `pubkey` is not the proposer for `slot`, then the builder MUST return (the appropriate error code).
If `parent_hash` does not correspond to the head block hash according to the fork choice of the builder, then the builder MUST return (the appropriate error code).
If possible under the rules of consensus, the builder MUST return an execution payload header whose `gas_limit` is equal to the `gas_limit` of the latest registration for `pubkey`.
Otherwise, the builder MUST return an execution payload header with `gas_limit` as close as possible to the desired value under the rules of consensus.

## Blinded block processing

### `process_blinded_beacon_block`

```python
def process_blinded_beacon_block(state: BeaconState,
                                 block: SignedBlindedBeaconBlock,
                                 bids: Dict[Slot, Set[BuilderBid],
                                 blocks: Dict[Slot, SignedBlindedBeaconBlock]):
    # Verify block signature
    assert verify_blinded_block_signature(state, block)

    # TODO: Verify slot

    block = block.message

    # Verify a previous block has not been submitted for the same slot
    assert blocks[block.slot] is None

    # Verify the execution payload header corresponds to a previous bid
    bid_headers = [b.header for b in bids[block.slot]]
    assert block.body.execution_payload_header in bid_headers

    # TODO: Verify the remainder of the block

    # Cache the block
    blocks[block.slot] = block
```

### `verify_blinded_block_signature`

```python
def verify_blinded_block_signature(state: BeaconState, signed_block: SignedBlindedBeaconBlock):
    proposer = state.validators[signed_block.message.proposer_index]
    signing_root = compute_signing_root(signed_block.message, get_domain(state, DOMAIN_BEACON_PROPOSER))
    return bls.Verify(proposer.pubkey, signing_root, signed_registration.signature)
```

## Endpoints

Builder API endpoints are defined in `builder-oapi.yaml` in the root of the
repository. A rendered version can be viewed at
https://ethereum.github.io/builder-specs/.


[consensus-specs]: https://github.com/ethereum/consensus-specs
[bls]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#bls-signatures
[compute-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_signing_root
[compute-domain]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_domain
