#!/bin/bash

ruff check --fix *.py
ruff format *.py
ruff check --fix apps
ruff format apps
#ruff check --preview --fix --ignore D205 tests
#ruff format --preview tests
