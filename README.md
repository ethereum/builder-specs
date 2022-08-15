# Ethereum Builder API Specification

![CI][ci]

The Builder API is an interface for consensus layer clients to source blocks
built by external entities.

In this repository:
* [API specification][oas-spec]
* [Builder specification][builder-spec]
* [Honest validator specification][validator-spec]


### Builder API is currently deprecated

In lights of current events, and in particular in lights of MEV-Boost adopting OFAC sanctions, the Builder API is momentairly deprecated.
Client Teams **MUST** not implement and expose the Builder API until the situation stabilises. **NOTE: Builder API is only momentairly deprecated, and could eventually be re-considered if the situation changes.**

### Why?

Block building is a specialized activity that requires high fixed costs to be
an efficient validator. This creates an advantage for staking pools as they can
effectively distribute the cost across many validators.

[Proposer-builder separation][pbs] (PBS) fixes this by spliting the roles of a
validator into block proposing and block building. However, PBS requires
modifications to the Beacon chain and will therefore not be possible at the
time of the merge.

The Builder API is a temporary solution that requires higher trust assumptions
than PBS, but can be fully implemented without modification to the base
protocol. This is done by providing the proposer with a "blind" execution layer
header to incorporate into a block and a "value" amount which will be
transferred to the proposer once they create a block with the aforementioned
header. Once the proposer signs a block with the header, they are bound to the
choice (or risk being slashed due to equivocation). That allows the builder to
reveal the blinded transactions without the possibility of the proposer
tampering with them.

This design is based on the original proposal for trusted external builders:
["MEV-Boost: Merge ready Flashbots Architecture"][mev-boost-ethr].

#### Builder software

Users will typically connect their CL clients to builders with builder
multiplexers. Please see their respective repositories for more information:

* [`mev-boost`][mev-boost]
* [`mev-rs`][mev-rs]

## Contributing

The API specification is checked for lint errors before merging pull requests.

To run the linter locally, install it with:
```console
npm install -g @stoplight/spectral-cli@6.2.1
```
and then run it:
```console
spectral lint builder-oapi.yaml
```

### Render API Specification

To render spec in browser, you will simply need an HTTP server to load the
`index.html` file in root of the repo.

For example:
```console
python -m http.server 8080
```

The spec will render at [http://localhost:8080](http://localhost:8080).

### Usage

Local changes will be observable if "dev" is selected in the "Select a
definition" drop-down in the web UI.

It may be necessary to tick the "Disable Cache" box in their browser's
developer tools to see changes after modifying the source. 

## Releasing

1. Create and push tag
   - Make sure `info.version` in `builder-oapi.yaml` file is updated before
     tagging.
   - CI will create a github release and upload bundled spec file
2. Add release entrypoint in `index.html`

In `SwaggerUIBundle` configuration (inside `index.html` file), add another
entry in `urls` field. Entry should be in following format (replace `<tag>`
with real tag name from step 1.):

```javascript
{url: "https://github.com/ethereum/builder-apis/releases/download/<tag>/builder-oapi.yaml", name: "<tag>"},
```

[ci]: https://github.com/ethereum/builder-specs/workflows/CI/badge.svg
[oas-spec]: https://ethereum.github.io/builder-specs/
[builder-spec]: specs/builder.md
[validator-spec]: specs/validator.md
[pbs]: https://ethresear.ch/t/proposer-block-builder-separation-friendly-fee-market-designs/9725
[mev-boost-ethr]: https://ethresear.ch/t/mev-boost-merge-ready-flashbots-architecture/11177
[mev-boost]: https://github.com/flashbots/mev-boost
[mev-rs]: https://github.com/ralexstokes/mev-rs
