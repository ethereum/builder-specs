<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
    - [`ValidatorRegistrationV1` are deprecated](#validatorregistrationv1-are-deprecated)
    - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
    - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)
    - [Sealing the Payload with `fee_recipient`](#sealing-the-payload-with-fee_recipient)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API.

### `ValidatorRegistrationV1` are deprecated

With Gloas, `ValidatorRegistrations` are deprecated. Pre-Gloas, Validators used `ValidatorRegistrationV1` to signal their 
preferred `fee_recipient` and `gas_limit` to the builder. 

Now, A proposer can indicate the `fee_recipient` to which they want the builder to pay as a header while requesting the 
`SignedExecutionPayloadBid`.

### Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a `SignedExecutionPayloadBid` is documented in the 
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].

### Constructing a `SignedExecutionPayloadEnvelope`

The specification for a block builder to construct a `SignedExecutionPayloadEnvelope` is documented in the 
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].

### Sealing the Payload with `fee_recipient`

The builder receives the `fee_recipient` as a header to the call to get the `SignedExecutionPayloadBid`. The builder
is required to seal the block to be sent with the payment transaction to the `fee_recipient` with the amount specified in the
`execution_payment` field in the `ExecutionPayloadBid`. 