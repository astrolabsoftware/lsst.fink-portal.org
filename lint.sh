#!/bin/bash

ruff check --fix --preview apps
ruff format --preview apps
