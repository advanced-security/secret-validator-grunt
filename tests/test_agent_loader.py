from secret_validator_grunt.loaders.agents import load_agent
from secret_validator_grunt.loaders.frontmatter import split_frontmatter
from secret_validator_grunt.models.agent_config import AgentConfig

SAMPLE = """---
name: test-agent
argument-hint: hint
tools: ["t1", "t2"]
model: gpt-4.1
---
Body here
"""


def test_split_frontmatter():
	"""Test YAML frontmatter extraction from markdown."""
	meta, body = split_frontmatter(SAMPLE)
	assert meta["name"] == "test-agent"
	assert meta["argument-hint"] == "hint"
	assert body.strip() == "Body here"


def test_load_agent(tmp_path):
	"""Test loading agent config from markdown file."""
	p = tmp_path / "agent.md"
	p.write_text(SAMPLE, encoding="utf-8")
	agent = load_agent(p)
	assert isinstance(agent, AgentConfig)
	assert agent.argument_hint == "hint"
	assert agent.tools == ["t1", "t2"]
