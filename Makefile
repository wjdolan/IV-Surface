PYTHON ?= python
APP ?= main.py

.PHONY: install run

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m streamlit run $(APP)
