PYTHON ?= python3

.PHONY: stage rq1 reproduce test
stage:
	$(PYTHON) scripts/run_stage.py --stage 1 --runs 3

rq1:
	$(PYTHON) scripts/run_stage.py --analysis rq1 --runs 3

reproduce:
	$(PYTHON) scripts/run_stage.py --analysis all --runs 3

test:
	$(PYTHON) -m unittest discover -s tests -v

.PHONY: repairs
repairs:
	$(PYTHON) scripts/run_repair_size.py
