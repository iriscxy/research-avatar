.PHONY: setup test validate paper

setup:
	python3 -m pip install -r requirements.lock
	python3 -m playwright install chromium

test:
	python3 -m unittest discover -s tests

validate:
	python3 -m tools.research_buddy_cli validate

paper:
	python3 -m tools.research_buddy_cli paper
