#!/bin/bash

ruff check --fix --preview apps
ruff format --preview apps
ruff check --fix --preview *.py
ruff format --preview *.py
