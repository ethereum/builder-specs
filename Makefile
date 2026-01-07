UV_RUN    = uv run

MARKDOWN_FILES := $(shell find $(CURDIR) -name '*.md' -not -path "*/beacon-apis/*" -not -path "*/node_modules/*")
MARKDOWN_FILES_FOR_DOCTOC := $(shell find $(CURDIR) -name '*.md' -not -path "*/beacon-apis/*" -not -path "*/node_modules/*" -not -name "README.md")
YAML_FILES := $(shell find $(CURDIR)/apis $(CURDIR)/types -name '*.yaml' -o -name '*.yml')
PYTHON_FILES := $(shell find $(CURDIR)/specs -name '*.md')

_sync: pyproject.toml
	@command -v uv >/dev/null 2>&1 || { \
		echo "Error: uv is required but not installed."; \
		echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}
	@uv sync --all-extras $(MAYBE_VERBOSE)

_check_doctoc:
	@command -v doctoc >/dev/null 2>&1 || { \
		echo "Error: doctoc is required but not installed."; \
		echo "Install with: npm install -g doctoc"; \
		exit 1; \
	}

_check_markdownlint:
	@command -v npx >/dev/null 2>&1 || { \
		echo "Error: npx (Node.js) is required but not installed."; \
		echo "Install Node.js from: https://nodejs.org/"; \
		exit 1; \
	}

lint-lock: _sync
	@uv --quiet lock --check

lint-doctoc: _sync _check_doctoc
	@echo "Running doctoc..."
	@doctoc --notitle $(MARKDOWN_FILES_FOR_DOCTOC)

lint-mdformat: _sync
	@echo "Running mdformat..."
	@$(UV_RUN) mdformat --number --wrap=80 $(MARKDOWN_FILES)

lint-python: _sync
	@echo "Running blacken-docs on Python code blocks..."
	@$(UV_RUN) blacken-docs $(MARKDOWN_FILES)

lint-spelling: _sync
	@echo "Running codespell..."
	@$(UV_RUN) codespell

lint-openapi: _sync
	@echo "Running redocly lint..."
	@redocly lint builder-oapi.yaml

lint: lint-lock lint-doctoc lint-mdformat lint-python lint-spelling lint-openapi
	@echo "All linting checks passed!"