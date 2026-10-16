"""
Custom agent conversion utilities.

Provides functions for converting internal AgentConfig models
to Copilot SDK CustomAgentConfig typed dicts.
"""

from __future__ import annotations

from copilot.session import CustomAgentConfig

from secret_validator_grunt.models.agent_config import AgentConfig


def to_custom_agent(agent: AgentConfig) -> CustomAgentConfig:
	"""
	Convert an AgentConfig to a Copilot CustomAgentConfig.

	Maps AgentConfig fields to the SDK's CustomAgentConfig typed dict.
	Prompt corresponds to the agent body and tools lists the allowed
	tool names. The agent's model (if set) is forwarded so the runtime
	uses it while this agent runs.

	``infer`` is False: each stage pre-selects its agent explicitly,
	so the model must not delegate to it (or to itself) as a
	sub-agent via the ``task`` tool.

	Parameters:
		agent: The internal agent configuration.

	Returns:
		Copilot SDK compatible custom agent configuration.
	"""
	cfg: CustomAgentConfig = {
	    "name": agent.name,
	    "prompt": agent.prompt,
	    "infer": False,
	}
	if agent.tools is not None:
		cfg["tools"] = agent.tools
	if agent.description:
		cfg["description"] = agent.description
	if agent.model:
		cfg["model"] = agent.model
	return cfg


__all__ = ["to_custom_agent"]
