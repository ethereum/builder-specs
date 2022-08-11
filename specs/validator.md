# Builder -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
- [Validator registration](#validator-registration)
  - [Preparing a registration](#preparing-a-registration)
  - [Signing and submitting a registration](#signing-and-submitting-a-registration)
  - [Registration dissemination](#registration-dissemination)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)
    - [Relation to local block building](#relation-to-local-block-building)
- [How to avoid slashing](#how-to-avoid-slashing)
  - [Proposer slashing](#proposer-slashing)
- [Responsibilites during the Merge transition](#responsibilites-during-the-merge-transition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document explains the way in which a beacon chain validator is expected to use the [Builder spec][builder-spec] to
participate in an external builder network.

At a high-level, there is a registration step validators must perform ahead of any proposal duties so builders know how
to craft blocks for their specific proposal. Having performed the registration, a validator waits until it is their turn
to propose the next block in the chain. The validator then requests an `ExecutionPayload` from the external builder
network to put into their `SignedBeaconBlock` in lieu of one they could build locally.

## Prerequisites

This document assumes knowledge of the terminology, definitions, and other material in the [Builder spec][builder-spec]
and by extension the [Bellatrix consensus specs][bellatrix-specs].

## Constants

| Name | Value | Units |
| - | - | - |
| `EPOCHS_PER_VALIDATOR_REGISTRATION_SUBMISSION` | 1 | epoch(s)|
| `BUILDER_PROPOSAL_DELAY_TOLERANCE` | 1 | second(s) |

## Validator registration

A validator begins interacting with the external builder network by submitting a signed registration to each of the
builders it wants to utilize during block production.

### Preparing a registration

To do this, the validator client assembles a [`ValidatorRegistrationV1`][validator-registration-v1] with the following
information:

* `fee_recipient`: an execution layer address where fees for the validator should go.
* `gas_limit`: the value a validator prefers for the execution block gas limit.
* `timestamp`: a recent timestamp later than any previously constructed `ValidatorRegistrationV1`.
  Builders use this timestamp as a form of anti-DoS and to sequence registrations.
* `pubkey`: the validator's public key. Used to identify the beacon chain validator and verify the wrapping signature.

### Signing and submitting a registration

The validator takes the constructed `ValidatorRegistrationV1` `message` and signs according to the method given in
the [Builder spec][builder-spec] to make a `signature`.

This `signature` is placed along with the `message` into a `SignedValidatorRegistrationV1` and submitted to a connected
beacon node using the [`registerValidator`][register-validator-api] endpoint of the standard validator
[beacon node APIs][beacon-node-apis].

Validators **should** submit valid registrations well ahead of any potential beacon chain proposal duties to ensure
their building preferences are widely available in the external builder network.

### Registration dissemination

Validators are expected to periodically send their own `SignedValidatorRegistrationV1` messages upstream to the external
builder network using the [`registerValidator`][register-validator-with-builder] endpoint of the standard
[APIs defined in the builder spec][builder-spec-apis].

Registrations should be re-submitted frequently enough that any changes to their building preferences can be widely
spread across the builder network in a timely manner.

This specification suggests validators re-submit to builder software every
`EPOCHS_PER_VALIDATOR_REGISTRATION_SUBMISSION` epochs.

## Beacon chain responsibilities

Refer to the [Bellatrix validator specs][bellatrix-validator-specs] for the expected set of duties a validator is
expected to perform, including a pathway for local block building. The external builder network offers a separate block
building pathway that can be used concurrently with this local process.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

To obtain an execution payload, a block proposer building a block on top of a beacon `state` in a given `slot` must take
the following actions:

1. Call upstream builder software to get an `ExecutionPayloadHeader` with the
   required data `slot`, `parent_hash` and `pubkey`, where:
   * `slot` is the proposal's slot
   * `parent_hash` is the value `state.latest_execution_payload_header.block_hash`
   * `pubkey` is the propser's public key
2. Assemble a `BlindedBeaconBlock` according to the process outlined in the [Bellatrix specs][bellatrix-specs] but with
   the `ExecutionPayloadHeader` from the prior step in lieu of the full `ExecutionPayload`.
3. The proposer signs the `BlindedBeaconBlock` and assembles a `SignedBlindedBeaconBlock` which is returned to the
   upstream builder software.
4. The upstream builder software responds with the full `ExecutionPayload`. The proposer can use this payload
   to assemble a `SignedBeaconBlock` following the rest of the proposal process outlined in the
   [Bellatrix specs][bellatrix-specs].

#### Relation to local block building

The external builder network offers a service for proposers that may from time to time fail to produce a timely block.
Honest proposers who elect to use the external builder network **MUST** also build a block locally in the event that the
external builder network fails to provide a `SignedBuilderBid` in time in order to propagate the full
`SignedBeaconBlock` during the proposer's slot. The local build task should begin in parallel to any use of the external
builder network.

Honest proposers using the external builder network will give the builders a duration of
`BUILDER_PROPOSAL_DELAY_TOLERANCE` to provide a `SignedBuilderBid` before the external builder is considered to have hit
the deadline and the external builder flow must be aborted in favor of a local build process.

**WARNING**: Validators must be careful to not get slashed when orchestrating the duplicate building pathways.
  See the [section on slashing](#proposer-slashing) for more information.

## How to avoid slashing

### Proposer slashing

Validators must take care to not publish signatures for two distinct blocks even if there is a failure with the external
builder network. A `ProposerSlashing` can be formed in this event from the competing beacon block headers which results
in getting slashed.

To avoid slashing when using the external builder network, a validator should begin the external build process for an
`ExecutionPayloadHeader` along with the local build process for an `ExecutionPayload` as soon as they know the required
parameters to do so. Regardless of which process completes in time, the validator should cancel the other
process as soon as they have produced a signature for a beacon block, either a `BeaconBlock` **or** a
`BlindedBeaconBlock`. Producing distinct signatures for the validator's proposal slot, for example because the
transactions list of the `BeaconBlockBody` are different, is the slashable offense. This means if a validator publishes
a signature for a `BlindedBeaconBlock` (via a dissemination of a `SignedBlindedBeaconBlock`) then the validator
**MUST** not use the local build process as a fallback, even in the event of some failure with the external builder
network.

## Responsibilites during the Merge transition

Honest validators will not utilize the external builder network during the transition from proof-of-work to
proof-of-stake. This requirement is in place to reduce the overall technical complexity of the Merge.

Concretely, honest validators **MUST** wait until the transition has been finalized before
they can start querying the external builder network. See [EIP-3675](eip-3675) for further details about the transition
process itself.

[builder-spec]: ./builder.md
[builder-spec-apis]: ./builder.md#endpoints
[register-validator-with-builder]: https://ethereum.github.io/builder-specs/#/Builder/registerValidator
[validator-registration-v1]: ./builder.md#validatorregistrationv1
[register-validator-api]: https://ethereum.github.io/beacon-APIs/#/Validator/registerValidator
[beacon-node-apis]: https://ethereum.github.io/beacon-APIs
[bellatrix-specs]: https://github.com/ethereum/consensus-specs/blob/dev/specs/bellatrix
[bellatrix-validator-specs]: https://github.com/ethereum/consensus-specs/blob/dev/specs/bellatrix/validator.md
[eip-3675]: https://eips.ethereum.org/EIPS/eip-3675
