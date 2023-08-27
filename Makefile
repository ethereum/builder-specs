SPEC_DIR = ./specs
TESTS_DIR = ./tests/core

PY_SPEC_DIR = $(TESTS_DIR)/pyspec
SPEC_MODULE_DIR = $(PY_SPEC_DIR)/builderspec

SPECS = bellatrix capella

clean:
	rm -rf venv;
	@for spec in $(SPECS) ; do \
		rm -rf $(SPEC_MODULE_DIR)/$$spec; \
	done

# make (i.e. generate) the pyspec
pyspec:
	python3 -m venv venv
	. venv/bin/activate
	pip install marko
	pip install git+https://github.com/ethereum/consensus-specs.git
	python3 spec.py --specs $(SPECS)

# test the pyspec
test: pyspec
	. venv/bin/activate
	pip install pytest
	python3 -m pytest $(PY_SPEC_DIR)/builderspec/test
