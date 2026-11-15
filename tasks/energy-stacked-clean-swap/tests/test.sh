#!/bin/bash
mkdir -p /logs/verifier
python3 /tests/grade.py /app/answer.json /tests/expected.json
