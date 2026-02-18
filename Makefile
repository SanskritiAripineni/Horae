APP_DIR := apps/mindful-rag
APP_VENV_PY := $(APP_DIR)/.venv/bin/python
PYTHON := $(if $(wildcard $(APP_VENV_PY)),$(APP_VENV_PY),python3)
APP_CMD := PYTHONPATH=$(APP_DIR)/src $(PYTHON) -m mindful_rag

.PHONY: help install ingest-help run-help verify-help ingest-by-type ingest-intro-concl ingest-raw ingest-csv-sources ingest-all run-by-type run-csv-sources verify-by-type verify-csv-sources csv-all test compile check

help:
	@echo "Simple targets:"
	@echo "  make install            Install dependencies (uses app venv if present)"
	@echo "  make ingest-by-type     Run by_type ingestion"
	@echo "  make ingest-intro-concl Run intro_concl ingestion"
	@echo "  make ingest-raw         Run raw ingestion (with --reset-db)"
	@echo "  make ingest-csv-sources Ingest CSV columns (relevant_info + intro_concl) for source-filter tests"
	@echo "  make ingest-all         Run by_type + intro_concl + raw"
	@echo "  make run-by-type        Run app with by_type experiment"
	@echo "  make run-csv-sources    Run app with csv_sources experiment"
	@echo "  make verify-by-type     Verify by_type vector DB"
	@echo "  make verify-csv-sources Verify csv_sources vector DB"
	@echo "  make csv-all            Build one CSV with by_type/intro_concl/raw text columns"
	@echo "  make ingest-help        Show ingest CLI flags"
	@echo "  make run-help           Show run-app CLI flags"
	@echo "  make verify-help        Show verify-chroma CLI flags"
	@echo "  make test               Run retrieval unit tests"
	@echo "  make compile            Compile-check app Python files"
	@echo "  make check              Run compile + test"

install:
	$(PYTHON) -m pip install -r $(APP_DIR)/requirements.txt
	$(PYTHON) -m pip install -e $(APP_DIR)

ingest-help:
	$(APP_CMD) ingest --help

run-help:
	$(APP_CMD) run-app --help

verify-help:
	$(APP_CMD) verify-chroma --help

ingest-by-type:
	$(APP_CMD) ingest --experiment by_type

ingest-intro-concl:
	INTRO_CONCL_INDEX_CSV=$(APP_DIR)/data/index/research_index_clean.csv $(APP_CMD) ingest --experiment intro_concl

ingest-raw:
	$(APP_CMD) ingest --experiment raw --reset-db

ingest-csv-sources:
	$(APP_CMD) ingest --experiment csv_sources --sources relevant_info,intro_concl

ingest-all: ingest-by-type ingest-intro-concl ingest-raw

run-by-type:
	$(APP_CMD) run-app --experiment by_type

run-csv-sources:
	$(APP_CMD) run-app --experiment csv_sources

verify-by-type:
	$(APP_CMD) verify-chroma --experiment by_type

verify-csv-sources:
	$(APP_CMD) verify-chroma --experiment csv_sources

csv-all:
	PYTHONPATH=$(APP_DIR)/src $(PYTHON) $(APP_DIR)/scripts/build_ingestion_csv.py

test:
	PYTHONPATH=$(APP_DIR)/src $(PYTHON) $(APP_DIR)/tests/test_retrieval.py

compile:
	PYTHONPYCACHEPREFIX=/tmp/pycache $(PYTHON) -m compileall \
		$(APP_DIR)/src \
		$(APP_DIR)/scripts \
		$(APP_DIR)/tests

check: compile test
