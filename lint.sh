#!/bin/bash

ruff check --fix --preview apps
ruff format --preview apps
ruff check --statistics --preview *.py
ruff format --check --preview *.py
