# CAT Automated Model Discovery & Validation Pipeline

## Overview

CAT continuously and automatically discovers new AI models across official provider APIs. To ensure that only genuine, operational models are added to the user's workspace, CAT passes every candidate model through an 8-stage validation pipeline before committing it to the Dynamic Registry.

---

## The 8-Stage Validation Pipeline

Defined in `calc_terminal/models/validator.py`:

```
[Candidate Model]
       │
  1. IDENTITY          --> Enforce non-empty provider ID and valid model ID slug
       │
  2. PROVIDER          --> Verify provider exists in supported ecosystem
       │
  3. MODEL-ID SANITY   --> Detect & reject invalid tokens, wildcards (*), placeholders
       │
  4. ENDPOINT          --> Validate HTTPS / valid localhost scheme, reject malicious URLs
       │
  5. AUTHENTICATION    --> Mark as auth_required or verify API key readiness
       │
  6. CAPABILITY        --> Normalize modalities, capabilities, context limits
       │
  7. AVAILABILITY      --> Categorize as paid_api, free_api, local, or open_weight
       │
  8. REGISTRATION GATE --> Check verified status, reject discovered_but_unavailable
       │
[Dynamic Registry Commit]
```

### Stage Details

1. **Stage 1: Identity Validation**
   - Validates that both `provider` and `model_id` are non-empty strings conforming to valid naming conventions.
2. **Stage 2: Provider Validation**
   - Checks that the provider is known or has a recognized protocol adapter.
3. **Stage 3: Model-ID Sanity**
   - Discards invalid wildcards (`*`, `default`), internal placeholders, or corrupted identifiers.
4. **Stage 4: Endpoint Validation**
   - Validates URL structure. Enforces HTTPS for remote services. Disallows dangerous protocols (`file://`, `ftp://`).
5. **Stage 5: Authentication Validation**
   - If an API key is required and missing, sets `status = "auth_required"` instead of failing.
6. **Stage 6: Capability Normalization**
   - Ensures standard capability tokens: `["reasoning", "coding", "vision", "tools", "streaming", "computer_use"]`.
7. **Stage 7: Availability Assessment**
   - Maps endpoint to pricing and local/cloud flags (`local` vs `cloud`).
8. **Stage 8: Registration Gate**
   - Enforces that only models passing all sanity checks and flagged as usable are exposed in autocomplete and picker menus.

---

## Reconciliation Engine

When a provider is polled, `registry.reconcile_models(provider_id, discovered_models)` compares newly discovered models against existing entries:

- **Added**: Models present in the live API that were not previously in the registry. These are queued in `_new_models_queue` and trigger desktop/TUI notifications.
- **Updated**: Existing models whose context windows, pricing, or capabilities have changed.
- **Deprecated**: Models that were previously active but have been flagged by the vendor as deprecated.
- **Offline Protection (Stale Flag)**: If a provider is temporarily offline or returns 0 models due to network disruption, existing models are **never deleted**. They are marked with `stale = True` until the next successful verification.

---

## Background Poller

The `ProviderDiscoveryManager` runs a daemon thread that executes periodic checks:
- Configurable poll interval (default 24 hours, or triggered manually).
- Non-blocking execution prevents freezing the TUI or terminal during interactive coding sessions.
- Notification callback triggers a non-intrusive toast notification in CAT when a model like GPT-6 Astra or Claude 4 becomes available.
