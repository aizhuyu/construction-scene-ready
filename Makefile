PYTHON ?= .venv/bin/python
LATEXMK ?= /Library/TeX/texbin/latexmk

.PHONY: test validate validate-faulty export-rules local-pipeline paper title-page clean

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

validate:
	PYTHONPATH=src $(PYTHON) -m construction_scene_ready.cli examples/minimal_scene.json

validate-faulty:
	PYTHONPATH=src $(PYTHON) -m construction_scene_ready.cli examples/faulty_scene.json

export-rules:
	PYTHONPATH=src $(PYTHON) scripts/export_rule_registry.py --output docs/scene-readiness-rules.csv

local-pipeline:
	PYTHONPATH=src $(PYTHON) -m construction_scene_ready.pipeline --output-dir generated/local-pipeline

paper:
	cd paper && $(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error manuscript.tex

title-page:
	cd paper && $(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error title-page.tex

clean:
	cd paper && $(LATEXMK) -C manuscript.tex && $(LATEXMK) -C title-page.tex
