#!/bin/bash

pip install ruff --upgrade

ruff check --fix --preview apps
ruff format --preview apps
ruff check --fix --preview *.py
ruff format --preview *.py
ruff check --fix --preview assets
ruff format --preview assets
