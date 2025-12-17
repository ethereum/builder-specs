UV_RUN    = uv run

MARKDOWN_FILES := $(shell find $(CURDIR) -name '*.md')

_sync: pyproject.toml
	@command -v uv >/dev/null 2>&1 || { \
		echo "Error: uv is required but not installed."; \
		echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}
	@uv sync --all-extras $(MAYBE_VERBOSE)

lint: _sync
	@uv --quiet lock --check
	@$(UV_RUN) mdformat --number --wrap=80 $(MARKDOWN_FILES)
	@$(UV_RUN) codespell
	@redocly lint builder-oapi.yaml