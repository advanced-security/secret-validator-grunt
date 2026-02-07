"""
Custom agent conversion utilities.

Provides functions for converting internal AgentConfig models
to Copilot SDK CustomAgentConfig typed dicts.
"""

from __future__ import annotations

from copilot import CustomAgentConfig

from secret_validator_grunt.models.agent_config import AgentConfig


def to_custom_agent(agent: AgentConfig) -> CustomAgentConfig:
	"""
	Convert an AgentConfig to a Copilot CustomAgentConfig.

	Maps AgentConfig fields to the SDK's CustomAgentConfig typed dict.
	Prompt corresponds to the agent body and tools lists the allowed
	tool names.

	Parameters:
		agent: The internal agent configuration.

	Returns:
		Copilot SDK compatible custom agent configuration.
	"""
	cfg: CustomAgentConfig = {
	    "name": agent.name,
	    "prompt": agent.prompt,
	    "tools": agent.tools,
	    "infer": True,
	}
	if agent.description:
		cfg["description"] = agent.description
	return cfg


__all__ = ["to_custom_agent"]
