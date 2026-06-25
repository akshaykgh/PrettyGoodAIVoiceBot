PYTHON := .venv/bin/python3
APP := pgai_voice_bot.cli

.PHONY: help install serve call suite fetch analyze full list-scenarios clean-artifacts check-env

help:
	@echo "Available targets:"
	@echo "  make install          Install the project into .venv"
	@echo "  make serve            Start the FastAPI webhook/media bridge"
	@echo "  make call SCENARIO=appointment_basic"
	@echo "  make suite            Run the full built-in scenario suite"
	@echo "  make fetch            Download Twilio recordings"
	@echo "  make analyze          Generate the markdown bug report"
	@echo "  make full             Run suite, fetch recordings, and analyze"
	@echo "  make list-scenarios   Print available scenario IDs"
	@echo "  make clean-artifacts  Remove generated transcripts, recordings, events, and reports"
	@echo ""
	@echo "Before calling, make sure:"
	@echo "  1. .env is configured"
	@echo "  2. ngrok is forwarding to the same port as the local server"
	@echo "  3. 'make serve' is running in a separate terminal"

install:
	$(PYTHON) -m pip install -e .

check-env:
	@test -f .env || (echo ".env is missing. Copy .env.example to .env and fill in the required values."; exit 1)

serve: check-env
	$(PYTHON) -m $(APP) serve

call: check-env
	@if [ -z "$(SCENARIO)" ]; then echo "Usage: make call SCENARIO=appointment_basic"; exit 1; fi
	$(PYTHON) -m $(APP) call --scenario $(SCENARIO)

suite: check-env
	$(PYTHON) -m $(APP) run-suite

fetch: check-env
	$(PYTHON) -m $(APP) fetch-recordings

analyze: check-env
	$(PYTHON) -m $(APP) analyze

full: suite fetch analyze

list-scenarios:
	$(PYTHON) -m $(APP) list-scenarios

clean-artifacts:
	rm -f artifacts/transcripts/*
	rm -f artifacts/recordings/*
	rm -f artifacts/events/*
	rm -f artifacts/reports/bug_report.md
	rm -f artifacts/calls.jsonl
