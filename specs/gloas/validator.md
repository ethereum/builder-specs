<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gloas - Honest Validator](#gloas---honest-validator)
  - [Introduction](#introduction)
    - [Block proposal](#block-proposal)
      - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
        - [ExecutionPayloadBid](#executionpayloadbid)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Gloas - Honest Validator


## Introduction

This document explains how a beacon-chain validator can participate in the external block building market post ePBS. 

Validators request an `ExecutionPayloadBid` from the external builder network to put it in their `SignedBeaconBlock`. 
The external builder network broadcasts the `SignedExecutionPayloadEnvelope` corresponding to the bid to the PTC commitee. 

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayloadBid

To obtain an execution payload, a block proposer building a block on top of a beacon `state` in a given `slot` must take
the following actions:

1. Call upstream builder software to get an `ExecutionPayloadBid`.
2. Assemble a `SignedBeaconBlock` according to the process outlined in the [Gloas specs][https://github.com/ethereum/consensus-specs/blob/master/specs/gloas/validator.md#block-proposal] but with
   the `ExecutionPayloadBid` from the prior step.
3. The proposer returns the `SignedBeaconBlock` back to the upstream block
   building software.
5. The upstream block building software constructs the `SignedExecutionPayloadEnvelope` from the
   `SignedBlindedExecutionPayloadEnvelope` and broadcasts it to the PTC commitee.