# AI Test Generator - Makefile
# User-friendly aliases aligned with QUICKSTART.md

.PHONY: help setup venv deps gen gen-demo gen-confluence show stats export clean verify ls raw-list raw-add raw-cat raw-edit coverage rebuild demo

PYTHON ?= python3
VENV ?= venv
VENV_BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
VENV_BIN := $(VENV)/Scripts
endif
PIP_VENV := $(VENV_BIN)/pip

# Default: show help
help:
	@echo ""
	@echo "AI Test Generator - Quick Commands"
	@echo "==================================="
	@echo ""
	@echo "Setup:"
	@echo "  make venv         - Create virtual environment (venv/)"
	@echo "  make deps         - Install dependencies into venv/"
	@echo "  make setup        - venv + deps"
	@echo ""
	@echo "Generation:"
	@echo "  make gen          - Generate tests from requirements/raw"
	@echo "  make gen-demo     - Generate tests from demo/petstore"
	@echo "  make gen-confluence PAGE_ID=123456789"
	@echo "  make rebuild      - Clean + generate"
	@echo ""
	@echo "State & Export:"
	@echo "  make show         - Show current session state"
	@echo "  make stats        - Show quick statistics"
	@echo "  make coverage     - Analyze test coverage"
	@echo "  make export       - Export tests (excel/csv/both)"
	@echo ""
	@echo "Raw Requirements:"
	@echo "  make ls           - List files in requirements/raw"
	@echo "  make raw-add N=x  - Create new requirement file x.md"
	@echo "  make raw-cat N=x  - Show contents of x.md"
	@echo "  make raw-edit N=x - Edit x.md in editor"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        - Clean state and artifacts (with backup)"
	@echo "  make verify       - Verify generated tests"
	@echo ""
	@echo "Advanced:"
	@echo "  make gen SOURCE=demo/petstore"
	@echo "  make gen FORMAT=excel"
	@echo "  make gen OUTPUT=artifacts/my_tests"
	@echo ""

venv:
	$(PYTHON) -m venv $(VENV)

deps: venv
	$(PIP_VENV) install -r requirements.txt

setup: deps

# Generate tests from raw requirements (default)
SOURCE ?= raw
FORMAT ?= excel
OUTPUT ?= artifacts/test_cases

gen:
	./generate_tests.py --source $(SOURCE) --format $(FORMAT) --output $(OUTPUT)

# Generate from demo
gen-demo:
	./generate_tests.py --source demo/petstore

PAGE_ID ?=
gen-confluence:
	./generate_tests.py --source confluence:$(PAGE_ID)

# Show current state
show:
	$(PYTHON) main.py state show

# Quick statistics
stats:
	$(PYTHON) main.py stats

# Export tests
export:
	$(PYTHON) main.py state export -o $(OUTPUT) -f $(FORMAT) --group-by-layer

# Clean state and artifacts
clean:
	$(PYTHON) main.py clean -y

# Full verify pipeline
verify:
	@echo "Verifying state..."
	$(PYTHON) main.py state show
	@echo ""
	@echo "Statistics:"
	$(PYTHON) main.py stats

# Quick rebuild: clean + generate
rebuild: clean gen

# Run with specific demo
demo:
	./generate_tests.py --source demo/petstore --output artifacts/demo_tests --format $(FORMAT)

# =============================================================================
# Raw Requirements Management
# =============================================================================

# List raw requirements
ls:
	$(PYTHON) main.py ls

raw-list: ls

# Add new requirement file (usage: make raw-add N=auth)
N ?= new_requirement
raw-add:
	$(PYTHON) main.py raw add $(N)

# Show requirement file contents (usage: make raw-cat N=auth)
raw-cat:
	$(PYTHON) main.py raw cat $(N)

# Edit requirement file (usage: make raw-edit N=auth)
raw-edit:
	$(PYTHON) main.py raw edit $(N)

# Analyze test coverage
coverage:
	$(PYTHON) main.py coverage
