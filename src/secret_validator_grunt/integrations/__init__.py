"""External service integrations.

This subpackage provides integration with external services
and APIs used by the secret validator.

Key modules:
    - github: GitHub Secret Scanning API client
    - copilot_tools: Copilot SDK tool definitions
    - custom_agents: Agent conversion utilities
"""

from secret_validator_grunt.integrations.github import (
    get_github_client,
    get_alert,
    list_alert_locations,
    DEFAULT_UA,
)
from secret_validator_grunt.integrations.copilot_tools import (
    get_session_tools,
    secret_scanning_alert_tool,
    secret_scanning_alert_locations_tool,
)
from secret_validator_grunt.integrations.custom_agents import to_custom_agent

__all__ = [
    # github
    "get_github_client",
    "get_alert",
    "list_alert_locations",
    "DEFAULT_UA",
    # copilot_tools
    "get_session_tools",
    "secret_scanning_alert_tool",
    "secret_scanning_alert_locations_tool",
    # custom_agents
    "to_custom_agent",
]
