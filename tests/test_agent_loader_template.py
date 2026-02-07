from secret_validator_grunt.loaders.agents import load_agent

AGENT = """---
name: sample
model: custom-model
---
Body before
Report template you must use:
```markdown
# Title
```
"""


def test_load_agent_report_template(tmp_path):
	p = tmp_path / "agent.md"
	p.write_text(AGENT, encoding="utf-8")
	agent = load_agent(p)
	assert agent.report_template.startswith("# Title")
	assert agent.model == "custom-model"
