# Security Guidelines for AI Model Discovery

## Threat Model & Security Principles

Automating the discovery of third-party models introduces specific security considerations. CAT strictly enforces defensive measures to maintain isolation, confidentiality, and integrity.

---

## 1. Zero Remote Code Execution (No Eval / Exec)

Discovery endpoints MUST NEVER execute untrusted code:
- **Strict Deserialization**: All incoming data from `/models` endpoints is parsed strictly via `json.loads` or `requests.Response.json()`.
- **No Deserialization of Binary Formats**: Pickles, YAML with custom constructors, or unsafe object graphs are rejected.
- **Pure Data Schema**: Model metadata is restricted to declarative data structures (`ModelInfo`).

---

## 2. Credential Hygiene and Secret Protection

- **No Secret Logging**: API keys and authorization tokens are strictly prohibited from appearing in:
  - CLI logs or stdout/stderr.
  - Exception tracebacks.
  - Model metadata files (`models.json`, `discovery_state.json`).
  - Terminal or browser UIs.
- **Masking**: In diagnostic views, keys are displayed only as `sk-...abcd` with the middle 90% truncated.
- **Process Isolation**: API keys in memory are only supplied to outbound HTTPS headers and never saved alongside catalog definitions.

---

## 3. URL and Scheme Sanitization (SSRF Prevention)

- **Scheme Validation**: Outbound discovery is strictly restricted to `https://` (or `http://localhost` / `http://127.0.0.1` for local inference daemons like Ollama).
- **Prohibited Schemes**: Protocols such as `file://`, `ftp://`, `gopher://`, or cloud metadata endpoints (`http://169.254.169.254`) are immediately rejected by Stage 4 of the `ModelValidator`.
- **Redirect Limits**: Network requests enforce strict redirect limits (`allow_redirects=False` or maximum 3 hops) to prevent SSRF chaining.

---

## 4. Resource Exhaustion and DoS Mitigation

- **Bounded Execution**: Network discovery calls have mandatory timeouts:
  - Default: `6.0` seconds.
  - Maximum cap: `10.0` seconds.
- **Parallel Workers Limit**: Thread-pool workers for discovery are capped at 8 concurrent threads to prevent resource starvation.
- **Catalog Size Clamps**: If a remote provider returns an unreasonable number of models (e.g. >10,000 spam entries), CAT clamps ingestion to the top 250 models per provider.

---

## 5. Offline Integrity & Data Tampering

- **Non-Destructive Failures**: Network failures or corrupt responses from a provider will never delete existing models from the local registry.
- **Atomic File Swapping**: Model metadata files are written to `.tmp` files and swapped atomically using `os.replace` to prevent file corruption during abrupt shutdowns.
