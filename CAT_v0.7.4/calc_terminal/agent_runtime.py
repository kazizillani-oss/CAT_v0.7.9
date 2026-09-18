import json
import re
import time
import os

from .tool_call_normalizer import ToolCall, normalize_tool_calls


def _fix_spacing(text):
    """Post-processing repair for LLMs that return concatenated text
    without spaces (e.g. 'Whatwouldyouliketodo?Youcanaskme...').

    Only fires when the text looks concatenated — normal text with
    proper spacing passes through untouched. Never modifies fenced
    code blocks, inline code, URLs, or LaTeX."""
    if not text or not isinstance(text, str):
        return text
    if "```" in text:
        parts = text.split("```")
        for i in range(0, len(parts), 2):
            parts[i] = _fix_spacing_segment(parts[i])
        return "```".join(parts)
    return _fix_spacing_segment(text)


def _fix_spacing_segment(text):
    if not text:
        return text
    lines = text.split("\n")
    out = []
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        stripped = line.strip()
        if len(stripped) < 8:
            out.append(line)
            continue
        spaces = sum(1 for c in stripped if c == " ")
        if spaces == 0 and len(stripped) > 12:
            fixed = _fix_concatenated_line(stripped)
            out.append(line.replace(stripped, fixed))
        else:
            out.append(line)
    return "\n".join(out)


_CONTRACTIONS = {
    "I'm": "I am", "I've": "I have", "I'll": "I will", "I'd": "I would",
    "you're": "you are", "you've": "you have", "you'll": "you will",
    "you'd": "you would", "he's": "he is", "he'll": "he will",
    "he'd": "he would", "she's": "she is", "she'll": "she will",
    "she'd": "she would", "it's": "it is", "it'll": "it will",
    "we're": "we are", "we've": "we have", "we'll": "we will",
    "we'd": "we would", "they're": "they are", "they've": "they have",
    "they'll": "they will", "they'd": "they would", "that's": "that is",
    "who's": "who is", "what's": "what is", "where's": "where is",
    "when's": "when is", "how's": "how is", "let's": "let us",
    "can't": "cannot", "won't": "will not", "don't": "do not",
    "doesn't": "does not", "didn't": "did not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "hasn't": "has not", "haven't": "have not", "hadn't": "had not",
    "couldn't": "could not", "shouldn't": "should not",
    "wouldn't": "would not", "mustn't": "must not",
}


def _fix_concatenated_line(s):
    for contraction, expansion in _CONTRACTIONS.items():
        s = s.replace(contraction, expansion)
    t = re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", s)
    t = re.sub(r"([a-z])([A-Z][A-Z])", r"\1 \2", t)
    t = re.sub(r"([a-z,;)])([A-Z])", r"\1 \2", t)
    t = re.sub(r"([a-z])(\()", r"\1 \2", t)
    t = re.sub(r"(\))([a-zA-Z])", r"\1 \2", t)
    t = re.sub(r"([.!?:;,])([A-Za-z])", r"\1 \2", t)
    parts = re.split(r"([.!?:;,])", t)
    result = []
    for part in parts:
        if not part:
            continue
        if re.match(r"^[.!?:;,]$", part):
            result.append(part)
            continue
        subparts = part.split(" ")
        fixed_subparts = []
        for sp in subparts:
            if not sp:
                fixed_subparts.append(sp)
                continue
            if " " in sp or len(sp) <= 5:
                fixed_subparts.append(sp)
                continue
            words = _segment_words(sp)
            fixed_subparts.append(" ".join(words) if len(words) > 1 else sp)
        result.append(" ".join(fixed_subparts))
    out = "".join(result)
    out = re.sub(r"  +", " ", out)
    return out.strip()


_WORDS = frozenset([
    "a", "i", "an", "is", "it", "in", "on", "to", "do", "no", "so", "if",
    "or", "be", "by", "he", "me", "my", "up", "we", "us", "am", "as", "at",
    "of", "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "had", "her", "was", "one", "our", "out", "has", "his", "how", "its",
    "may", "new", "now", "old", "see", "way", "who", "did", "get", "let",
    "say", "she", "too", "use", "what", "when", "your", "will", "with",
    "have", "from", "they", "been", "each", "make", "like", "long", "look",
    "many", "some", "than", "them", "then", "these", "time", "very",
    "just", "over", "such", "take", "year", "into", "also", "back",
    "that", "this", "which", "would", "could", "about", "there", "their",
    "other", "after", "first", "being", "where", "still", "every", "world",
    "those", "ask", "help", "problem", "discuss", "coding", "request",
    "question", "scientific", "topic", "know", "think", "need", "want",
    "try", "give", "come", "here", "real", "own", "same", "tell", "work",
    "plan", "show", "find", "keep", "let", "run", "set", "go", "open",
    "read", "write", "edit", "file", "code", "test", "build", "fix",
    "error", "debug", "print", "loop", "list", "type", "class", "func",
    "true", "false", "null", "none", "self", "data", "text", "name",
    "path", "line", "char", "byte", "int", "str", "bool", "float",
    "def", "return", "import", "from", "class", "while", "break",
    "pass", "else", "elif", "except", "raise", "try", "finally",
    "welcome", "am", "here", "assist", "today", "ready", "start",
    "hello", "hey", "hi", "yes", "yeah", "sure", "okay", "ok",
    "please", "thank", "thanks", "sorry", "good", "bad", "well",
    "also", "just", "only", "even", "still", "already", "yet",
    "really", "quite", "right", "well", "too", "much", "more",
    "most", "less", "least", "very", "quite", "rather", "pretty",
    "sure", "happy", "glad", "able", "unable", "possible", "impossible",
    "need", "want", "like", "love", "hate", "prefer", "choose",
    "make", "create", "build", "write", "read", "run", "use",
    "can", "could", "will", "would", "shall", "should", "may",
    "might", "must", "ought", "dare", "need", "used",
    "tasks", "task", "work", "done", "doing", "do", "working",
    "about", "where", "there", "their", "which", "what", "when",
    "while", "about", "after", "before", "during", "through",
    "being", "having", "going", "coming", "making", "doing",
    "seeing", "saying", "telling", "asking", "helping", "using",
    "coding", "scientist", "assistant", "terminal", "agent",
])


def _segment_words(s):
    n = len(s)
    dp = [None] * (n + 1)
    dp[0] = []
    for i in range(n):
        if dp[i] is None:
            continue
        for end in range(i + 1, min(i + 20, n + 1)):
            word = s[i:end].lower()
            if word in _WORDS:
                if dp[end] is None or len(dp[end]) > len(dp[i]) + 1:
                    dp[end] = dp[i] + [s[i:end]]
    if dp[n]:
        return dp[n]
    return [s]


class AgentRuntime:
    def __init__(self, tools_dict, max_steps=18):
        self.tools = tools_dict
        self.max_steps = max_steps

    def _build_prompt(self, convo):
        lines = []
        for turn in convo:
            lines.append(f"{turn['role'].upper()}: {turn['text']}")
        lines.append("ASSISTANT:")
        return "\n\n".join(lines)

    def _normalize_action(self, action, raw_response=""):
        if not isinstance(action, dict):
            return None

        tool_keys = [k for k in action.keys() if k in self.tools]
        if len(tool_keys) == 1 and "action" not in action and "tool" not in action:
            tool_name = tool_keys[0]
            tool_args = action[tool_name]
            if isinstance(tool_args, dict):
                return {
                    "action": "tool",
                    "tool": tool_name,
                    "args": tool_args,
                    "thought": action.get("thought") or "Corrected from implicit tool call format.",
                }

        act = action.get("action")
        reserved = {"action", "tool", "args", "thought"}

        if act == "final" or act == "tool":
            return action

        if act is None and isinstance(action.get("tool"), str) and action["tool"] in self.tools:
            args = action.get("args")
            if not isinstance(args, dict):
                args = {k: v for k, v in action.items() if k not in reserved}
            return {"action": "tool", "tool": action["tool"], "args": args,
                    "thought": action.get("thought")}

        if isinstance(act, str) and act in self.tools:
            args = action.get("args")
            if not isinstance(args, dict):
                args = {k: v for k, v in action.items() if k not in reserved}
            return {"action": "tool", "tool": act, "args": args,
                    "thought": action.get("thought")}

        for key in ("text", "answer", "response", "message"):
            if isinstance(action.get(key), str):
                return {"action": "final", "text": action[key]}

        return action

    def _find_balanced_json(self, text, start=0):
        if start >= len(text) or text[start] != "{":
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    def _extract_json(self, text):
        if not text:
            return None
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            depth = 0
            for i, ch in enumerate(candidate):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(candidate[: i + 1])
                        except Exception:
                            return None
            return None

    def _extract_protocol_text(self, data):
        if not isinstance(data, dict):
            return None
        if isinstance(data.get("action"), str):
            payload = data.get("text") or data.get("answer") \
                or data.get("response") or data.get("message")
            return payload if isinstance(payload, str) else None
        for key in ("text", "answer", "response", "message"):
            if isinstance(data.get(key), str):
                return data[key]
        return None

    def _balanced_json_spans(self, text):
        spans = []
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        spans.append((start, i + 1))
                        start = -1
        return spans

    def _is_protocol_blob(self, data):
        return isinstance(data, dict) and isinstance(data.get("action"), str)

    def clean_final_text(self, text):
        if not text or not isinstance(text, str):
            return text or ""
        stripped = text.strip()
        if not stripped:
            return ""

        m = re.search(r"\{.*\}", stripped, re.S)
        if m and len(m.group(0).replace(" ", "")) >= len(stripped.replace(" ", "")) * 0.7:
            try:
                data = json.loads(m.group(0))
                payload = self._extract_protocol_text(data)
                if payload and payload.strip():
                    return payload.strip()
            except Exception:
                pass

        out = []
        cursor = 0
        changed = False
        for start, end in self._balanced_json_spans(text):
            chunk = text[start:end]
            try:
                data = json.loads(chunk)
            except Exception:
                continue
            if not self._is_protocol_blob(data):
                continue
            out.append(text[cursor:start])
            cursor = end
            changed = True
        if changed:
            out.append(text[cursor:])
            cleaned = "".join(out)
            cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
            return _fix_spacing(cleaned or text.strip())
        return _fix_spacing(text)

    def _check_permission(self, name, args, permission_callback):
        spec = self.tools[name]
        perm_key = spec.get("perm_key")
        if not perm_key:
            return True, None

        from . import permissions as perm
        if perm.manager.refused_by_always_deny(perm_key):
            return False, "Blocked by permission setting — previously denied for this session."
        needs = perm.manager.needs_prompt(perm_key)
        if not needs:
            return True, None

        describe = spec.get("describe")
        if describe:
            action_label, path, reason = describe(args)
        else:
            action_label, path, reason = name, str(args.get("path", "")), "Requested by the AI."

        if permission_callback:
            decision = permission_callback(perm_key, action_label, path, reason)
        else:
            decision = "allow_once"

        proceed = perm.manager.decide(perm_key, decision, action_label, reason)
        if proceed:
            return True, None

        verb = "Rejected" if perm.manager.restricted_review(perm_key) else "Denied"
        return False, (f"{verb} by the user \u2014 did not {action_label.lower()}. "
                       f"Do not retry this exact action; tell the user it was declined "
                       f"and continue only if there's another way to help.")

    def run(self, user_text, query_fn, system_prompt, on_step=None,
            permission_callback=None, should_cancel=None, history=None):
        def _cancelled():
            try:
                return bool(should_cancel and should_cancel())
            except Exception:
                return False

        convo = list(history) if history else []
        convo.append({"role": "user", "text": user_text})
        steps = []
        last_call = None
        stall_count = 0

        def _finish(text):
            meta = {
                "mode": "agent",
                "suggest_agent": False,
                "file_changes": "",
            }
            return self.clean_final_text(text), steps, meta

        for i in range(self.max_steps):
            if _cancelled():
                return _finish(
                    "*(interrupted \u2014 here is everything completed so far)*\n"
                    + ("\n".join(f"- {n}: {o}" for n, _, o, _c in steps)
                       if steps else "No tools had run yet."))

            prompt = self._build_prompt(convo)
            raw = query_fn(prompt, system_prompt=system_prompt)
            if not raw or not raw.strip():
                raw = query_fn(prompt, system_prompt=system_prompt)

            tool_calls = normalize_tool_calls(raw, list(self.tools.keys()))
            if tool_calls:
                tc = tool_calls[0]
                name = tc.name
                args = tc.arguments if isinstance(tc.arguments, dict) else {}
                spec = self.tools.get(name)

                fingerprint = (name, json.dumps(args, sort_keys=True, default=str))
                stall_count = stall_count + 1 if fingerprint == last_call else 0
                last_call = fingerprint

                if not spec:
                    obs = f"Tool '{name}' does not exist. Valid tools: {', '.join(self.tools)}"
                elif stall_count >= 1:
                    obs = ("You already ran this exact tool call and got a result \u2014 repeating it "
                           "won't help. Use that result and move on to the NEXT step, or if every "
                           "part of the question is now answered, reply with the final JSON action.")
                else:
                    if on_step:
                        on_step(name, args)
                    if _cancelled():
                        return _finish(
                            "*(interrupted \u2014 here is everything completed so far)*\n"
                            + ("\n".join(f"- {n}: {o}" for n, _, o, _c in steps)
                               if steps else "No tools had run yet."))
                    proceed, denial_obs = self._check_permission(name, args, permission_callback)
                    if not proceed:
                        obs = denial_obs
                    else:
                        try:
                            obs = spec["run"](args)
                        except Exception as e:
                            obs = f"Tool '{name}' raised an error: {e}"
                    change = {}
                    steps.append((name, args, obs, change))

                convo.append({"role": "assistant", "text": raw})
                steps_left = self.max_steps - i - 1
                nudge = ""
                if steps_left <= 3:
                    nudge = (f"\n\n(You have about {steps_left} step(s) left \u2014 start wrapping up: "
                             "finish any remaining sub-calculations now and prepare the final answer.")
                convo.append({"role": "user", "text": (
                    f"TOOL RESULT [{name}]: {obs}{nudge}\n\n"
                    "Continue: call another tool if needed, or reply with the final JSON action now."
                )})
                continue

            action = self._normalize_action(self._extract_json(raw), raw)
            if action and action.get("action") == "final":
                text = action.get("text") or raw
                return _finish(text)
            if action and action.get("action") == "tool":
                name = action.get("tool")
                args = action.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                spec = self.tools.get(name)

                fingerprint = (name, json.dumps(args, sort_keys=True, default=str))
                stall_count = stall_count + 1 if fingerprint == last_call else 0
                last_call = fingerprint

                if not spec:
                    obs = f"Tool '{name}' does not exist. Valid tools: {', '.join(self.tools)}"
                elif stall_count >= 1:
                    obs = ("You already ran this exact tool call and got a result \u2014 repeating it "
                           "won't help. Use that result and move on to the NEXT step, or if every "
                           "part of the question is now answered, reply with the final JSON action.")
                else:
                    if on_step:
                        on_step(name, args)
                    if _cancelled():
                        return _finish(
                            "*(interrupted \u2014 here is everything completed so far)*\n"
                            + ("\n".join(f"- {n}: {o}" for n, _, o, _c in steps)
                               if steps else "No tools had run yet."))
                    proceed, denial_obs = self._check_permission(name, args, permission_callback)
                    if not proceed:
                        obs = denial_obs
                    else:
                        try:
                            obs = spec["run"](args)
                        except Exception as e:
                            obs = f"Tool '{name}' raised an error: {e}"
                    change = {}
                    steps.append((name, args, obs, change))

                convo.append({"role": "assistant", "text": raw})
                steps_left = self.max_steps - i - 1
                nudge = ""
                if steps_left <= 3:
                    nudge = (f"\n\n(You have about {steps_left} step(s) left \u2014 start wrapping up: "
                             "finish any remaining sub-calculations now and prepare the final answer.")
                convo.append({"role": "user", "text": (
                    f"TOOL RESULT [{name}]: {obs}{nudge}\n\n"
                    "Continue: call another tool if needed, or reply with the final JSON action now."
                )})
                continue

            return _finish(raw or "I couldn't reach the AI provider. Try again.")

        convo.append({"role": "user", "text": (
            "You're out of tool-call steps. Using every result computed above, give your single "
            "best complete answer to the ORIGINAL question now \u2014 reply with the final "
            'JSON action: {"action": "final", "text": "<complete answer, every part labeled>"}.'
        )})
        raw = query_fn(self._build_prompt(convo), system_prompt=system_prompt)
        action = self._normalize_action(self._extract_json(raw), raw)
        if action and action.get("action") == "final" and action.get("text"):
            return _finish(action["text"])
        if raw and raw.strip():
            return _finish(raw)
        summary = "\n".join(f"- {n}: {o}" for n, _, o, _c in steps) or "No tools were run."
        return _finish("Here's everything computed so far while working on that:\n" + summary)
