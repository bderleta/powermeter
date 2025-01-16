#!/bin/bash

cwd=$(dirname "$0")
exec $cwd/venv/bin/python3 $cwd/gather.py
