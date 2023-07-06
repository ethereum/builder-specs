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

Validators must submit registrations before they can work with builders.

To assist in registration processing, we use the following functions from the [consensus specs][consensus-specs]:

* [`get_current_epoch`][get-current-epoch]
* [`is_active_validator`][is-active-validator]

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
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER)
    signing_root = compute_signing_root(signed_registration.message, domain)
    return bls.Verify(pubkey, signing_root, signed_registration.signature)
```

### `process_registration`

A `registration` is considered valid if the following function completes without raising any assertions:

```python
def process_registration(state: BeaconState,
                         registration: SignedValidatorRegistrationV1,
                         registrations: Dict[BLSPubkey, ValidatorRegistrationV1],
                         current_timestamp: uint64):
    signature = registration.signature
    registration = registration.message

    # Verify BLS public key corresponds to a registered validator
    validator_pubkeys = [v.pubkey for v in state.validators]
    assert pubkey in validator_pubkeys

    index = ValidatorIndex(validator_pubkeys.index(pubkey))
    validator = state.validators[index]

    # Verify validator registration elibility
    assert is_eligible_for_registration(state, validator)

    # Verify timestamp is not too far in the future
    assert registration.timestamp <= current_timestamp + MAX_REGISTRATION_LOOKAHEAD

    # Verify timestamp is not less than the timestamp of the previous registration (if it exists)
    if registration.pubkey in registrations:
        prev_registration = registrations[registration.pubkey]
        assert registration.timestamp >= prev_registration.timestamp

    # Verify registration signature
    assert verify_registration_signature(state, registration)
```

## Building

The builder builds execution payloads for registered validators and submits them to an auction that happens each slot.
When a validator goes to propose, they select the winning `SignedBuilderBid` offered in that slot by constructing a `SignedBlindedBeaconBlock`.
The builder only reveals the full execution payload once they receive a valid `SignedBlindedBeaconBlock`.
The validator accepts a bid and commits to a specific `ExecutionPayload` with a `SignedBlindedBeaconBlock`.

### Bidding

To assist in bidding, we use the following functions from the [consensus specs][consensus-specs]:

* [`get_beacon_proposer_index`][get-beacon-proposer-index]
* [`hash_tree_root`][hash-tree-root]

Execution payloads are built for a specific `slot`, `parent_hash`, and `pubkey` tuple corresponding to a unique beacon block serving as the parent.

The builder validates requests for bids according to `is_eligible_for_bid(state, registrations, slot, parent_hash, pubkey)` where:

* `state` is the builder's consensus state transitioned to `slot`, including the application of any blocks before `slot`.
* `registrations` is the registry of validators [successfully registered](#process-registration) with the builder.

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
    return parent_hash == state.latest_execution_payload_header.block_hash
```

#### Constructing the `ExecutionPayloadHeader`

The builder MUST provide a bid for the valid execution payload that is able to pay the `fee_recipient` in the validator registration for the registered `pubkey` the most.
The builder MUST build an execution payload whose `gas_limit` is equal to the `gas_limit` of the latest registration for `pubkey`, or as close as is possible under the consensus rules.

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
    domain = compute_domain(DOMAIN_APPLICATION_BUILDER)
    signing_root = compute_signing_root(bid, domain)
    return bls.Sign(privkey, signing_root)
```

### Revealing the `ExecutionPayload`

#### Blinded block processing

To assist in blinded block processing, we use the following functions from the [consensus specs][consensus-specs]:

* [`get_beacon_proposer_index`][get-beacon-proposer-index]
* [`get_current_epoch`][get-current-epoch]
* [`compute_epoch_at_slot`][compute-epoch-at-slot]
* [`get_domain`][get-domain]

A proposer selects a bid by constructing a valid `SignedBlindedBeaconBlock`.
The proposer MUST accept at most one bid for a given `slot`.
Otherwise, the builder can produce a [`ProposerSlashing`][proposer-slashing].

The builder must ensure the `SignedBlindedBeaconBlock` is valid according to the rules of consensus and also that the signature is correct for the expected proposer using `verify_blinded_block_signature`:

##### `verify_blinded_block_signature`

```python
def verify_blinded_block_signature(state: BeaconState, signed_block: SignedBlindedBeaconBlock):
    proposer = state.validators[get_beacon_proposer_index(state)]
    epoch = get_current_epoch(state)
    signing_root = compute_signing_root(signed_block.message, get_domain(state, DOMAIN_BEACON_PROPOSER, epoch))
    return bls.Verify(proposer.pubkey, signing_root, signed_block.signature)
```

## Endpoints

Builder API endpoints are defined in `builder-oapi.yaml` in the root of the
repository. A rendered version can be viewed at
https://ethereum.github.io/builder-specs/.

[consensus-specs]: https://github.com/ethereum/consensus-specs
[bls]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#bls-signatures
[compute-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_signing_root
[compute-domain]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_domain
[get-current-epoch]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#get_current_epoch
[is-active-validator]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#is_active_validator
[hash-tree-root]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#hash_tree_root
[get-domain]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#get_domain
[compute-epoch-at-slot]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#compute_epoch_at_slot
[get-beacon-proposer-index]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#get_beacon_proposer_index
[proposer-slashing]: https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/beacon-chain.md#proposerslashing
