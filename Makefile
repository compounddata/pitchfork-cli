#!/usr/bin/env make

VENV = $(CURDIR)/venv
VENV_CMD = virtualenv-3
PIP = $(CURDIR)/venv/bin/pip

default: $(VENV)

$(VENV):
	$(VENV_CMD) $@
	$(PIP) install file://$(CURDIR)

clean:
	rm -rf $(VENV)
