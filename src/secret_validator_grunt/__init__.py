"""
Secret Validator Grunt - Agentic validation of GitHub Secret Scanning alerts.

This package provides an agentic framework for automated validation of
secret scanning alerts using the Copilot SDK.

Main entry points:
    - secret_validator_grunt.main: CLI entrypoint
    - secret_validator_grunt.core.runner: run_all() for batch validation
    - secret_validator_grunt.models.config: Config and load_env()
"""