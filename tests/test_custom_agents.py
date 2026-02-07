from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.integrations.custom_agents import to_custom_agent


def test_to_custom_agent_maps_fields():
	agent = AgentConfig(name="foo", description="desc", prompt="body")
	cfg = to_custom_agent(agent)
	assert cfg["name"] == agent.name
	assert cfg["prompt"] == agent.prompt
	assert cfg["tools"] == agent.tools
	assert cfg["infer"] is True
	assert cfg["description"] == "desc"


def test_to_custom_agent_omits_optional_description():
	agent = AgentConfig(name="foo", prompt="body")
	cfg = to_custom_agent(agent)
	assert "description" not in cfg
