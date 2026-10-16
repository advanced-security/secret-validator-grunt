from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.integrations.custom_agents import to_custom_agent


def test_to_custom_agent_maps_fields():
	agent = AgentConfig(name="foo", description="desc", prompt="body",
	                    tools=["view"])
	cfg = to_custom_agent(agent)
	assert cfg["name"] == agent.name
	assert cfg["prompt"] == agent.prompt
	assert cfg["tools"] == ["view"]
	# Stages pre-select their agent; it must not be inferred/delegated to
	assert cfg["infer"] is False
	assert cfg["description"] == "desc"


def test_to_custom_agent_omits_optional_description():
	agent = AgentConfig(name="foo", prompt="body")
	cfg = to_custom_agent(agent)
	assert "description" not in cfg


def test_to_custom_agent_passes_model():
	"""Per-agent model from frontmatter is forwarded to the SDK."""
	agent = AgentConfig(name="foo", prompt="body", model="gpt-5.3-codex")
	cfg = to_custom_agent(agent)
	assert cfg["model"] == "gpt-5.3-codex"


def test_to_custom_agent_omits_model_when_unset():
	agent = AgentConfig(name="foo", prompt="body")
	cfg = to_custom_agent(agent)
	assert "model" not in cfg


def test_to_custom_agent_omits_tools_when_unset():
	"""Omitted tools leave the agent unrestricted."""
	agent = AgentConfig(name="foo", prompt="body")
	cfg = to_custom_agent(agent)
	assert "tools" not in cfg


def test_to_custom_agent_preserves_empty_tools():
	"""An explicit empty tool list is forwarded, not dropped."""
	agent = AgentConfig(name="foo", prompt="body", tools=[])
	cfg = to_custom_agent(agent)
	assert cfg["tools"] == []


def test_to_custom_agent_does_not_use_sdk_skill_preloading():
	"""Required bodies have one delivery path: the task prompt."""
	agent = AgentConfig(name="foo", prompt="body")
	assert "skills" not in to_custom_agent(agent)
