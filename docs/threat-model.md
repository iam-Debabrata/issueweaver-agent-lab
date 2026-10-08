# Threat model (v0.1)

| Threat | Implemented safeguard | Remaining risk |
|---|---|---|
| Forged webhook | HMAC SHA-256, timing-safe compare | Exposed secret enables spoofing |
| Wrong repository | Exact `GITHUB_REPOSITORY` check | Config misconfiguration |
| Unauthorized modifications | Opt-in label and `GITHUB_ALLOW_PR` | Maintainer credential compromise |
| LLM path traversal | Strict `.py` path allowlist, symlink checks | Unsafe Python files can still harm logic |
| Host code execution | Docker with no network, limits and ro binds | Docker/kernel escapes; insecure socket |
| Infinite repair loop | `MAX_REPAIRS` capped 0..4 | Cost and token budget within each call |
| GitHub duplicate delivery | SQLite primary key | Crash after acknowledgment can lose work |
| Token leakage | Token never passed into runner | Orchestrator host still has token |
| Prompt injection | Untrusted-content framing | LLM guardrail not guaranteed |
| CI sabotage | Writes to `.github/` refused | Generated Python tests may be misleading |

Use a disposable **private test-target repo**, a minimally scoped fine-grained token, and a
separate worker VM. Never point the service at sensitive production code without safeguards.
