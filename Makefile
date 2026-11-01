PYTHON ?= python3

.PHONY: stage
stage:
	$(PYTHON) scripts/run_stage.py --stage 1 --runs 3
