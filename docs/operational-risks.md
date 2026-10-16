# Operational risks

This app can use real credentials to make real requests. Only run it when you
have permission to access the alert, process the secret, and test the provider
account. Access to a repository does not grant permission to test every service
referenced in its code.

The precautions below are operating guidance, not guarantees enforced by the app.

## Production changes and data loss

**Testing a secret can change or destroy production data.** An agent may find
an endpoint in the repository and use it to test a token. If that endpoint
accepts `DELETE` requests, the test could delete a real production resource.
Other requests could change settings, send messages, revoke access, or incur
charges. A challenger may repeat the same request.

An endpoint used by the application is not necessarily a safe authentication
check. Separate workspaces and file locks protect local evidence; they do not
prevent changes to remote systems.

Use test accounts for development. Before testing a production credential, agree
on the allowed checks with the account owner. Use documented operations that
verify identity or access without changing data. Check the operation's behavior,
not just its HTTP method. If there is no safe check, leave validation inconclusive
rather than replaying a destructive operation to prove that the token works.

## Other risks

- **Access to the host.** Tool permission requests are approved automatically.
  Agents can run commands with the host user's access. Use a disposable,
  isolated environment without unrelated credentials or files.
- **Sensitive output.** Secrets and code can appear in model prompts, scripts,
  logs, reports, and backups. Do not assume they are all redacted. Restrict access,
  review the model service's data policy, and redact output before sharing it.
- **Misleading instructions in content.** Repository files, alert text, and web
  pages can steer an agent toward unsafe actions or wrong conclusions. Treat
  them as evidence, not trusted instructions. Review consequential actions.
- **Incomplete or outdated facts.** Locations may be missing, history may be
  shallow, and credentials can change after a check. Confirm that the evidence
  covers the alert and is recent enough for the decision.
- **Agents agreeing on a mistake.** Analysts, challengers, and the judge can
  share incorrect assumptions. Agreement and report checks do not prove
  correctness. Review the underlying evidence before acting.
- **Cost and repeated requests.** Parallel agents and reruns consume resources
  and can trigger provider limits. Start with low concurrency. Stopping a run
  does not undo requests already sent or guarantee that every subprocess stopped.
- **Untrusted tools and dependencies.** Guides, validators, generated scripts,
  and installed packages can execute code with the runner's access. Review their
  sources and avoid unnecessary installs or repository setup commands.

## What the built-in controls cover

Challengers use separate working copies. Original scripts, logs, artifacts, and
reports are made read-only and checked for changes afterward. This helps prevent
accidental overwrites; it is not a sandbox against a process running as the same
OS user. The default judge reviews supplied reports without calling providers.

Required guidance is supplied to agents, but delivery does not prove that an
agent followed it or chose a safe test.
