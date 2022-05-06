# Ethereum Builder Specification

![CI](https://github.com/ethereum/builder-spec/workflows/CI/badge.svg)

Collection of RESTful APIs provided by external builder nodes.

## Render 

To render spec in browser you will need any http server to load `index.html` file
in root of the repo.

##### Python

```
python -m http.server 8080
```
And api spec will render on [http://localhost:8080](http://localhost:8080).

### Usage

Local changes will be observable if "dev" is selected in the "Select a definition" drop-down in the web UI.

Users may need to tick the "Disable Cache" box in their browser's developer tools to see changes after modifying the source. 

## Contributing

API spec is checked for lint errors before merge. 

To run lint locally, install linter with
```
npm install -g @stoplight/spectral-cli@6.2.1
```
and run lint with
```
spectral lint builder-oapi.yaml
```

## Releasing

1. Create and push tag

   - Make sure info.version in builder-oapi.yaml file is updated before tagging.
   - CD will create github release and upload bundled spec file

2. Add release entrypoint in index.html

In SwaggerUIBundle configuration (inside index.html file), add another entry in "urls" field (SwaggerUI will load first item as default).
Entry should be in following format(replace `<tag>` with real tag name from step 1.):
```javascript
         {url: "https://github.com/ethereum/builder-apis/releases/download/<tag>/builder-oapi.yaml", name: "<tag>"},
```
