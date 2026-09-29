# Copilot code review instructions

When reviewing pull requests in this repository:

- Flag any suppressed lint rule or scanner skip that lacks a reason next to the code.
- Tool authorization must stay in the gateway policy engine (`policy/`), with a matching case in
  `policy/cases.yaml`; the prompt is never a control.
- The agent image must be referenced by digest (`@sha256:`), never by tag, in Terraform and in workflows.
- The AgentCore runtime must stay in VPC mode with no internet gateway, NAT gateway or public subnet.
- Pull request workflows must not request `id-token: write` or read AWS secrets.
- Actions must be pinned by full commit SHA with the version in a comment.
- New Terraform behavior needs an assertion in a `.tftest.hcl` file that runs against the mocked provider.
- New agent behavior needs a scripted scenario in `data/scenarios.yaml` or a unit test that runs offline.
- Only fictional names and AWS documentation example account IDs may appear; no real IDs, ARNs, IPs or emails.
- Verify conventional commit format in PR titles.
