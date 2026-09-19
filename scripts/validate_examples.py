#!/usr/bin/env python3
"""
Validate that JSON and SSZ examples in the builder-specs repository match.

This script deserializes both JSON and SSZ example files and verifies that
they represent the same data. It supports all forks from Bellatrix onwards.

Usage:
    python scripts/validate_examples.py [--verbose] [--fork FORK] [--example EXAMPLE]

Exit codes:
    0 - All examples validated successfully
    1 - One or more examples failed validation
    2 - Script error (e.g., missing dependencies)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

# Check for required dependencies
try:
    from remerkleable.basic import uint8, uint64, uint256
    from remerkleable.byte_arrays import ByteVector, ByteList
    from remerkleable.complex import Container, List, Vector
    from remerkleable.core import View
except ImportError:
    print(
        "Error: Missing required dependency 'remerkleable'.\n"
        "Install it with: pip install remerkleable",
        file=sys.stderr,
    )
    sys.exit(2)


# =============================================================================
# Constants
# =============================================================================

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# SSZ field element sizes
BYTES_PER_LOGS_BLOOM = 256
BYTES_PER_EXTRA_DATA_MAX = 32
MAX_TRANSACTIONS_PER_PAYLOAD = 1048576
MAX_BYTES_PER_TRANSACTION = 1073741824
MAX_WITHDRAWALS_PER_PAYLOAD = 16
MAX_BLOB_COMMITMENTS_PER_BLOCK = 4096
MAX_BLOBS_PER_BLOCK = 4096
MAX_DEPOSIT_REQUESTS_PER_PAYLOAD = 8192
MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD = 16
MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD = 1
BYTES_PER_BLOB = 131072
MAX_CELL_PROOFS_PER_PAYLOAD = 33554432  # 8192 * 4096 for Fulu

# Beacon chain constants
MAX_PROPOSER_SLASHINGS = 16
MAX_ATTESTER_SLASHINGS = 2
MAX_ATTESTER_SLASHINGS_ELECTRA = 1
MAX_ATTESTATIONS = 128
MAX_ATTESTATIONS_ELECTRA = 8
MAX_DEPOSITS = 16
MAX_VOLUNTARY_EXITS = 16
MAX_BLS_TO_EXECUTION_CHANGES = 16
MAX_VALIDATORS_PER_COMMITTEE = 2048
DEPOSIT_CONTRACT_TREE_DEPTH = 32
SYNC_COMMITTEE_SIZE = 512

# Forks
FORKS = ["bellatrix", "capella", "deneb", "electra", "fulu"]


# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger("validate_examples")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.setLevel(level)
    logger.addHandler(handler)


# =============================================================================
# SSZ Type Aliases
# =============================================================================

# Primitive types
Bytes4 = ByteVector[4]
Bytes20 = ByteVector[20]
Bytes32 = ByteVector[32]
Bytes48 = ByteVector[48]
Bytes96 = ByteVector[96]

# Domain-specific aliases
Root = Bytes32
BLSPubkey = Bytes48
BLSSignature = Bytes96
ExecutionAddress = Bytes20
LogsBloom = ByteVector[BYTES_PER_LOGS_BLOOM]
ExtraData = ByteList[BYTES_PER_EXTRA_DATA_MAX]
Transaction = ByteList[MAX_BYTES_PER_TRANSACTION]
KZGCommitment = Bytes48
KZGProof = Bytes48
Blob = ByteVector[BYTES_PER_BLOB]


# =============================================================================
# SSZ Container Definitions - Common Types
# =============================================================================


class ValidatorRegistration(Container):
    """ValidatorRegistration as defined in the Builder API spec."""

    fee_recipient: ExecutionAddress
    gas_limit: uint64
    timestamp: uint64
    pubkey: BLSPubkey


class SignedValidatorRegistration(Container):
    """SignedValidatorRegistration as defined in the Builder API spec."""

    message: ValidatorRegistration
    signature: BLSSignature


# =============================================================================
# SSZ Container Definitions - Beacon Chain Types (Phase0/Altair)
# =============================================================================

# Type alias for bitlists/bitvectors - using ByteList as approximation
# Attestation aggregation_bits is a Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
# SyncCommitteeBits is a Bitvector[SYNC_COMMITTEE_SIZE]
CommitteeBits = ByteList[MAX_VALIDATORS_PER_COMMITTEE // 8 + 1]
SyncCommitteeBits = ByteVector[SYNC_COMMITTEE_SIZE // 8]


class Checkpoint(Container):
    """Checkpoint as defined in the CL Phase0 spec."""

    epoch: uint64
    root: Root


class Eth1Data(Container):
    """Eth1Data as defined in the CL Phase0 spec."""

    deposit_root: Root
    deposit_count: uint64
    block_hash: Bytes32


class BeaconBlockHeader(Container):
    """BeaconBlockHeader as defined in the CL Phase0 spec."""

    slot: uint64
    proposer_index: uint64
    parent_root: Root
    state_root: Root
    body_root: Root


class SignedBeaconBlockHeader(Container):
    """SignedBeaconBlockHeader as defined in the CL Phase0 spec."""

    message: BeaconBlockHeader
    signature: BLSSignature


class ProposerSlashing(Container):
    """ProposerSlashing as defined in the CL Phase0 spec."""

    signed_header_1: SignedBeaconBlockHeader
    signed_header_2: SignedBeaconBlockHeader


class AttestationData(Container):
    """AttestationData as defined in the CL Phase0 spec."""

    slot: uint64
    index: uint64
    beacon_block_root: Root
    source: Checkpoint
    target: Checkpoint


class IndexedAttestation(Container):
    """IndexedAttestation as defined in the CL Phase0 spec."""

    attesting_indices: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    signature: BLSSignature


class AttesterSlashing(Container):
    """AttesterSlashing as defined in the CL Phase0 spec."""

    attestation_1: IndexedAttestation
    attestation_2: IndexedAttestation


class Attestation(Container):
    """Attestation as defined in the CL Phase0 spec."""

    aggregation_bits: CommitteeBits
    data: AttestationData
    signature: BLSSignature


class DepositData(Container):
    """DepositData as defined in the CL Phase0 spec."""

    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: uint64
    signature: BLSSignature


class Deposit(Container):
    """Deposit as defined in the CL Phase0 spec."""

    proof: Vector[Bytes32, DEPOSIT_CONTRACT_TREE_DEPTH + 1]
    data: DepositData


class VoluntaryExit(Container):
    """VoluntaryExit as defined in the CL Phase0 spec."""

    epoch: uint64
    validator_index: uint64


class SignedVoluntaryExit(Container):
    """SignedVoluntaryExit as defined in the CL Phase0 spec."""

    message: VoluntaryExit
    signature: BLSSignature


class SyncAggregate(Container):
    """SyncAggregate as defined in the CL Altair spec."""

    sync_committee_bits: SyncCommitteeBits
    sync_committee_signature: BLSSignature


class SigningData(Container):
    """SigningData as defined in the CL Phase0 spec."""

    object_root: Root
    domain: Bytes32


class BLSToExecutionChange(Container):
    """BLSToExecutionChange as defined in the CL Capella spec."""

    validator_index: uint64
    from_bls_pubkey: BLSPubkey
    to_execution_address: ExecutionAddress


class SignedBLSToExecutionChange(Container):
    """SignedBLSToExecutionChange as defined in the CL Capella spec."""

    message: BLSToExecutionChange
    signature: BLSSignature


# =============================================================================
# SSZ Container Definitions - Electra Attestation Types
# =============================================================================


class ElectraIndexedAttestation(Container):
    """IndexedAttestation as modified in Electra spec."""

    attesting_indices: List[uint64, MAX_VALIDATORS_PER_COMMITTEE * 64]  # MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT
    data: AttestationData
    signature: BLSSignature


class ElectraAttesterSlashing(Container):
    """AttesterSlashing as modified in Electra spec."""

    attestation_1: ElectraIndexedAttestation
    attestation_2: ElectraIndexedAttestation


class ElectraAttestation(Container):
    """Attestation as modified in Electra spec."""

    aggregation_bits: ByteList[MAX_VALIDATORS_PER_COMMITTEE * 64 // 8 + 1]  # Bitlist
    data: AttestationData
    signature: BLSSignature
    committee_bits: ByteVector[8]  # Bitvector[MAX_COMMITTEES_PER_SLOT] = 64 bits = 8 bytes


# =============================================================================
# SSZ Container Definitions - Withdrawal Types
# =============================================================================


class Withdrawal(Container):
    """Withdrawal as defined in the CL Capella spec."""

    index: uint64
    validator_index: uint64
    address: ExecutionAddress
    amount: uint64


# =============================================================================
# SSZ Container Definitions - Electra Request Types
# =============================================================================


class DepositRequest(Container):
    """DepositRequest as defined in the CL Electra spec."""

    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: uint64
    signature: BLSSignature
    index: uint64


class WithdrawalRequest(Container):
    """WithdrawalRequest as defined in the CL Electra spec."""

    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    amount: uint64


class ConsolidationRequest(Container):
    """ConsolidationRequest as defined in the CL Electra spec."""

    source_address: ExecutionAddress
    source_pubkey: BLSPubkey
    target_pubkey: BLSPubkey


class ExecutionRequests(Container):
    """ExecutionRequests as defined in the CL Electra spec."""

    deposits: List[DepositRequest, MAX_DEPOSIT_REQUESTS_PER_PAYLOAD]
    withdrawals: List[WithdrawalRequest, MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD]
    consolidations: List[ConsolidationRequest, MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD]


# =============================================================================
# SSZ Container Definitions - Bellatrix
# =============================================================================


class BellatrixExecutionPayloadHeader(Container):
    """ExecutionPayloadHeader for Bellatrix fork."""

    parent_hash: Root
    fee_recipient: ExecutionAddress
    state_root: Root
    receipts_root: Root
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ExtraData
    base_fee_per_gas: uint256
    block_hash: Root
    transactions_root: Root


class BellatrixExecutionPayload(Container):
    """ExecutionPayload for Bellatrix fork."""

    parent_hash: Root
    fee_recipient: ExecutionAddress
    state_root: Root
    receipts_root: Root
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ExtraData
    base_fee_per_gas: uint256
    block_hash: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]


class BellatrixBuilderBid(Container):
    """BuilderBid for Bellatrix fork."""

    header: BellatrixExecutionPayloadHeader
    value: uint256
    pubkey: BLSPubkey


class BellatrixSignedBuilderBid(Container):
    """SignedBuilderBid for Bellatrix fork."""

    message: BellatrixBuilderBid
    signature: BLSSignature


class BellatrixBlindedBeaconBlockBody(Container):
    """BlindedBeaconBlockBody for Bellatrix fork."""

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: BellatrixExecutionPayloadHeader


class BellatrixBlindedBeaconBlock(Container):
    """BlindedBeaconBlock for Bellatrix fork."""

    slot: uint64
    proposer_index: uint64
    parent_root: Root
    state_root: Root
    body: BellatrixBlindedBeaconBlockBody


class BellatrixSignedBlindedBeaconBlock(Container):
    """SignedBlindedBeaconBlock for Bellatrix fork."""

    message: BellatrixBlindedBeaconBlock
    signature: BLSSignature


# =============================================================================
# SSZ Container Definitions - Capella
# =============================================================================


class CapellaExecutionPayloadHeader(Container):
    """ExecutionPayloadHeader for Capella fork."""

    parent_hash: Root
    fee_recipient: ExecutionAddress
    state_root: Root
    receipts_root: Root
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ExtraData
    base_fee_per_gas: uint256
    block_hash: Root
    transactions_root: Root
    withdrawals_root: Root


class CapellaExecutionPayload(Container):
    """ExecutionPayload for Capella fork."""

    parent_hash: Root
    fee_recipient: ExecutionAddress
    state_root: Root
    receipts_root: Root
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ExtraData
    base_fee_per_gas: uint256
    block_hash: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]


class CapellaBuilderBid(Container):
    """BuilderBid for Capella fork."""

    header: CapellaExecutionPayloadHeader
    value: uint256
    pubkey: BLSPubkey


class CapellaSignedBuilderBid(Container):
    """SignedBuilderBid for Capella fork."""

    message: CapellaBuilderBid
    signature: BLSSignature


class CapellaBlindedBeaconBlockBody(Container):
    """BlindedBeaconBlockBody for Capella fork."""

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: CapellaExecutionPayloadHeader
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]


class CapellaBlindedBeaconBlock(Container):
    """BlindedBeaconBlock for Capella fork."""

    slot: uint64
    proposer_index: uint64
    parent_root: Root
    state_root: Root
    body: CapellaBlindedBeaconBlockBody


class CapellaSignedBlindedBeaconBlock(Container):
    """SignedBlindedBeaconBlock for Capella fork."""

    message: CapellaBlindedBeaconBlock
    signature: BLSSignature


# =============================================================================
# SSZ Container Definitions - Deneb
# =============================================================================


class DenebExecutionPayloadHeader(Container):
    """ExecutionPayloadHeader for Deneb fork.
    
    Field order per consensus-specs/specs/deneb/beacon-chain.md#executionpayloadheader
    """

    parent_hash: Root
    fee_recipient: ExecutionAddress
    state_root: Root
    receipts_root: Root
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ExtraData
    base_fee_per_gas: uint256
    block_hash: Root
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: uint64
    excess_blob_gas: uint64


class DenebExecutionPayload(Container):
    """ExecutionPayload for Deneb fork.
    
    Field order per consensus-specs/specs/deneb/beacon-chain.md#executionpayload
    """

    parent_hash: Root
    fee_recipient: ExecutionAddress
    state_root: Root
    receipts_root: Root
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ExtraData
    base_fee_per_gas: uint256
    block_hash: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64


class DenebBlobsBundle(Container):
    """BlobsBundle for Deneb fork."""

    commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    proofs: List[KZGProof, MAX_BLOBS_PER_BLOCK]
    blobs: List[Blob, MAX_BLOBS_PER_BLOCK]


class DenebExecutionPayloadAndBlobsBundle(Container):
    """ExecutionPayloadAndBlobsBundle for Deneb fork."""

    execution_payload: DenebExecutionPayload
    blobs_bundle: DenebBlobsBundle


class DenebBuilderBid(Container):
    """BuilderBid for Deneb fork."""

    header: DenebExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    value: uint256
    pubkey: BLSPubkey


class DenebSignedBuilderBid(Container):
    """SignedBuilderBid for Deneb fork."""

    message: DenebBuilderBid
    signature: BLSSignature


class DenebBlindedBeaconBlockBody(Container):
    """BlindedBeaconBlockBody for Deneb fork."""

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: DenebExecutionPayloadHeader
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]


class DenebBlindedBeaconBlock(Container):
    """BlindedBeaconBlock for Deneb fork."""

    slot: uint64
    proposer_index: uint64
    parent_root: Root
    state_root: Root
    body: DenebBlindedBeaconBlockBody


class DenebSignedBlindedBeaconBlock(Container):
    """SignedBlindedBeaconBlock for Deneb fork."""

    message: DenebBlindedBeaconBlock
    signature: BLSSignature


# =============================================================================
# SSZ Container Definitions - Electra
# =============================================================================


class ElectraBuilderBid(Container):
    """BuilderBid for Electra fork."""

    header: DenebExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests
    value: uint256
    pubkey: BLSPubkey


class ElectraSignedBuilderBid(Container):
    """SignedBuilderBid for Electra fork."""

    message: ElectraBuilderBid
    signature: BLSSignature


class ElectraBlindedBeaconBlockBody(Container):
    """BlindedBeaconBlockBody for Electra fork."""

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[ElectraAttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    attestations: List[ElectraAttestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: DenebExecutionPayloadHeader
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests: ExecutionRequests


class ElectraBlindedBeaconBlock(Container):
    """BlindedBeaconBlock for Electra fork."""

    slot: uint64
    proposer_index: uint64
    parent_root: Root
    state_root: Root
    body: ElectraBlindedBeaconBlockBody


class ElectraSignedBlindedBeaconBlock(Container):
    """SignedBlindedBeaconBlock for Electra fork."""

    message: ElectraBlindedBeaconBlock
    signature: BLSSignature


class ElectraExecutionPayloadAndBlobsBundle(Container):
    """ExecutionPayloadAndBlobsBundle for Electra fork."""

    execution_payload: DenebExecutionPayload
    blobs_bundle: DenebBlobsBundle


# =============================================================================
# SSZ Container Definitions - Fulu
# =============================================================================


class FuluBlobsBundle(Container):
    """BlobsBundle for Fulu fork with cell proofs."""

    commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    proofs: List[KZGProof, MAX_CELL_PROOFS_PER_PAYLOAD]
    blobs: List[Blob, MAX_BLOBS_PER_BLOCK]


class FuluExecutionPayloadAndBlobsBundle(Container):
    """ExecutionPayloadAndBlobsBundle for Fulu fork."""

    execution_payload: DenebExecutionPayload
    blobs_bundle: FuluBlobsBundle


# Fulu uses the same BuilderBid structure as Electra
FuluBuilderBid = ElectraBuilderBid


class FuluSignedBuilderBid(Container):
    """SignedBuilderBid for Fulu fork."""

    message: FuluBuilderBid
    signature: BLSSignature


# Fulu uses the same BlindedBeaconBlock structure as Electra
FuluBlindedBeaconBlockBody = ElectraBlindedBeaconBlockBody
FuluBlindedBeaconBlock = ElectraBlindedBeaconBlock


class FuluSignedBlindedBeaconBlock(Container):
    """SignedBlindedBeaconBlock for Fulu fork."""

    message: FuluBlindedBeaconBlock
    signature: BLSSignature


# =============================================================================
# Type Mapping
# =============================================================================


@dataclass
class ExampleTypeInfo:
    """Information about an example type."""

    ssz_type: type[Container]
    json_extractor: Callable[[dict[str, Any]], dict[str, Any]]


def extract_signed_builder_bid(data: dict[str, Any]) -> dict[str, Any]:
    """Extract SignedBuilderBid from JSON wrapper."""
    return data["value"]["data"]


def extract_execution_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Extract ExecutionPayload from JSON wrapper."""
    return data["value"]["data"]


def extract_execution_payload_and_blobs_bundle(data: dict[str, Any]) -> dict[str, Any]:
    """Extract ExecutionPayloadAndBlobsBundle from JSON wrapper."""
    return data["value"]["data"]


def extract_signed_validator_registrations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract SignedValidatorRegistration list from JSON wrapper."""
    return data["value"]


def extract_signed_blinded_beacon_block(data: dict[str, Any]) -> dict[str, Any]:
    """Extract SignedBlindedBeaconBlock from JSON wrapper."""
    return data["value"]


# Map (fork, example_name) to type information
EXAMPLE_TYPES: dict[tuple[str, str], ExampleTypeInfo] = {
    # Bellatrix
    ("bellatrix", "signed_builder_bid"): ExampleTypeInfo(
        BellatrixSignedBuilderBid, extract_signed_builder_bid
    ),
    ("bellatrix", "execution_payload"): ExampleTypeInfo(
        BellatrixExecutionPayload, extract_execution_payload
    ),
    ("bellatrix", "signed_blinded_beacon_block"): ExampleTypeInfo(
        BellatrixSignedBlindedBeaconBlock, extract_signed_blinded_beacon_block
    ),
    # Capella
    ("capella", "signed_builder_bid"): ExampleTypeInfo(
        CapellaSignedBuilderBid, extract_signed_builder_bid
    ),
    ("capella", "execution_payload"): ExampleTypeInfo(
        CapellaExecutionPayload, extract_execution_payload
    ),
    ("capella", "signed_blinded_beacon_block"): ExampleTypeInfo(
        CapellaSignedBlindedBeaconBlock, extract_signed_blinded_beacon_block
    ),
    # Deneb
    ("deneb", "signed_builder_bid"): ExampleTypeInfo(
        DenebSignedBuilderBid, extract_signed_builder_bid
    ),
    ("deneb", "execution_payload_and_blobs_bundle"): ExampleTypeInfo(
        DenebExecutionPayloadAndBlobsBundle, extract_execution_payload_and_blobs_bundle
    ),
    ("deneb", "signed_blinded_beacon_block"): ExampleTypeInfo(
        DenebSignedBlindedBeaconBlock, extract_signed_blinded_beacon_block
    ),
    # Electra
    ("electra", "signed_builder_bid"): ExampleTypeInfo(
        ElectraSignedBuilderBid, extract_signed_builder_bid
    ),
    ("electra", "execution_payload_and_blobs_bundle"): ExampleTypeInfo(
        ElectraExecutionPayloadAndBlobsBundle,
        extract_execution_payload_and_blobs_bundle,
    ),
    ("electra", "signed_blinded_beacon_block"): ExampleTypeInfo(
        ElectraSignedBlindedBeaconBlock, extract_signed_blinded_beacon_block
    ),
    # Fulu
    ("fulu", "signed_builder_bid"): ExampleTypeInfo(
        FuluSignedBuilderBid, extract_signed_builder_bid
    ),
    ("fulu", "execution_payload_and_blobs_bundle"): ExampleTypeInfo(
        FuluExecutionPayloadAndBlobsBundle, extract_execution_payload_and_blobs_bundle
    ),
    ("fulu", "signed_blinded_beacon_block"): ExampleTypeInfo(
        FuluSignedBlindedBeaconBlock, extract_signed_blinded_beacon_block
    ),
}


def resolve_all_container_annotations() -> None:
    """Resolve stringified (postponed) annotations for Container subclasses.

    Some classes may have annotations stored as strings (PEP 563). Remerkleable
    inspects annotations to build field metadata; if annotations remain strings
    the library may keep unresolved types which break serialization. This
    attempts to evaluate annotation strings in the module global namespace.
    """
    g = globals()
    for name, obj in list(g.items()):
        try:
            if isinstance(obj, type) and issubclass(obj, Container):
                ann = getattr(obj, "__annotations__", {})
                changed = False
                for k, v in list(ann.items()):
                    if isinstance(v, str):
                        try:
                            resolved = eval(v, g)
                        except Exception:
                            resolved = g.get(v, v)
                        if resolved is not v:
                            ann[k] = resolved
                            changed = True
                if changed:
                    obj.__annotations__ = ann
        except Exception:
            # Be forgiving: don't fail module import if resolution fails
            continue


def rebuild_container_classes() -> None:
    """Recreate Container subclasses so remerkleable builds proper Field metadata.

    When classes were defined with postponed annotations (strings), remerkleable
    sometimes stores unresolved annotation strings inside its internal field
    structures. Re-creating the class with evaluated annotations forces the
    Container metaclass to build concrete Field objects with resolved types.
    """
    g = globals()
    # Collect names to rebuild to avoid modifying dict during iteration
    to_rebuild = [name for name, obj in g.items() if isinstance(obj, type) and issubclass(obj, Container) and obj.__module__ == __name__]

    for name in to_rebuild:
        old_cls = g[name]
        ann = getattr(old_cls, "__annotations__", {})
        doc = getattr(old_cls, "__doc__", None)
        # Create a new class using evaluated annotations
        try:
            New = type(name, (Container,), {"__annotations__": ann, "__doc__": doc})
            New.__module__ = __name__
            g[name] = New
        except Exception:
            # If class recreation fails for any reason, skip it but continue
            continue


# =============================================================================
# JSON to SSZ Conversion Utilities
# =============================================================================


def hex_to_bytes(hex_str: str) -> bytes:
    """Convert a hex string (with 0x prefix) to bytes."""
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]
    return bytes.fromhex(hex_str)


def is_byte_vector_type(t: type) -> bool:
    """Check if a type is a ByteVector subclass."""
    try:
        cls = t if isinstance(t, type) else t.__class__
        if hasattr(cls, "__mro__") and any(
            c.__name__ == "ByteVector" for c in cls.__mro__ if hasattr(c, "__name__")
        ):
            return True
        # remerkleable view classes often have names like SpecialByteVectorView
        name = getattr(cls, "__name__", "")
        if "ByteVector" in name or "SpecialByteVectorView" in name:
            return True
        if "ByteVector" in repr(t):
            return True
        return False
    except (TypeError, AttributeError):
        return False


def is_byte_list_type(t: type) -> bool:
    """Check if a type is a ByteList subclass."""
    try:
        cls = t if isinstance(t, type) else t.__class__
        if hasattr(cls, "__mro__") and any(
            c.__name__ == "ByteList" for c in cls.__mro__ if hasattr(c, "__name__")
        ):
            return True
        name = getattr(cls, "__name__", "")
        if "ByteList" in name or "SpecialByteListView" in name:
            return True
        if "ByteList" in repr(t):
            return True
        return False
    except (TypeError, AttributeError):
        return False


def is_container_type(t: type) -> bool:
    """Check if a type is a Container subclass."""
    try:
        return hasattr(t, "__mro__") and any(
            c.__name__ == "Container" for c in t.__mro__ if hasattr(c, "__name__")
        )
    except (TypeError, AttributeError):
        return False


def is_list_type(t: type) -> bool:
    """Check if a type is an SSZ List type."""
    try:
        if hasattr(t, "__class__") and t.__class__.__name__ == "ListMeta":
            return True
        # remerkleable list-like types expose an element_cls attribute
        if hasattr(t, "element_cls"):
            return True
        # Fallback: heuristics on repr or stringified types
        if isinstance(t, str) and "List[" in t:
            return True
        if "List[" in repr(t):
            return True
        return False
    except (TypeError, AttributeError):
        return False


def is_uint_type(t: type) -> bool:
    """Check if a type is a uint type."""
    try:
        return t in (uint8, uint64, uint256) or (
            hasattr(t, "__mro__") and any(
                c.__name__ in ("uint8", "uint64", "uint256", "uint")
                for c in t.__mro__ if hasattr(c, "__name__")
            )
        )
    except (TypeError, AttributeError):
        return False


def json_to_ssz_value(json_value: Any, ssz_type: type) -> Any:
    """Convert a JSON value to the corresponding SSZ type."""
    # If annotation came through as a string (postponed annotations), try to resolve it
    if isinstance(ssz_type, str):
        try:
            ssz_type = eval(ssz_type, globals())
        except Exception:
            ssz_type = globals().get(ssz_type, ssz_type)

    # Handle basic integers
    if is_uint_type(ssz_type):
        if isinstance(json_value, str):
            return ssz_type(int(json_value))
        return ssz_type(json_value)

    # Handle ByteVector types
    if is_byte_vector_type(ssz_type):
        return ssz_type(hex_to_bytes(json_value))

    # Handle ByteList types
    if is_byte_list_type(ssz_type):
        return ssz_type(hex_to_bytes(json_value))

    # Handle List types
    if is_list_type(ssz_type):
        element_type_instance = ssz_type.element_cls()
        elements = [json_to_ssz_value(item, element_type_instance) for item in json_value]
        return ssz_type(*elements)

    # Handle Container types
    if is_container_type(ssz_type):
        return json_to_container(json_value, ssz_type)

    raise ValueError(f"Unsupported type conversion: {ssz_type}")


def json_to_container(json_data: dict[str, Any], container_type: type[Container]) -> Container:
    """Convert JSON data to an SSZ Container instance."""
    kwargs = {}

    # If a List type was passed, handle it as a list conversion
    if is_list_type(container_type):
        if not isinstance(json_data, list):
            raise ValueError(f"Expected list for type {container_type}, got {type(json_data)}")
        element_type = container_type.element_cls()
        elements = [json_to_ssz_value(item, type(element_type)) for item in json_data]
        return container_type(*elements)

    # Use class annotations (avoids remerkleable's internal Field objects which
    # may contain unresolved stringified types). Annotations preserve order.
    annotations = getattr(container_type, "__annotations__", {})
    for field_name, field_type in annotations.items():
        if field_name not in json_data:
            raise ValueError(f"Missing field '{field_name}' in JSON data for {container_type.__name__}")

        json_value = json_data[field_name]
        actual_type = field_type

        # Resolve stringified annotations if present
        if isinstance(actual_type, str):
            # Try globals() first, then eval as a last resort
            resolved = globals().get(actual_type)
            if resolved is None:
                try:
                    resolved = eval(actual_type, globals())
                except Exception:
                    resolved = actual_type
            actual_type = resolved

        # Handle List types first (avoid misclassifying List[...] as ByteList)
        if is_list_type(actual_type):
            element_type_instance = actual_type.element_cls()

            if isinstance(json_value, list):
                elements = []
                for item in json_value:
                    elements.append(json_to_ssz_value(item, element_type_instance))
                kwargs[field_name] = actual_type(*elements)
            else:
                raise ValueError(f"Expected list for field '{field_name}', got {type(json_value)}")

        # Handle basic integer types
        elif is_uint_type(actual_type):
            if isinstance(json_value, str):
                kwargs[field_name] = actual_type(int(json_value))
            else:
                kwargs[field_name] = actual_type(json_value)

        # Handle ByteVector types (fixed-size byte arrays)
        elif is_byte_vector_type(actual_type):
            kwargs[field_name] = actual_type(hex_to_bytes(json_value))

        # Handle ByteList types (variable-size byte arrays)
        elif is_byte_list_type(actual_type):
            kwargs[field_name] = actual_type(hex_to_bytes(json_value))

        # Handle nested Container types
        elif is_container_type(actual_type):
            kwargs[field_name] = json_to_container(json_value, actual_type)

        else:
            raise ValueError(
                f"Unsupported field type for '{field_name}': {actual_type} "
                f"(type class: {type(actual_type).__name__})"
            )

    return container_type(**kwargs)


# =============================================================================
# Validation Result
# =============================================================================


@dataclass
class ValidationResult:
    """Result of validating a single example."""

    fork: str
    example_name: str
    success: bool
    error_message: str | None = None


# =============================================================================
# Validation Functions
# =============================================================================


def validate_signed_validator_registrations(
    json_path: Path, ssz_path: Path
) -> ValidationResult:
    """Validate SignedValidatorRegistrations example (special case - array type)."""
    fork = json_path.parent.name
    example_name = json_path.stem

    try:
        # Load JSON
        with open(json_path, "r") as f:
            json_data = json.load(f)

        # Load SSZ
        with open(ssz_path, "rb") as f:
            ssz_bytes = f.read()

        # Extract registrations from JSON wrapper
        registrations_json = extract_signed_validator_registrations(json_data)

        # Convert JSON to SSZ objects
        json_registrations = []
        for reg in registrations_json:
            json_registrations.append(json_to_container(reg, SignedValidatorRegistration))

        # Serialize JSON-derived objects to SSZ bytes
        # For a list of containers, we concatenate their serializations
        # with a 4-byte offset prefix for each element
        json_derived_bytes = b""
        
        # Calculate the fixed part size (4 bytes per offset)
        fixed_part_size = 4 * len(json_registrations)
        
        # Build offsets and variable parts
        variable_parts = []
        for reg in json_registrations:
            variable_parts.append(reg.encode_bytes())
        
        # Write offsets (little-endian uint32)
        current_offset = fixed_part_size
        for var_part in variable_parts:
            json_derived_bytes += current_offset.to_bytes(4, "little")
            current_offset += len(var_part)
        
        # Write variable parts
        for var_part in variable_parts:
            json_derived_bytes += var_part

        # Compare bytes
        if json_derived_bytes == ssz_bytes:
            logger.debug(f"✓ {fork}/{example_name}: JSON and SSZ match")
            return ValidationResult(fork, example_name, True)
        else:
            # Try alternative: direct concatenation without offsets
            # (depends on how the SSZ was originally created)
            direct_concat = b"".join(reg.encode_bytes() for reg in json_registrations)
            if direct_concat == ssz_bytes:
                logger.debug(f"✓ {fork}/{example_name}: JSON and SSZ match (direct concat)")
                return ValidationResult(fork, example_name, True)

            logger.error(f"✗ {fork}/{example_name}: JSON and SSZ do not match")
            logger.debug(f"  JSON-derived length: {len(json_derived_bytes)}")
            logger.debug(f"  SSZ file length: {len(ssz_bytes)}")
            return ValidationResult(
                fork,
                example_name,
                False,
                f"Byte mismatch: JSON-derived={len(json_derived_bytes)} bytes, "
                f"SSZ file={len(ssz_bytes)} bytes",
            )

    except Exception as e:
        logger.error(f"✗ {fork}/{example_name}: Error - {e}")
        return ValidationResult(fork, example_name, False, str(e))


def validate_example(json_path: Path, ssz_path: Path) -> ValidationResult:
    """Validate a single JSON/SSZ example pair."""
    fork = json_path.parent.name
    example_name = json_path.stem

    # Special handling for signed_validator_registrations (array type)
    if example_name == "signed_validator_registrations":
        return validate_signed_validator_registrations(json_path, ssz_path)

    # Get type info for this example
    type_key = (fork, example_name)
    if type_key not in EXAMPLE_TYPES:
        logger.warning(f"⚠ {fork}/{example_name}: No type definition found, skipping")
        return ValidationResult(
            fork, example_name, True, "Skipped - no type definition"
        )

    type_info = EXAMPLE_TYPES[type_key]

    try:
        # Load JSON
        with open(json_path, "r") as f:
            json_data = json.load(f)

        # Load SSZ
        with open(ssz_path, "rb") as f:
            ssz_bytes = f.read()

        # Extract the relevant data from JSON wrapper
        extracted_json = type_info.json_extractor(json_data)

        # Convert JSON to SSZ object
        json_ssz_obj = json_to_container(extracted_json, type_info.ssz_type)

        # Serialize the JSON-derived object to SSZ bytes
        json_derived_bytes = json_ssz_obj.encode_bytes()

        # Compare bytes
        if json_derived_bytes == ssz_bytes:
            logger.debug(f"✓ {fork}/{example_name}: JSON and SSZ match")
            return ValidationResult(fork, example_name, True)
        else:
            logger.error(f"✗ {fork}/{example_name}: JSON and SSZ do not match")
            logger.debug(f"  JSON-derived length: {len(json_derived_bytes)}")
            logger.debug(f"  SSZ file length: {len(ssz_bytes)}")
            
            # Find first difference for debugging
            for i, (a, b) in enumerate(zip(json_derived_bytes, ssz_bytes)):
                if a != b:
                    logger.debug(f"  First difference at byte {i}: JSON={a:02x}, SSZ={b:02x}")
                    break
            
            return ValidationResult(
                fork,
                example_name,
                False,
                f"Byte mismatch: JSON-derived={len(json_derived_bytes)} bytes, "
                f"SSZ file={len(ssz_bytes)} bytes",
            )

    except Exception as e:
        logger.error(f"✗ {fork}/{example_name}: Error - {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return ValidationResult(fork, example_name, False, str(e))


def find_example_pairs(
    examples_dir: Path, fork_filter: str | None = None, example_filter: str | None = None
) -> list[tuple[Path, Path]]:
    """Find all JSON/SSZ example pairs in the examples directory."""
    pairs = []

    for fork_dir in sorted(examples_dir.iterdir()):
        if not fork_dir.is_dir():
            continue

        fork = fork_dir.name
        if fork not in FORKS:
            continue

        if fork_filter and fork != fork_filter:
            continue

        # Find all JSON files and their SSZ counterparts
        for json_file in sorted(fork_dir.glob("*.json")):
            example_name = json_file.stem
            
            if example_filter and example_name != example_filter:
                continue

            ssz_file = fork_dir / f"{example_name}.ssz"
            if ssz_file.exists():
                pairs.append((json_file, ssz_file))
            else:
                logger.warning(f"⚠ {fork}/{example_name}: Missing SSZ file")

    return pairs


def validate_all_examples(
    examples_dir: Path,
    fork_filter: str | None = None,
    example_filter: str | None = None,
) -> list[ValidationResult]:
    """Validate all example pairs and return results."""
    pairs = find_example_pairs(examples_dir, fork_filter, example_filter)
    results = []

    logger.info(f"Found {len(pairs)} example pair(s) to validate")
    logger.info("-" * 60)

    for json_path, ssz_path in pairs:
        result = validate_example(json_path, ssz_path)
        results.append(result)

    return results


def print_summary(results: list[ValidationResult]) -> None:
    """Print a summary of validation results."""
    passed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    logger.info("-" * 60)
    logger.info(f"Summary: {passed} passed, {failed} failed, {len(results)} total")

    if failed > 0:
        logger.info("\nFailed examples:")
        for r in results:
            if not r.success:
                logger.info(f"  - {r.fork}/{r.example_name}: {r.error_message}")


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate JSON and SSZ example pairs in the builder-specs repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Validate all examples
  %(prog)s --verbose                # Validate with detailed output
  %(prog)s --fork deneb             # Validate only Deneb examples
  %(prog)s --example signed_builder_bid  # Validate only signed_builder_bid examples
        """,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with debug information",
    )

    parser.add_argument(
        "-f",
        "--fork",
        choices=FORKS,
        help="Only validate examples for the specified fork",
    )

    parser.add_argument(
        "-e",
        "--example",
        help="Only validate examples with the specified name (e.g., signed_builder_bid)",
    )

    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=EXAMPLES_DIR,
        help=f"Path to the examples directory (default: {EXAMPLES_DIR})",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    # Ensure annotations are resolved and Container classes rebuilt so
    # remerkleable has concrete Field metadata (not string placeholders).
    resolve_all_container_annotations()
    rebuild_container_classes()

    logger.info("Builder-specs JSON/SSZ Example Validator")
    logger.info("=" * 60)

    if not args.examples_dir.exists():
        logger.error(f"Examples directory not found: {args.examples_dir}")
        return 2

    results = validate_all_examples(
        args.examples_dir,
        fork_filter=args.fork,
        example_filter=args.example,
    )

    print_summary(results)

    # Return 1 if any validations failed
    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
