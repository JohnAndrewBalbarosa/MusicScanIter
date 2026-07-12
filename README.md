# MusicScanIter

## Overview

Python CLI tool that scans music library, suggests metadata via Gemini AI, writes tags, and organizes files into target folder structures.

Repository: [JohnAndrewBalbarosa/MusicScanIter](https://github.com/JohnAndrewBalbarosa/MusicScanIter)

## Problem and Goal

**Problem.** Large music libraries accumulate inconsistent tags, filenames, and folder structures that are costly to repair track by track.

**Goal.** Scan a source library, suggest metadata with Gemini, let the user review changes, write tags, and organize copies into a target structure.

## System Design

- `main.py`: CLI entry point and run coordination.
- `music_metadata/`: scanning, metadata inference, tag writing, and file organization modules.
- `.env.example`: external model configuration; `docs/`: workflow guidance.

## Setup and Usage

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python main.py --help
```

## Evaluation Method

- Define the project task and expected behavior.
- Run representative examples or user flows.
- Record correctness, speed, reliability, usability, and failure cases.

## Results

- No validated quantitative results are published yet.
- Current README status: implementation and usage are documented before formal measurement.

## Interpretation

- The project can be described as implemented or in progress, but impact claims should stay limited until measurements are collected.
- Use the evaluation plan below to turn the project into resume-ready, evidence-backed work.

## Limitations

- Results should only be treated as validated when this README includes the dataset, sample size, metric definition, and reproduction steps.
- Any AI-generated, OCR-based, scraped, or heuristic output requires manual review before being used as ground truth.
- Environment-dependent measurements such as latency, memory use, browser behavior, and API reliability should be re-measured on the target machine.

## Recommendations and Future Work

- Number of files scanned.
- Metadata suggestion acceptance rate.
- Tag-write success rate.
- Organization accuracy after file moves.

## Documentation Standard

This README follows a technical-project structure: overview, goal, system design, setup, evaluation method, results, interpretation, limitations, and recommendations. Update the Results section whenever new measurements are available so project claims stay evidence-backed.
