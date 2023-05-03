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

### Time parameters

| Name | Value | Unit | Duration |
| - | - | - | - |
| `MAX_REGISTRATION_LOOKAHEAD` | `uint64(10)` | seconds | 10 seconds |

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

## Validator registration processing

To assist in registration processing, we use a function from the [consensus specs][consensus-specs]: [`is_active_validator`][is-active-validator].

### `is_pending_validator`

```python
def is_pending_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is pending in ``epoch``.
    """
    return validator.activation_epoch > epoch
```

### `is_eligible_for_registration`

```python
def is_eligible_for_registration(state: BeaconState, validator: Validator) -> bool:
    """
    Check if ``validator`` is active or pending.
    """
    epoch = get_current_epoch(state)
    return is_active_validator(validator, epoch) or is_pending_validator(validator, epoch)
```

### `verify_registration_signature`

```python
def verify_registration_signature(state: BeaconState, signed_registration: SignedValidatorRegistrationV1):
    pubkey = signed_registration.message.pubkey
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER, fork_version=None, genesis_validators_root=None)
    signing_root = compute_signing_root(signed_registration.message, domain)
    return bls.Verify(pubkey, signing_root, signed_registration.signature)
```

### `process_registration`

```python
def process_registration(state: BeaconState,
                         registration: SignedValidatorRegistrationV1,
                         registrations: Dict[BLSPubkey, ValidatorRegistrationV1]):
    signature = registration.signature
    registration = registration.message

    # Verify BLS public key corresponds to a registered validator
    validator_pubkeys = [v.pubkey for v in state.validators]
    assert pubkey in validator_pubkeys

    index = ValidatorIndex(validator_pubkeys.index(pubkey))
    validator = state.validators[index]

    # Verify validator registration elibility
    assert is_eligible_for_registration(state, validator)

    # If there exists a previous registration, then verify timestamp
    if registration.pubkey in registrations:
        prev_registration = registrations[registration.pubkey]
        assert registration.timestamp >= prev_registration.timestamp
        assert registration.timestamp <= (compute_timestamp_at_slot(state, state.slot) + MAX_REGISTRATION_LOOKAHEAD)

    # Verify registration signature
    assert verify_registration_signature(state, registration)
```

## Building

Upon request, a builder is expected to build execution payloads for registered validators.
The builder responds with a `SignedBuilderBid` that commits to the header of an execution payload.
The builder only reveals the full execution payload once the validator accepts the bid.
The validator accepts a bid and commits to a specific `ExecutionPayload` with a `SignedBlindedBeaconBlock`.

### Bidding

To assist in bidding, we use the following functions from the [consensus specs][consensus-specs]:

* [`get_beacon_proposer_index`][get-beacon-proposer-index]
* [`hash_tree_root`][hash-tree-root]

Validators submit execution payload header requests for a specific `slot`, `parent_hash`, and `pubkey`.

The builder validates the request according to `is_eligible_for_bid(state, registrations, slot, parent_hash, pubkey)` where:

* `registrations` is the registry of validators [successfully registered](#process-registration) with the builder

```python
def is_valid_parent_hash(state: BeaconState, parent_hash: Hash32) -> bool:
    """
    Check if ``parent_hash`` is in ``state``.
    """
    # TODO
```

```python
def is_eligible_for_bid(state: BeaconState,
                        registrations: Dict[BLSPubkey, ValidatorRegistrationV1],
                        slot: Slot,
                        parent_hash: Hash32,
                        pubkey: BLSPubkey) -> bool:
    # Verify slot
    if slot != state.slot:
        return False

    # Verify BLS public key corresponds to a registered validator
    if pubkey not in registrations:
        return False

    # Verify BLS public key corresponds to the proposer for the slot
    proposer_index = get_beacon_proposer_index(state)
    if pubkey != state.validators[proposer_index].pubkey:
        return False

    # Verify parent hash
    return is_valid_parent_hash(state, parent_hash)
```

#### Constructing the `ExecutionPayloadHeader`

Suppose the builder receives an execution payload header request for `slot`, `parent_hash`, and `pubkey`.
The builder MUST return the header of the valid execution payload that is able to pay the `fee_recipient` for the registered `pubkey` the most.
If possible under the rules of consensus, the builder MUST return an execution payload header whose `gas_limit` is equal to the `gas_limit` of the latest registration for `pubkey`.
Otherwise, the builder MUST return an execution payload header with `gas_limit` as close as possible to the desired value under the rules of consensus.

#### Constructing the `BuilderBid`

```python
def get_bid(execution_payload: ExecutionPayload, value: uint256, pubkey: BLSPubkey) -> BuilderBid:
    header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
    )
    return BuilderBid(header=header, value=value, pubkey=pubkey)
```

#### Packaging into a `SignedBuilderBid`

The builder packages `bid` into a `SignedBuilderBid`, denoted `signed_bid`, with `signed_bid=SignedBuilderBid(bid=bid, signature=signature)` where `signature` is obtained from:

```python
def get_bid_signature(state: BeaconState, bid: BuilderBid, privkey: int) -> BLSSignature:
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER, fork_version=None, genesis_validators_root=None)
    signing_root = compute_signing_root(bid, domain)
    return bls.Sign(privkey, signing_root)
```

### Revealing the `ExecutionPayload`

#### Blinded block processing

To assist in blinded block processing, we use the following functions from the [consensus specs][consensus-specs]:

* [`compute_epoch_at_slot`][compute-epoch-at-slot]
* [`get_domain`][get-domain]

##### `verify_blinded_block_signature`

```python
def verify_blinded_block_signature(state: BeaconState, signed_block: SignedBlindedBeaconBlock):
    proposer = state.validators[signed_block.message.proposer_index]
    epoch = compute_epoch_at_slot(signed_block.message.slot)
    signing_root = compute_signing_root(signed_block.message, get_domain(state, DOMAIN_BEACON_PROPOSER, epoch))
    return bls.Verify(proposer.pubkey, signing_root, signed_block.signature)
```

##### `process_blinded_beacon_block`

```python
def process_blinded_beacon_block(state: BeaconState,
                                 block: SignedBlindedBeaconBlock,
                                 bids: Dict[Slot, Set[ExecutionPayloadHeader]],
                                 blocks: Dict[Slot, BlindedBeaconBlock]):
    block = block.message

    # Verify a previous, distinct block has not been submitted for the same slot
    assert block.slot not in blocks or blocks[block.slot] == block

    # Verify the execution payload header corresponds to a previous bid
    assert block.slot in bids
    assert block.body.execution_payload_header in bids[slot]

    # Verify block signature
    assert verify_blinded_block_signature(state, block)
```

## Endpoints

Builder API endpoints are defined in `builder-oapi.yaml` in the root of the
repository. A rendered version can be viewed at
https://ethereum.github.io/builder-specs/.

[consensus-specs]: https://github.com/ethereum/consensus-specs
[bls]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#bls-signatures
[compute-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_signing_root
[compute-domain]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_domain
[is-active-validator]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#is_active_validator
[hash-tree-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#hash_tree_root
[get-domain]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#get_domain
[compute-epoch-at-slot]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_epoch_at_slot
[get-beacon-proposer-index]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#get_beacon_proposer_index
