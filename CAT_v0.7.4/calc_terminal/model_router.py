"""
CAT v0.7.9.0 — model_router.py: the Smart Model Router + Request Classifier.

CAT should not blindly send every request to the same model through the
same heavyweight path. This module is the brain that sits between the
user's message and the pipeline:

    USER MESSAGE
        ↓
    classify()          — task types (pure regex/heuristics, no LLM call:
    ↓                      classification itself must cost microseconds,
    │                      not seconds)
    route()
    ├── fast_path       — simple chat: skip memory/tools/multi-agent/vision
    ├── agent_path      — real tool loop (coding / agentic execution)
    ├── vision_path     — image(s) attached → vision-capable model chosen
    └── multi_ai_path   — genuinely complex tasks only

The router also owns the MODEL CAPABILITY REGISTRY: every configured
provider/model (primary + backups) is described by ModelCapabilities
(text/vision/tools/streaming/reasoning/context_window/latency/cost/
reliability) so routing decisions never have to be discovered "after a
request fails".

Everything here is heuristic and local: no network calls on the routing
path (availability probing would add latency — the opposite of the
goal). Availability/failover stays with aicore's existing backup chain;
the router just picks the BEST CAPABLE candidate order.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# ----------------------------------------------------------------- types --

TASK_TYPES = (
    "simple_chat", "coding", "debugging", "research", "mathematics",
    "long_context", "vision", "document_analysis", "multimodal",
    "planning", "agentic_execution", "multi_agent",
)

# Pipeline paths the router can choose between.
PATH_FAST = "fast"
PATH_STREAM = "stream"          # plain streaming chat (default)
PATH_AGENT = "agent"            # tool-calling loop
PATH_VISION = "vision"          # image analysis
PATH_MULTI_AI = "multi_ai"      # orchestrated team

# Privacy & routing policies (CAT Master Architecture)
POLICY_LOCAL_FIRST = "local_first"
POLICY_CLOUD_FIRST = "cloud_first"
POLICY_BEST_AVAILABLE = "best_available"
POLICY_NEVER_CLOUD = "never_cloud"
POLICIES = (POLICY_LOCAL_FIRST, POLICY_CLOUD_FIRST, POLICY_BEST_AVAILABLE, POLICY_NEVER_CLOUD)

# v0.7.9.5 complexity classes (spec #4): one coarse label per request so
# the execution path AND the timeout budget both key off the same
# classification — simple prompt → simple path, complex prompt → complex
# path. Pure-local, microseconds.
CLASS_TRIVIAL = "TRIVIAL"       # "hi", "2+2", "thanks" → direct answer
CLASS_SIMPLE = "SIMPLE"         # "what is recursion?" → one efficient call
CLASS_NORMAL = "NORMAL"         # coding/debugging questions → model + tools
CLASS_COMPLEX = "COMPLEX"       # long context / docs / vision analysis
CLASS_AGENT = "AGENT"           # workspace/build tasks → agent workflow
CLASS_RESEARCH = "RESEARCH"     # web research → retrieval-heavy path


@dataclass
class RouteDecision:
    """What the router decided for one user message."""
    path: str = PATH_STREAM
    task_types: Set[str] = field(default_factory=set)
    reason: str = ""
    # When images are attached and the PRIMARY provider/model cannot see,
    # this carries a vision-capable backup config to use instead.
    vision_config: Optional[dict] = None
    use_tools: bool = False
    fast: bool = False
    use_multi_agent: bool = False
    # TRIVIAL / SIMPLE / NORMAL / COMPLEX / AGENT / RESEARCH
    size_class: str = CLASS_NORMAL
    privacy_policy: str = POLICY_LOCAL_FIRST
    candidate_chain: List[dict] = field(default_factory=list)


@dataclass
class ModelCapabilities:
    """Requirement #8: explicit per-model capability record. The router
    consults this BEFORE sending a request; capabilities are never
    discovered only after a failure."""
    provider: str = ""
    model: str = ""
    api_style: str = "openai"
    text: bool = True
    vision: bool = False
    tools: bool = True
    streaming: bool = True
    reasoning: bool = False
    context_window: int = 32000
    latency_score: float = 0.5   # 0 slow .. 1 instant (heuristic prior)
    cost_score: float = 0.5      # 0 cheap .. 1 expensive (heuristic prior)
    reliability: float = 0.7     # heuristic prior; nudged by observed fails
    is_backup: bool = False

    def score_for(self, needed_vision: bool = False,
                  needed_reasoning: bool = False,
                  needed_long_ctx: bool = False,
                  wants_fast: bool = False) -> float:
        """Higher is better fit for the stated requirements."""
        if needed_vision and not self.vision:
            return -1.0
        if needed_long_ctx and self.context_window < 60000:
            return -1.0
        s = 1.0
        if needed_vision:
            s += 0.5
        if needed_reasoning and self.reasoning:
            s += 0.4
        if wants_fast:
            s += self.latency_score * 0.6
            s -= self.cost_score * 0.15
        else:
            s += self.reliability * 0.2
            if needed_reasoning:
                s += min(self.context_window, 200000) / 500000.0
        return s

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_style": self.api_style,
            "text": self.text,
            "vision": self.vision,
            "tools": self.tools,
            "streaming": self.streaming,
            "reasoning": self.reasoning,
            "context_window": self.context_window,
            "latency_score": self.latency_score,
            "cost_score": self.cost_score,
            "reliability": self.reliability,
            "is_backup": self.is_backup,
        }


# ------------------------------------------------------- classification --

_RE_GREETING = re.compile(
    r"^\s*(hi|hello|hey|yo|sup|good (morning|evening|afternoon)|thanks|thank you|"
    r"ok(ay)?|cool|nice|great|bye)\b[\s!.?]*$", re.I)

_RE_SIMPLE_Q = re.compile(
    r"\b(what is|what's|who is|when is|where is|define|explain|meaning of|"
    r"how do you spell|translate)\b.{0,120}\?", re.I)

_RE_ARITH = re.compile(r"^\s*[\d\s().+\-*/^%]+$")
# "what is 2+2", "12*7" etc. — tiny arithmetic, no tools needed.
_RE_TINY_MATH = re.compile(
    r"\b(?:what(?:'s| is)\s+)?\d+[\s]*[+\-*/x×÷^%][\s]*\d+", re.I)

_RE_CODING = re.compile(
    r"\b(code|coding|program|script|function|class |refactor|implement|"
    r"build (me |us )?(a|an|the)? ?(website|web ?app|app|site|page|dashboard|game|api|server|cli|bot)|"
    r"create (a|an|the)? ?(website|web ?app|app|site|page|component|file|module|package)|"
    r"react|vue|angular|django|flask|fastapi|node|express|html|css|javascript|typescript|python|"
    r"java\b|c\+\+|c#|rust|golang|sql query|database schema|unit test|pytest|npm|pip install)\b",
    re.I)

_RE_DEBUGGING = re.compile(
    r"\b(debug|bug|error|exception|traceback|stack trace|crash|not working|"
    r"doesn'?t work|fails?|fix this|why is this (broken|failing)|"
    r"undefined|null pointer|segfault|lint)\b", re.I)

_RE_RESEARCH = re.compile(
    r"\b(research|latest|recent|news|current|202\d|compare|vs\.?|versus|"
    r"search (the web|online)|look up|sources?|cite|state of the art|"
    r"best (library|framework|tool)|documentation)\b", re.I)

_RE_MATH = re.compile(
    r"\b(solve|equation|integral|derivative|limit|matrix|probability|"
    r"calculus|algebra|geometry|trigonometry|prove|theorem|"
    r"first[- ]order|second[- ]order|kinetics|mole|stoichiometr|nernst|"
    r"half[- ]life|arrhenius|ph\b|equilibrium)\b", re.I)

_RE_PLANNING = re.compile(
    r"\b(plan|roadmap|strategy|milestones?|architecture design|design (a|an) "
    r"(system|architecture|approach)|step[- ]by[- ]step plan|brainstorm|proposal)\b",
    re.I)

_RE_MULTI_AGENT = re.compile(
    r"\b(review (this|the) (whole |entire )?(project|codebase|architecture)|"
    r"(refactor|improve|overhaul).{0,40}(project|codebase|architecture)|"
    r"across (the )?(whole |entire )?(project|codebase)|multi[- ]agent|"
    r"use (multiple|several|3) (agents|ais|models)|team (up|of agents))\b",
    re.I)

_RE_AGENTIC = re.compile(
    r"\b(create|write|make|generate|build|install|delete|move|rename|organize|run|execute)"
    r"\b[^?.!]{0,60}\b(file|folder|directory|script|package|command|test)s?\b", re.I)
_RE_FILE_OP = re.compile(
    r"\b(read|open|list|summarize) (this |the |that )?(file|folder|directory|workspace)\b", re.I)

_RE_LONG_CTX = re.compile(
    r"\b(entire (document|codebase|book|pdf)|whole (document|file|report)|"
    r"large document|long document|all \d+ (pages|files)|summarize .{0,30}(document|chapter|paper))\b",
    re.I)

_RE_DOC_ANALYSIS = re.compile(
    r"\b(analyz|extract|parse|ocr|read) .{0,40}(image|screenshot|scan|document|receipt|invoice|table|chart|diagram)\b",
    re.I)

_RE_EXTRACT_ALL = re.compile(
    r"\b(extract (and explain |all )?(everything|all|important|information|text|data)|"
    r"detailed (analysis|extraction)|full(y)? (analyz|extract)|transcribe)\b", re.I)


def classify(prompt: str, attachments: Optional[List] = None,
             mode: Optional[str] = None) -> Set[str]:
    """Pure-local task classification. Returns a set of TASK_TYPES.
    Costs microseconds — regex only, deliberately NO LLM call here."""
    text = (prompt or "").strip()
    types: Set[str] = set()
    low = text.lower()

    has_image = any(getattr(a, "kind", "") == "image" or
                    str(getattr(a, "extension", "")).lower() in
                    (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
                     ".tif", ".tiff")
                    for a in (attachments or []))
    has_any_attachment = bool(attachments)

    if len(text) <= 140 and (_RE_GREETING.match(text) or _RE_SIMPLE_Q.match(text)
                             or _RE_ARITH.match(text)):
        types.add("simple_chat")

    if _RE_TINY_MATH.search(low) and len(text) < 80:
        types.add("simple_chat")
        types.add("mathematics")

    if _RE_CODING.search(low):
        types.update(("coding",))
    if _RE_DEBUGGING.search(low):
        types.add("debugging")
    if _RE_RESEARCH.search(low):
        types.add("research")
    if _RE_MATH.search(low):
        types.add("mathematics")
    if _RE_PLANNING.search(low):
        types.add("planning")
    if _RE_LONG_CTX.search(low) or (has_any_attachment and len(text) > 400):
        types.add("long_context")
    if has_image:
        types.update(("vision", "multimodal"))
        if _RE_DOC_ANALYSIS.search(low) or _RE_EXTRACT_ALL.search(low):
            types.add("document_analysis")
    elif has_any_attachment:
        types.add("document_analysis")
    if _RE_AGENTIC.search(low) or _RE_FILE_OP.search(low):
        types.add("agentic_execution")
    if _RE_MULTI_AGENT.search(low):
        types.add("multi_agent")
    if mode in ("agent", "build"):
        types.add("agentic_execution")
    if mode == "debugger":
        types.add("debugging")
    if mode == "research":
        types.add("research")
    if mode == "plan":
        types.add("planning")
    if not types:
        types.add("simple_chat" if len(text) < 60 else "research")
    return types


def complexity_score(types: Set[str], prompt: str) -> float:
    """0..1 rough complexity estimate used for dynamic multi-AI team sizing
    and the fast/heavy path decision."""
    score = 0.15
    heavy = {"coding": 0.25, "agentic_execution": 0.25, "multi_agent": 0.35,
             "long_context": 0.2, "vision": 0.15, "document_analysis": 0.1,
             "planning": 0.1, "debugging": 0.15}
    for t in types:
        score += heavy.get(t, 0.05)
    words = len((prompt or "").split())
    if words > 60:
        score += 0.1
    if words > 150:
        score += 0.1
    return min(1.0, score)


def complexity_class(types: Set[str], prompt: str,
                     mode: Optional[str] = None) -> str:
    """Map the classification to one coarse execution class (spec #4).
    Drives both the pipeline path AND the timeout size class."""
    p = (prompt or "").strip()
    # Explicit agent/build intent or agentic work always wins.
    if "multi_agent" in types or "agentic_execution" in types \
            or "planning" in types or mode in ("agent", "build"):
        return CLASS_AGENT
    if "research" in types:
        return CLASS_RESEARCH
    if types & {"vision", "document_analysis", "long_context", "multimodal"}:
        return CLASS_COMPLEX
    if len(p) <= 25 and (types <= {"simple_chat"} or not types):
        return CLASS_TRIVIAL
    if types <= {"simple_chat", "mathematics"} and len(p) < 120:
        return CLASS_SIMPLE
    if types & {"coding", "debugging", "mathematics"}:
        return CLASS_NORMAL
    return CLASS_NORMAL


# Timeout budget per class (aicore.request_timeouts consumes the same
# labels): trivial prompts fail fast instead of hanging on '...'.
_CLASS_TO_SIZE = {
    CLASS_TRIVIAL: "simple",
    CLASS_SIMPLE: "simple",
    CLASS_NORMAL: "normal",
    CLASS_COMPLEX: "normal",
    CLASS_AGENT: "large",
    CLASS_RESEARCH: "normal",
}


def timeout_size_class(complexity_cls: str) -> str:
    return _CLASS_TO_SIZE.get(complexity_cls, "normal")


# ---------------------------------------------------- capability registry --

_VISION_STYLES = ("openai", "anthropic", "gemini")

_NON_VISION_HINTS = ("gpt-3.5", "llama", "mixtral", "mistral", "deepseek",
                     "phi-3", "phi3", "qwen", "command", "gemma", "granite",
                     "codex", "o1-mini", "o3-mini")
_VISION_HINTS = ("gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4", "claude-3",
                 "claude-4", "gemini-1.5", "gemini-2.0", "gemini-2.5",
                 "gemini-3", "qwen2.5-vl", "llava", "llama-3.2-vision",
                 "pixtral", "vision")
_REASONING_HINTS = ("o1", "o3", "o4", "r1", "thinking", "reason", "qwq",
                    "claude-3.7", "claude-4", "gpt-5", "deepseek-r")
_FAST_HINTS = ("mini", "flash", "lite", "small", "turbo", "instant", "haiku",
               "nano", "8b", "7b")
_EXPENSIVE_HINTS = ("opus", "gpt-5", "o3", "ultra", "claude-4")
_BIGCTX_HINTS = ("gemini", "claude-3", "claude-4", "gpt-4.1", "gpt-5")


_registry_cache: Optional[Tuple[float, List[ModelCapabilities]]] = None
_REGISTRY_TTL = 30.0  # seconds — config rarely changes mid-session


def invalidate_cache() -> None:
    """Invalidate cached available configs so router immediately picks up
    new primary or backup model choices without waiting for TTL."""
    global _registry_cache
    _registry_cache = None


def capabilities_for(provider: str, model: str = "") -> ModelCapabilities:
    """Public helper to derive capabilities for a given provider and model."""
    return _capabilities_for({"provider": provider, "model": model})


def _capabilities_for(config: dict, is_backup: bool = False) -> ModelCapabilities:
    """Derive ModelCapabilities from a provider config dict. Pure name/
    style heuristics plus curated context-window metadata — no network."""
    provider = str(config.get("provider", "")).lower()
    model = str(config.get("model", "")).lower()
    api_style = str(config.get("api_style", "") or "").lower()
    try:
        from . import aicore as _a
        info = _a.PROVIDERS.get(provider)
        api_style = api_style or ((info["api_style"] if info else "openai") or "openai")
    except Exception:
        api_style = api_style or "openai"

    caps = ModelCapabilities(provider=provider, model=model,
                             api_style=api_style, is_backup=is_backup)
    caps.vision = (api_style in _VISION_STYLES
                   and not any(h in model for h in _NON_VISION_HINTS)
                   and any(h in model for h in _VISION_HINTS))
    caps.tools = api_style != "unsupported"
    caps.streaming = True
    caps.reasoning = any(h in model for h in _REASONING_HINTS)
    caps.latency_score = 0.85 if any(h in model for h in _FAST_HINTS) else 0.45
    if provider == "ollama":
        caps.latency_score = max(0.1, caps.latency_score - 0.25)
        caps.cost_score = 0.0
    if provider == "groq":
        caps.latency_score = min(1.0, caps.latency_score + 0.2)
    caps.cost_score = 0.8 if any(h in model for h in _EXPENSIVE_HINTS) else \
        (0.3 if any(h in model for h in _FAST_HINTS) else 0.5)
    try:
        from . import aicore as _a
        caps.context_window = int(_a.context_window_for(model) or 32000)
    except Exception:
        caps.context_window = 200000 if any(h in model for h in _BIGCTX_HINTS) else 32000
    return caps


def available_configs(force_refresh: bool = False) -> List[ModelCapabilities]:
    """Every configured model (primary first, then enabled backups), with
    capabilities. Cached briefly — building it must stay off the hot path."""
    global _registry_cache
    now = time.time()
    if not force_refresh and _registry_cache is not None:
        ts, items = _registry_cache
        if now - ts < _REGISTRY_TTL:
            return items
    out: List[ModelCapabilities] = []
    try:
        from . import aicore as _a
        cfg = _a.load_config() or {}
        if cfg.get("provider"):
            out.append(_capabilities_for(cfg, is_backup=False))
        try:
            from .providers.provider_manager import backup_configs
            for bcfg, _entry in backup_configs():
                out.append(_capabilities_for(bcfg, is_backup=True))
        except Exception:
            pass
    except Exception:
        pass
    _registry_cache = (now, out)
    return out


def find_vision_capable(preferred_config: Optional[dict] = None
                        ) -> Tuple[Optional[dict], Optional[ModelCapabilities]]:
    """Requirement #19: when the active model can't see an image, find a
    configured model that CAN. Returns (config_dict_or_None, caps_or_None).
    Never raises; (None, None) means honestly 'no vision-capable model is
    configured'."""
    configs = available_configs()
    if preferred_config:
        pref_caps = _capabilities_for(preferred_config)
        if pref_caps.vision:
            return preferred_config, pref_caps
    for caps in configs:
        if caps.vision:
            try:
                if caps.is_backup:
                    from .providers.provider_manager import backup_configs
                    for bcfg, _e in backup_configs():
                        if str(bcfg.get("provider", "")).lower() == caps.provider \
                                and str(bcfg.get("model", "")).lower() == caps.model:
                            return bcfg, caps
                else:
                    from . import aicore as _a
                    return _a.load_config(), caps
            except Exception:
                continue
    return None, None


def get_privacy_policy() -> str:
    """Read the active privacy and routing policy from central config."""
    try:
        from . import config as _cfg
        c = _cfg.get_config()
        p = getattr(c, "privacy_policy", POLICY_LOCAL_FIRST)
        if p in POLICIES:
            return p
    except Exception:
        pass
    return POLICY_LOCAL_FIRST


def set_privacy_policy(policy: str) -> None:
    """Update and persist the active privacy and routing policy."""
    if policy not in POLICIES:
        return
    try:
        from . import config as _cfg
        c = _cfg.get_config()
        c.privacy_policy = policy
        _cfg.save_config(c)
        invalidate_cache()
    except Exception:
        pass


def build_candidate_chain(task_types: Set[str], prompt: str = "", policy: Optional[str] = None) -> List[dict]:
    """Return ordered candidate model configs adhering to the selected privacy policy.
    
    - never_cloud: Strict privacy — filters out all non-local providers.
    - local_first: Prioritizes local models; cloud models act as secondary fallback.
    - cloud_first: Prioritizes high-end cloud providers; local models act as offline fallback.
    - best_available: Scores candidates purely on capability and benchmark fit.
    """
    pol = policy or get_privacy_policy()
    caps_list = available_configs()
    
    needed_vision = "vision" in task_types
    needed_reasoning = bool({"reasoning", "mathematics", "debugging"} & task_types)
    needed_long_ctx = "long_context" in task_types
    wants_fast = "simple_chat" in task_types
    
    local_providers = {"ollama", "local", "vllm"}
    
    scored_candidates = []
    for c in caps_list:
        is_local = c.provider.lower() in local_providers
        if pol == POLICY_NEVER_CLOUD and not is_local:
            continue
            
        base_score = c.score_for(
            needed_vision=needed_vision,
            needed_reasoning=needed_reasoning,
            needed_long_ctx=needed_long_ctx,
            wants_fast=wants_fast,
        )
        if base_score < 0:
            continue
            
        priority = 0.0
        if pol == POLICY_LOCAL_FIRST:
            priority = 10.0 if is_local else 0.0
        elif pol == POLICY_CLOUD_FIRST:
            priority = 10.0 if not is_local else 0.0
        elif pol == POLICY_BEST_AVAILABLE:
            priority = 5.0 * (1.0 if not is_local else 0.8)
            
        final_score = priority + base_score
        scored_candidates.append((final_score, c))
        
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    return [c.to_dict() for _, c in scored_candidates]


# ----------------------------------------------------------------- route --

def route(prompt: str, attachments: Optional[List] = None,
          mode: Optional[str] = None,
          workflow_hint: Optional[str] = None) -> RouteDecision:
    """The one function the UI/pipeline calls per user message. Returns a
    RouteDecision choosing the pipeline path + best capable model config
    (for vision rerouting). Deliberately cheap: pure local heuristics."""
    t0 = time.perf_counter()
    types = classify(prompt, attachments, mode)
    pol = get_privacy_policy()
    dec = RouteDecision(task_types=types, privacy_policy=pol)
    dec.candidate_chain = build_candidate_chain(types, prompt, pol)
    has_image = "vision" in types
    complexity = complexity_score(types, prompt)
    dec.size_class = timeout_size_class(complexity_class(types, prompt, mode))

    # ---- vision path -----------------------------------------------------
    if has_image:
        dec.path = PATH_VISION
        dec.use_tools = bool({"agentic_execution"} & types) and mode in ("agent", "build")
        dec.reason = "image attached → vision-capable model required"
        dec.size_class = "large"
        vision_cfg, vcaps = find_vision_capable()
        dec.vision_config = vision_cfg
        if vision_cfg is None:
            dec.reason = ("image attached but no vision-capable model is "
                          "configured — will report clearly")
        _stamp(dec, t0)
        return dec

    # ---- fast path (requirement #9) --------------------------------------
    tiny = len(prompt) < 220 and types <= {"simple_chat", "mathematics", "research"}
    greetingish = bool({"simple_chat"} & types) and complexity <= 0.2
    # v0.7.9.5: a genuinely trivial prompt takes the fast path regardless
    # of complexity scoring — "hi" must never trigger planning.
    trivial = len((prompt or "").strip()) <= 25 and \
        types <= {"simple_chat", "mathematics"}
    if (tiny and (greetingish or mode in (None, "notebook"))) or \
            (trivial and mode in (None, "notebook")):
        dec.path = PATH_FAST
        dec.fast = True
        dec.size_class = "simple"
        dec.reason = ("trivial prompt → fast path (no memory scan, no agents,"
                      " no tools)" if trivial else
                      "simple question → fast path (no memory scan, no agents,"
                      " no tools)")
        _stamp(dec, t0)
        return dec

    # ---- multi-AI only when it actually helps (requirement #33) ----------
    wants_multi = "multi_agent" in types or (
        mode == "agent" and complexity >= 0.75 and
        ({"coding", "agentic_execution", "long_context"} & types))
    if wants_multi and complexity >= 0.6:
        dec.path = PATH_MULTI_AI
        dec.use_multi_agent = True
        dec.size_class = "large"
        dec.reason = f"complex multi-part task (complexity {complexity:.2f}) → orchestrated team"
        _stamp(dec, t0)
        return dec

    # ---- agent/tool path --------------------------------------------------
    if mode in ("agent", "build"):
        dec.path = PATH_AGENT
        dec.use_tools = True
        dec.size_class = "large"
        dec.reason = f"{mode} mode → tool-executing agent loop"
        _stamp(dec, t0)
        return dec
    if "agentic_execution" in types and mode not in ("notebook",):
        dec.path = PATH_AGENT
        dec.use_tools = True
        dec.size_class = "large"
        dec.reason = "task requires real file/tool operations → agent loop"
        _stamp(dec, t0)
        return dec
    if workflow_hint in ("install", "pipeline"):
        dec.path = PATH_AGENT
        dec.use_tools = True
        dec.size_class = "large"
        dec.reason = f"workflow '{workflow_hint}' → agent/pipeline execution"
        _stamp(dec, t0)
        return dec

    # ---- default: plain streaming -----------------------------------------
    bits = sorted(types)
    dec.path = PATH_STREAM
    dec.fast = complexity <= 0.2
    dec.reason = "streaming chat (" + ", ".join(bits) + ")" if bits else "streaming chat"
    _stamp(dec, t0)
    return dec


def _stamp(dec: RouteDecision, t0: float) -> None:
    try:
        from . import metrics
        m = metrics.current()
        if m is not None:
            m.mark_stage("routing", t0)
            m.task_types = sorted(dec.task_types)
            m.route_path = dec.path
    except Exception:
        pass


def describe_decision(dec: RouteDecision) -> str:
    """One human-readable line for the UI activity feed — real decision,
    really made."""
    tt = ", ".join(sorted(dec.task_types)) or "general"
    pol_tag = f" [{dec.privacy_policy.upper()}]" if hasattr(dec, "privacy_policy") and dec.privacy_policy else ""
    icon = "[Router]"
    try:
        # Check if terminal/stream supports unicode compass
        import sys
        enc = getattr(sys.stdout, "encoding", "") or "utf-8"
        if "utf" in enc.lower():
            icon = "\U0001f9ed Router:"
        else:
            icon = "[Router]"
    except Exception:
        icon = "[Router]"
    line = f"{icon} {dec.path.upper()}{pol_tag} ({tt})"
    if dec.vision_config is not None:
        line += (f" → {dec.vision_config.get('provider', '?')}/"
                 f"{dec.vision_config.get('model', '?')}")
    return line
