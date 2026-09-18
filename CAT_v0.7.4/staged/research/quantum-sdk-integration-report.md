# Integrating Qiskit, Cirq, and PennyLane into CAT

## A Capability-Bus Architecture Proposal Grounded in the 2026 SDK Landscape

## Core Conclusion

CAT already has the architectural primitive it needs for quantum: the capability bus defined in §4 of the master evolution spec. Quantum software development kits (Qiskit, Cirq, PennyLane) should enter CAT as **adapters under that bus**, not as a new mode, not as direct tool implementations, and not as native CAT extensions. The real work in 2026 is in three places: (1) modeling quantum semantics faithfully — circuits, primitives, jobs, results, hardware backends — without collapsing them into generic Python or shell tools; (2) enforcing real-execution verification per §8 and §86, so that "I ran a Bell state on IBM" never becomes a model-text assertion but a runtime event tied to a job ID returned by the provider; and (3) sequencing a rollout that begins with simulators CAT can actually prove, then layers in real quantum hardware one provider at a time. The two capabilities CAT already has — the `/bloch` Born-rule renderer and the `bloch_sphere` agent tool — are the smallest honest quantum surface CAT can ship today, and they should stay; everything else should be added behind the same registry schema already used by 296 other capabilities [15].

This report is written for the CAT platform architect. It assumes the reader is fluent in the §1–§106 architecture and is deciding where quantum lives inside that architecture, not whether to add it.

## State of the Quantum SDK Landscape (Late 2026)

Qiskit, Cirq, and PennyLane are all actively maintained under Apache 2.0, but they have diverged sharply in scope and lifecycle position. Qiskit 2.5.2 (released 13 August 2026) is the dominant general-purpose SDK; it requires Python 3.10–3.13 [1][2]. Its companion simulator `qiskit-aer` is on 0.17.1, with separate wheels `qiskit-aer-gpu` (Linux x86_64, CUDA ≥11.2) and a newer `qiskit-aer-gpu-rocm` AMD build on ROCm 7.2 [11]. Cirq 1.7.0 (released 30 June 2026) requires Python 3.11+; importantly, the `cirq-rigetti` sub-package was removed in v1.6.0 — a concrete reminder that single-vendor integrations rot and that CAT's adapters must wrap, not import directly [3]. PennyLane 0.45.1 (released 26 June 2026) just dropped Python 3.10 and, as of late July 2026, requires Python 3.12+ and NumPy 2.0+ [4][5][6]. Its `import pennylane as qp` alias introduced in March 2026 reframes the library as a general quantum platform rather than purely a quantum-machine-learning layer [4].

This sets a real constraint: any CAT environment intended to host all three SDKs natively must run Python 3.12+, and any environment still on 3.10 is restricted to Qiskit (with no Cirq and no PennyLane 0.45+). The environment-detection layer CAT needs for quantum is therefore finer-grained than "is Python installed?" — it must report SDK presence, version, supported Python range, and known incompatibilities per §57 of the spec.

The second meaningful change is the move to **MCP-based access** to quantum resources. IBM's own `Qiskit/mcp-servers` repository now hosts five official Model Context Protocol servers covering circuit creation, transpilation, serialization (OpenQASM 3, QPY), backend analysis, hardware execution, and documentation search; the current release is v0.12.0 on 13 July 2026 [8]. Conductor Quantum's CODA MCP exposes IBM, IonQ, Rigetti, IQM, and AQT hardware (more than 1,000 qubits total) with cross-framework transpilation across Qiskit, Cirq, PennyLane, Braket, and CUDA-Q through a single interface [10]. A Waseda University team published an MCP server for the ABCI-Q hybrid quantum-HPC environment in April 2026, demonstrating natural-language → OpenQASM → CUDA-Q → Quantinuum-emulator workflows via MCP tools named `sampler_qasm_cudaq` and `estimator_qasm_cudaq` [9]. A July 2026 survey of the quantum-MCP landscape catalogues the field into five areas: circuit design and execution (IBM Qiskit, Conductor CODA, Amazon Braket), simulation and noise modelling, quantum machine learning (QML-MCP, Psi-MCP), hardware design (qsim-mcp for Qiskit Metal), and post-quantum cryptography [13].

CAT should treat MCP not as an alternative to its own capability bus, but as a *transport-layer* the bus can talk to. A "submit to IBM Quantum" capability can dispatch through CAT's secrets, verification, and event bus while delegating the protocol-level dialogue to an MCP server — this is the §47 compute-fabric principle applied at the quantum layer.

## CAT's Existing Quantum Surface

CAT v0.7.4 already has two quantum affordances and nothing else quantum-native. First, a `/bloch [theta] [phi]` command renders an exact Born-rule Bloch sphere from polar and azimuthal angles; the v0.6.13 changelog confirms it is a closed-form computation, not a simulation, which is the strongest verification posture possible for a quantum visualisation [CAT internal: CHANGELOG_v0.6.13_bloch_sphere.md]. Second, the `bloch_sphere` tool exists in the agent tool layer and is wired through `calc_terminal/agent.py` [CAT internal: CHANGELOG_v0.7.0_quantum_ide.md]. Third, the `cat_capability_registry.json` already records quantum-related entries among its 296 capabilities, 37 tools, 86 commands, 6 modes, 10 permissions, 2 extensions, and 155 providers [15].

That is the entire quantum surface today. A grep for `import qiskit`, `from cirq`, or `import pennylane` across the CAT v0.7.4 source tree returns nothing. So CAT's quantum story is currently: a deterministic renderer and one visualisation tool, both kept honest by being pure math, both waiting for a capability-bus integration that the existing schema already permits.

CAT's own `ARCHITECTURE_REVIEW_v0.7.4.md` (audited 31 July 2026) defines a five-phase migration roadmap that is unusually well aligned with this work. Phase 4 is "Plugin architecture", and the review explicitly names "remote/cloud/HPC execution backends as transport plugins" as a later target [CAT internal: ARCHITECTURE_REVIEW_v0.7.4.md, §"Phase 4"]. Quantum SDK adapters are exactly such transport plugins. The same review flags G7 ("No plugin architecture") as a critical gap; the right way to close G7 is to make the first real plugin a quantum adapter — small enough to ship without rewriting the core, large enough to prove the mechanism.

## The Capability-as-Adapter Pattern

The §4 capability schema requires every capability to carry: name, version, implementation, availability status, authentication requirements, permissions, input/output/error schemas, environment requirements, health check, version compatibility, documentation, and provenance. Quantum adapters must populate every field, not just the name and version. Three structural decisions drive the rest of the architecture:

**First, quantum adapters are not Python-execute adapters.** They cannot be implemented as `python.execute("from qiskit import …")`. The reason is not style but verification: a generic Python adapter cannot return a structured job ID, cannot distinguish "the Qiskit call returned" from "the circuit actually executed on hardware", and cannot record provenance per §96. Quantum adapters are first-class capability implementations that take a circuit-description payload (OpenQASM 3.0 or one of the SDK-native circuit-IR serialisations), produce a job record (provider, backend, job ID, submitted-at, shots, transpilation parameters), and yield a result record (counts, expectation values, calibration metadata, execution duration, queue position). This mirrors what the IBM and Conductor MCP servers already expose as `tools` [8][10].

**Second, modes do not own quantum adapters.** §56 of the spec is explicit and correct: a Research mode must not own a private Jupyter implementation, and likewise no QuantumResearch mode should own a private Qiskit wrapper. Quantum adapters live on the capability bus. Any mode with appropriate permission — `BioLab`, `MLTrainer`, `QuantumResearch`, or even the default `Notebook` mode — may request a circuit execution capability. This preserves the §82 data-consistency principle and avoids the regression of having six near-duplicate SDK wrappers.

**Third, verification is a capability, not an afterthought.** §8 and §86 of the spec are absolute. A capability that claims "ran a Bell state on IBM" must produce, in addition to counts, a verifiable record: the exact transpiled OpenQASM submitted, the job ID returned by IBM, the retrieval timestamp, and the post-selection rules. Where the same circuit can also be run on a simulator baseline, the verification engine must compare distributions and surface disagreement rather than silently average it. Bell states (Φ⁺ = (|00⟩+|11⟩)/√2) and GHZ states (|0…0⟩+|1…1⟩)/√2 are the canonical regression circuits for this purpose: their ideal distributions are closed-form, and small deviations are easy to interpret as either hardware noise (acceptable, expected on real QPUs) or adapter bugs (unacceptable, must fail verification).

## Per-SDK Mapping

The table below sketches the minimum viable adapter surface for each SDK as of late 2026. It is intentionally compact; production adapters will need many more input/output fields, but the rows identify the boundaries CAT must enforce.

| SDK | Primary capability name | Minimum input | Minimum output | Required Python | Default simulator | Verification hook |
|---|---|---|---|---|---|---|
| Qiskit | `qiskit.run_circuit` | OpenQASM 3.0 string or QPY bytes, shots, optional backend | counts, job ID, transpiled QASM | 3.10–3.13 | `qiskit-aer` 0.17.1 (CPU), `qiskit-aer-gpu` (CUDA Linux), `qiskit-aer-gpu-rocm` (AMD Linux) | Bell/GHZ simulator baseline + provider job-record retrieval |
| Qiskit IBM | `qiskit.ibm.submit` | QPY circuit, backend name, shots, runtime options | job ID, queue position, final result | 3.10–3.13 | n/a (hardware only) | Real-job retrieval via `service.job(job_id).result()` |
| Cirq | `cirq.run_circuit` | Cirq Circuit serialised via JSON or `cirq.to_json` | measurement results, simulator name | 3.11+ | `cirq.DensityMatrixSimulator`, new `willow_pink` QVM | Cirq-vs-Qiskit Bell-state cross-check on identical input |
| Cirq hardware | `cirq.google.submit` | same | Cirq `Result` with device metadata | 3.11+ | n/a | Google Cloud collaboration-only path; explicitly mark "research access only" |
| PennyLane | `pennylane.run_qnode` | QNode specification (device, observables, shots) | expectation values, samples | 3.12+ | `default.qubit`, `lightning.qubit`, `lightning.gpu`, `lightning.kokkos`, `lightning.amdgpu`, `lightning.tensor` | Differentiation cross-check: parameter-shift vs. adjoint-Jacobian |
| PennyLane Catalyst | `pennylane.run_qjit` | `@qjit`-compiled hybrid program | compiled MLIR artefacts + results | 3.12+ | `lightning.qubit` with `qjit(capture=True)` | Round-trip import: compiled artefact replayed as raw QNode |

The PennyLane rows call out `lightning.amdgpu` deliberately. The March 2026 PennyLane/Rolls-Royce/AMD demonstration showed a 20× speedup on MI300X for QSVT workflows and the ability to compile and execute a 256×256 CFD mesh model on 20 qubits with 35 million gates in under two hours [PennyLane blog, March 2026]. That is enough scale to justify making CAT's compute-fabric layer (§47, §53) aware of GPU choices beyond CUDA, which is consistent with the AMD-backed ROCm extension of `qiskit-aer` [11]. Treating both CUDA and ROCm as first-class GPU backends is consistent with CAT's hardware-agnostic posture and avoids a CUDA-only bias that would lock out AMD workstations and Frontier-class systems.

## Verification: Proving Real Quantum Ran

This is the section that decides whether the feature is real. §86 of the master spec is unambiguous: if CAT cannot perform an operation it must report "NOT AVAILABLE"; if execution failed it must report "EXECUTION FAILED"; if a result was not verified it must report "NOT VERIFIED". Never turn failure into a success message. Quantum results are uniquely susceptible to silent misrepresentation — models can produce plausible-looking histograms from invented numbers, and real quantum hardware produces distributions that diverge from theory due to noise in ways easy to misread as bugs.

The verification engine for quantum needs four checks, in order of cost.

**Check 1 — Schema and presence.** The capability must return all mandatory fields from the table above. Any missing field is an automatic `EXECUTION FAILED` with the schema violation named.

**Check 2 — Simulator baseline.** For circuits of small enough width (say, up to 20 qubits or whatever the available simulator can handle in under ten seconds), CAT must run the same circuit on a local simulator and compare distributions. This catches adapter bugs — wrong transpilation, wrong measurement basis, wrong shot normalisation. PennyLane's `lightning.qubit` is fast enough for routine use; Qiskit's `qiskit-aer` is the alternative when only OpenQASM is available.

**Check 3 — Provider job retrieval.** For hardware runs, CAT must call the provider's job-retrieval API (IBM's `service.job(job_id).result()`, AWS Braket's `AwsQuantumTask`, Azure Quantum's job API, etc.) at least once after the job's claimed completion. The retrieved status, results, and metadata must match what the adapter stored. This protects against adapters that fabricate job IDs.

**Check 4 — Theoretical comparison.** For canonical circuits (Bell, GHZ, Deutsch–Jozsa, simple VQE ansätze), CAT keeps reference distributions. Real-hardware results must fall within a confidence interval derived from reported readout error rates; failing the test marks the run as `NOT VERIFIED — distribution outside expected envelope`.

The status model should expose all four checks individually, not collapse to a single boolean. A user seeing "Simulator ✓, Provider retrieval ✓, Theoretical envelope ✗" understands the situation is "real hardware ran and we got its data back, but the result looks unlike what theory predicts" — which is honest, actionable, and matches the spec's NO-FAKE-CAPABILITY rule.

## Environment and Dependency Constraints

Three SDKs in one environment is a real packaging problem. CAT's existing eventbus topics should publish an `EnvironmentAudit` event whenever a quantum capability is requested, and the audit must report at minimum: Python version, `qiskit` version and Python-range support, `qiskit-aer` version and GPU backend, `qiskit-ibm-runtime` version, `cirq` version and Python-range support, `pennylane` version and Python-range support, `pennylane-lightning` device availability, `pennylane-catalyst` version, and NumPy version (because PennyLane 0.45+ requires NumPy 2.0+). Per §34 of the spec, CAT detects but does not silently change these.

The realistic deployment posture is two virtualenvs at most: one with Qiskit + Aer on Python 3.11 (broadest compatibility for production users), and one with all three SDKs on Python 3.12 (for advanced users and PennyLane Catalyst work). Trying to keep a single Python install working with every SDK version will fail because PennyLane's mid-2026 jump from 3.11 to 3.12 collides with environments that still hold older Qiskit builds.

GPU detection should follow the same posture: query for CUDA and ROCm separately, report both, do not pretend either exists when it does not. CAT's `EnvironmentAudit` event should emit the raw `nvidia-smi` and `rocm-smi` exit codes alongside the human-readable summary so the §85 verify pipeline can audit the audit.

## Authentication and Secrets

Hardware access requires provider credentials. As of late 2026, the relevant patterns are: IBM's `IBMProvider.save_account(token=…, overwrite=True)` storing into `~/.qiskit/qiskit-ibm.json`; AWS Braket's boto3-style credential chain; Azure Quantum's `azure-quantum` workspace tokens; Google Quantum AI's invitation-only research access (no self-serve token path); and PennyLane device plugins pulling per-backend tokens (most require the underlying vendor's auth). Conductor CODA requires a `coda-account`-issued API token [10].

CAT's §27 secrets manager must own all of these. Adapters should never receive raw tokens; they should request a scoped credential handle from the secrets layer, and the secrets layer should redact the value from every log, chat transcript, and Live Activity panel per §27. The verification event must record only that authentication succeeded, never the token itself.

Pricing-aware UX belongs here too. AWS Braket charges per-shot and per-task on a per-device basis — IonQ Forte at roughly $0.08/shot plus $0.30/task, Rigetti Cepheus-1-108Q at $0.000425/shot, IQM Garnet at $0.00145/shot as of late 2026 [12]. IBM's Open Plan provides ten minutes of runtime per rolling 28-day window, which is the right ceiling to surface to a user before submitting a 1,000-shot, 50-layer circuit. CAT should refuse to submit a job whose estimated cost exceeds a configurable per-workspace ceiling and surface the refusal as a human-approval event per §24.

## Phased Rollout

Three phases align with the natural verification postures and with CAT's own Phase 0–4 roadmap.

**Phase Q1 (verify posture).** Ship only the simulator adapters: `qiskit.run_circuit`, `cirq.run_circuit`, `pennylane.run_qnode`, plus the existing `/bloch` and `bloch_sphere` tools. Verification checks 1–2 are mandatory; checks 3–4 are placeholders. This delivers a usable quantum surface today — circuits, counts, expectation values, Bloch visualisation — and proves CAT's capability-as-adapter pattern with the smallest possible external dependency.

**Phase Q2 (hardware path).** Add `qiskit.ibm.submit` and `aws_braket.submit` against the providers that have self-serve access and meaningful free or low-cost tiers (IBM Open Plan, AWS Braket on-demand). Verification check 3 becomes mandatory. PennyLane's QML differentiation cross-check lands here. The CAPEX of hardware integration is real, so this phase should be merged into CAT's Phase 4 plugin-architecture work — quantum adapters become the first concrete plugin type, the de-facto reference implementation.

**Phase Q3 (research-tier and QML).** Add Google Cirq device access (research collaboration only), PennyLane Catalyst with `qjit(capture=True)`, and the more advanced backends (Rigetti via AWS Braket, IonQ via AWS Braket or Azure, QuEra neutral-atom via AWS Braket). Verification check 4 becomes mandatory for canonical circuits. Cross-framework transpilation enters via CODA MCP, exposing a single `quantum.run` capability that fans out to whichever adapter best fits the circuit — at the cost of a paid CODA token and a clear licensing disclosure.

## Risks and "What Not To Do"

A small number of architectural temptations will produce a fake-quantum surface if not actively resisted.

Do not create a `quantum` mode. §56 of the spec, the existing five-mode architecture, and the failure of single-SDK wrappers all point the same way. Quantum work belongs across modes that need it, behind the capability bus.

Do not let adapters swallow untrusted circuit text. §26 (prompt-injection defence) applies to circuit payloads: an OpenQASM string from a web page or a README is *untrusted input*, not a user instruction. CAT should parse and validate, never execute as code, and should reject circuits with suspicious patterns (e.g., file-system-touching imports, hard-coded absolute paths, classic prompt-injection tokens like "ignore previous instructions" embedded in comments).

Do not advertise PennyLane as a general-purpose quantum simulator — it is the right choice for quantum-machine-learning and hybrid-classical workflows but the wrong default for circuit-first development. Likewise, do not advertise Qiskit as a QML platform. The adapters expose the right tool for the right job; the planner picks.

Do not silently fall back from real hardware to simulator on failure. A user requesting IBM execution who is rerouted to `qiskit-aer` without an explicit consent event has been lied to. The failure must surface, the user must approve any fallback, and the event must record the substitution.

Do not invent cryptography around quantum. §74 is correct: use established primitives. The MCP servers themselves are an emerging attack surface — the MCP-for-quantum paper [9] explicitly warns about context injection via compromised MCP responses, and a recent security analysis of MCP deployments notes that long-lived stateful connections complicate standard WAF-based defences. CAT's secrets manager must treat any MCP-returned circuit or calibration blob as untrusted data subject to the §26 injection rules.

## Concrete Next Steps

Three actions are sufficient to move from this architecture document to running code, all consistent with CAT's Phase 0–4 plan.

First, complete Phase 0 (truth and hygiene) and Phase 1 (composition root) from `ARCHITECTURE_REVIEW_v0.7.4.md`. Without those, quantum adapters cannot be cleanly tested or registered. The dependency arrow in CAT's existing layout — `ui → backend → leaf utilities` — already accommodates new `calc_terminal/quantum/` leaf modules.

Second, define one Python 3.12 environment with Qiskit 2.5.x, Cirq 1.7.x, PennyLane 0.45.x, `qiskit-aer` 0.17.x, and `pennylane-lightning` (qubit, gpu, kokkos, amdgpu, tensor devices) as a CI target. Use `pennylane-catalyst` only on Linux x86_64 and ARM64 — Mac x86 is explicitly dropped in Catalyst 0.15.0. The CAT self-test (§33) should include a quantum-block that reports the EnvironmentAudit and refuses to mark "Quantum available" unless the schema is fully populated.

Third, implement the three Phase Q1 adapters (`qiskit.run_circuit`, `cirq.run_circuit`, `pennylane.run_qnode`) plus the four-check verification pipeline. Halve the surface to ship in a week; prove the pattern. Real hardware adapters (Phase Q2) ship after CAT's Phase 4 plugin architecture lands, with quantum adapters as the first concrete plugin type.

The smallest honest quantum surface CAT can ship today is the two capabilities it already has plus three new simulator-backed adapters with the verification pipeline above. That is enough to give BioLab, MLTrainer, QuantumResearch, and any future custom mode real, verifiable quantum computation without any new mode and without any fake integration. Everything else is sequencing.

---

## References

[1] Qiskit releases, GitHub. <https://github.com/Qiskit/qiskit/releases>
[2] qiskit on PyPI (Python version constraint). <https://pypi.org/project/qiskit/>
[3] Cirq releases, GitHub. <https://github.com/quantumlib/Cirq/releases>
[4] PennyLane installation guide. <https://docs.pennylane.ai/en/stable/development/guide/installation.html>
[5] pennylane on PyPI. <https://pypi.org/project/pennylane/>
[6] PennyLane source repository, GitHub. <https://github.com/PennyLaneAI/pennylane>
[7] PennyLane-Lightning releases, GitHub. <https://github.com/PennyLaneAI/pennylane-lightning/releases>
[8] Qiskit Model Context Protocol servers, GitHub (v0.12.0, 13 July 2026). <https://github.com/Qiskit/mcp-servers>
[9] Shiraishi, Hamamura, Ishigaki, Kadowaki. "A Model Context Protocol Server for Quantum Execution in Hybrid Quantum-HPC Environments." arXiv:2604.08318, 9 April 2026. <https://arxiv.org/abs/2604.08318>
[10] "Conductor Quantum Launches CODA MCP to Integrate Quantum Tools with AI Agents." Quantum Computing Report. <https://quantumcomputingreport.com/conductor-quantum-launches-coda-mcp-to-integrate-quantum-tools-with-ai-agents/>
[11] Qiskit Aer documentation (qiskit-aer-gpu, qiskit-aer-gpu-rocm). <https://qiskit.github.io/qiskit-aer/>
[12] AWS Braket device pricing summary, quantumcomputingcost.com (late-2026 snapshot). <https://quantumcomputingcost.com/>
[13] "Quantum Computing MCP Servers." Chatforest Reviews, July 2026 survey. <https://chatforest.com/reviews/quantum-computing-mcp-servers/>
[14] PennyLane + AMD + Rolls-Royce performance demonstration, PennyLane blog, March 2026. <https://pennylane.ai/blog/2026/03/propelling-aerospace-applications-rolls-royce-amd-pennylane>
[15] CAT capability registry, internal file (296 capabilities, 37 tools, 86 commands, 6 modes, 10 permissions, 2 extensions, 155 providers).
[16] CAT `ARCHITECTURE_REVIEW_v0.7.4.md`, internal file (Phase 0–4 roadmap, audit date 31 July 2026).
