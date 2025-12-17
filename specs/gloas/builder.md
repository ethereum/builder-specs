<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gloas - Builder Specification](#gloas---builder-specification)
  - [Introduction](#introduction)
    - [Constructing a `SignedExecutionPayloadBid`](#constructing-a-signedexecutionpayloadbid)
    - [Constructing a `SignedExecutionPayloadEnvelope`](#constructing-a-signedexecutionpayloadenvelope)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Builder Specification

## Introduction

This document documents the builder behaviour with the Builder-API.

### `ValidatorRegistrationV1` are deprecated

With Gloas, `ValidatorRegistrations` are deprecated. Pre-Gloas, Validators used `ValidatorRegistrationV1` to signal their 
preferred `fee_receipient` and `gas_limit` to the builder. 

Now, A proposer can indicate the `fee_receipient` to which they want the builder to pay as a header while requesting the 
`SignedExecutionPayloadBid`.

### Constructing a `SignedExecutionPayloadBid`

The specification for a block builder to construct a `SignedExecutionPayloadBid` is documented in the 
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].

### Constructing a `SignedExecutionPayloadEnvelope`

The specification for a block builder to construct a `SignedExecutionPayloadEnvelope` is documented in the 
gloas-specs[https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/builder.md].
