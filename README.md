# secret-validator-grunt

![Secret Validator Grunt](./assets/repo_header.png)

Agentic framework for automated validation of GitHub Secret Scanning alerts using Copilot SDK.

## Overview

This app addresses the challenge of efficiently triaging and validating secret scanning alerts at scale. It orchestrates a three-stage pipeline — concurrent analysis sessions, adversarial challenge validation, and LLM-as-judge selection — to produce structured reports with confidence scoring.

### Key Features

- **Concurrent Analysis**: Run multiple validation agents in parallel, each with an independent workspace
- **Adversarial Challenge**: Each report is independently challenged by an adversarial agent
- **LLM Judge**: Automatically selects the most complete and accurate analysis, informed by challenge results
- **Skills-Based Methodology**: Phase organized skills define the validation methodology - agents load them on-demand
- **GitHub Integration**: Fetches alert details and repository context via GitHub APIs

## Requirements

- Python 3.11+
- [Copilot CLI](https://github.com/github/copilot-cli)
- [Copilot SDK](https://github.com/github/copilot-sdk)
- GitHub token

## Setup

```bash
uv venv
uv sync --extra dev
cp .env.example .env  # configure your environment
```

## Usage

```bash
uv run secret-validator-grunt run org/repo alert_id
```

Options:
- `--analyses N` — Number of concurrent analyses (default: 3)
- `--show-usage` — Enable diagnostics display and persistence
- `--timeout N` — Per-analysis timeout in seconds (default: 1800)
- `--judge-timeout N` — Judge session timeout in seconds (default: 300)
- `--stream-verbose` — Stream raw deltas to console

Reports by default are saved to `analysis/<org>/<repo>/<alert_id>/`

## Pipeline

```
CLI -> pre_clone_repo -> N × analysis (concurrent) -> N × challenge (concurrent) -> judge -> final report
```

1. Each analysis agent independently researches the secret, writes verification scripts, and produces a structured report.
2. An adversarial challenger validates each report by inspecting the workspace.
3. A judge agent compares all reports with challenge annotations and selects the winner.

## Development

```bash
uv run pytest          # run tests
uv run yapf -ir src    # format code
```

## License

This project is licensed under the terms of the MIT open source license. Please refer to the [LICENSE](./LICENSE) file for the full terms.
