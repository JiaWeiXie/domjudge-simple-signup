SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:

MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

COMMA := ,

PROJECT_NAME := $(shell echo $(notdir $(CURDIR)) | sed -e 's/_/-/g')
PYTHON_IMAGE_VERSION := $(shell cat .python-version)

CURRENT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD  | sed -e 's/_/-/g; s/\//-/g')
CURRENT_VERSION := $(shell git rev-parse --short HEAD)

install: poetry install
.PHONY: install

venv: poetry shell
.PHONY: venv

lint:  ## Check lint
	isort --check --diff .
	black --check --diff .
.PHONY: lint

lint-fix: ## Fix lint
	isort .
	black .
.PHONY: lint-fix

clean:  ## Clean cache files
	find . -name '__pycache__' -type d | xargs rm -rvf
.PHONY: clean

run:  ## Run dev server
	poetry run streamlit run src/main.py
.PHONY: run

.DEFAULT_GOAL := help
help: Makefile
	@grep -E '(^[a-zA-Z_-]+:.*?##.*$$)|(^##)' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\[32m##/[33m/'
.PHONY: help
