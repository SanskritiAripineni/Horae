APP_DIR := apps/mindful-rag

.PHONY: help install app-install ingest run-app verify test compile check

help:
	@echo "Available targets:"
	@echo "  make install         Install app dependencies and editable package"
	@echo "  make ingest          Show ingest CLI help"
	@echo "  make run-app         Show run-app CLI help"
	@echo "  make verify          Show verify-chroma CLI help"
	@echo "  make test            Run retrieval unit tests"
	@echo "  make compile         Compile-check app Python files"
	@echo "  make check           Run compile + test"

install:
	python3 -m pip install -r $(APP_DIR)/requirements.txt
	python3 -m pip install -e $(APP_DIR)

ingest:
	python3 $(APP_DIR)/scripts/ingest.py --help

run-app:
	python3 $(APP_DIR)/scripts/run_app.py --help

verify:
	python3 $(APP_DIR)/scripts/verify_chroma.py --help

test:
	python3 $(APP_DIR)/tests/test_retrieval.py

compile:
	PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall \
		$(APP_DIR)/src \
		$(APP_DIR)/scripts \
		$(APP_DIR)/tests

check: compile test
