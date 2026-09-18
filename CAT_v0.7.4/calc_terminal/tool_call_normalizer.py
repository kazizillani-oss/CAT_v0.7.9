import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _log(msg):
    try:
        print(f"[Normalizer] {msg}", file=sys.stderr)
    except Exception:
        pass


TOOL_ALIASES = {
    "runcommand": "run_terminal",
    "run_command": "run_terminal",
    "execute_command": "run_terminal",
    "execute_terminal": "run_terminal",
    "run_cmd": "run_terminal",
    "terminal": "run_terminal",
    "shell": "run_terminal",
    "bash": "run_terminal",
    "listdirectory": "list_directory",
    "list_dir": "list_directory",
    "list_files": "list_directory",
    "ls": "list_directory",
    "dir": "list_directory",
    "create_file": "write_file",
    "new_file": "write_file",
    "rewrite_file": "write_file",
    "writefile": "write_file",
    "write": "write_file",
    "edit_file": "edit_file",
    "editfile": "edit_file",
    "modify_file": "edit_file",
    "patch_file": "edit_file",
    "replace_in_file": "edit_file",
    "str_replace_editor": "edit_file",
    "delete_file": "delete_file",
    "deletefile": "delete_file",
    "remove_file": "delete_file",
    "rm": "delete_file",
    "move_file": "rename_file",
    "movefile": "rename_file",
    "rename": "rename_file",
    "mv": "rename_file",
    "create_directory": "create_folder",
    "create_dir": "create_folder",
    "mkdir": "create_folder",
    "read_file": "read_file",
    "readfile": "read_file",
    "cat": "read_file",
    "search_workspace": "search_workspace",
    "search": "search_workspace",
    "find": "search_workspace",
    "grep": "search_workspace",
    "run_build": "run_build",
    "build_project": "run_build",
    "build": "run_build",
    "run_tests": "run_tests",
    "run_test": "run_tests",
    "runtests": "run_tests",
    "test_suite": "run_tests",
    "inspect_project": "inspect_project",
    "project_info": "inspect_project",
    "inspect": "inspect_project",
    "install_package": "install_packages",
    "install": "install_packages",
    "archive_list": "archive_list",
    "list_archive": "archive_list",
    "zip_list": "archive_list",
    "archive_extract": "archive_extract",
    "extract_archive": "archive_extract",
    "unzip": "archive_extract",
    "extract": "archive_extract",
    "archive_delete_entries": "archive_delete_entries",
    "archive_remove_entries": "archive_delete_entries",
    "archive_add_entries": "archive_add_entries",
    "add_to_archive": "archive_add_entries",
    "archive_repack": "archive_repack",
    "repack_archive": "archive_repack",
    "archive_validate": "archive_validate",
    "validate_archive": "archive_validate",
}


def resolve_tool_name(name):
    if not name:
        return name
    # normalize separators/case first so "Create File", "write-file",
    # "RUN COMMAND" style names all resolve (requirement #2)
    low = re.sub(r"[\s\-]+", "_", str(name).lower().strip())
    if low in TOOL_ALIASES:
        resolved = TOOL_ALIASES[low]
        if resolved != low:
            _log(f"Alias resolved: {name} -> {resolved}")
        return resolved
    return low


@dataclass
class ToolCall:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""
    source_format: str = ""
    confidence: float = 1.0


def _find_balanced_json(text: str, start: int = 0) -> Optional[str]:
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


def _parse_json_protocol(text: str, known_tools: set) -> List[ToolCall]:
    calls = []
    patterns = [
        r'\{"action"\s*:\s*"tool"\s*,\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"args"\s*:\s*(\{[^}]*\})\s*\}',
        r'\{"action"\s*:\s*"tool"\s*,\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"parameters"\s*:\s*(\{[^}]*\})\s*\}',
        r'\{"tool"\s*:\s*"([^"]+)"\s*,\s*"args"\s*:\s*(\{[^}]*\})\s*\}',
        r'\{"tool"\s*:\s*"([^"]+)"\s*,\s*"parameters"\s*:\s*(\{[^}]*\})\s*\}',
        r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            tool_name = match.group(1)
            args_str = match.group(2)
            if tool_name in known_tools:
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
                calls.append(ToolCall(
                    name=tool_name,
                    arguments=args,
                    source_format="json_protocol",
                    confidence=0.95,
                ))
    idx = 0
    while idx < len(text):
        brace_pos = text.find("{", idx)
        if brace_pos == -1:
            break
        obj_str = _find_balanced_json(text, brace_pos)
        if not obj_str:
            idx = brace_pos + 1
            continue
        try:
            obj = json.loads(obj_str)
        except json.JSONDecodeError:
            idx = brace_pos + 1
            continue
        if isinstance(obj, dict):
            action = obj.get("action", "")
            tool = obj.get("tool", obj.get("name", ""))
            args = obj.get("args", obj.get("parameters", obj.get("arguments", {})))
            if action == "tool" and tool in known_tools:
                calls.append(ToolCall(
                    name=tool,
                    arguments=args if isinstance(args, dict) else {},
                    source_format="json_protocol_action",
                    confidence=0.9,
                ))
            elif action in known_tools:
                calls.append(ToolCall(
                    name=action,
                    arguments={k: v for k, v in obj.items() if k != "action"},
                    source_format="json_protocol_action",
                    confidence=0.85,
                ))
            elif tool in known_tools and tool:
                calls.append(ToolCall(
                    name=tool,
                    arguments=args if isinstance(args, dict) else {},
                    source_format="json_protocol",
                    confidence=0.8,
                ))
        idx = brace_pos + len(obj_str)
    return calls


def _extract_xml_params(block):
    params = {}
    for m in re.finditer(r'<parameter\s+name="([^"]+)">(.*?)</parameter>', block, re.DOTALL):
        params[m.group(1).strip()] = m.group(2).strip()
    return params

def _parse_xml_tool_calls(text, known_tools):
    calls = []; seen = set()

    ire = re.compile(r'<invoke\s+name="([^"]+)">(.*?)</invoke>', re.DOTALL)
    for m in ire.finditer(text):
        rn = m.group(1).strip(); bl = m.group(2).strip()
        tn = resolve_tool_name(rn); p = _extract_xml_params(bl)
        if not p:
            try: p = json.loads(bl)
            except: p = {'raw': bl}
        k = (tn, json.dumps(p, sort_keys=True))
        if k in seen: continue; seen.add(k)
        if tn in known_tools:
            calls.append(ToolCall(name=tn, arguments=p, source_format='xml_invoke', confidence=0.9))
            _log('TOOL_DETECTED: ' + tn + ' (xml_invoke)')

    mmre = re.compile(r'<minimax:toolcall>(.*?)</minimax:toolcall>', re.DOTALL)
    for m in mmre.finditer(text):
        for im in ire.finditer(m.group(1)):
            rn = im.group(1).strip(); bl = im.group(2).strip()
            tn = resolve_tool_name(rn); p = _extract_xml_params(bl)
            if not p:
                try: p = json.loads(bl)
                except: p = {'raw': bl}
            k = (tn, json.dumps(p, sort_keys=True))
            if k in seen: continue; seen.add(k)
            if tn in known_tools:
                calls.append(ToolCall(name=tn, arguments=p, source_format='xml_minimax', confidence=0.9))

    tnre = re.compile(r'<tool_name>([^<]+)</tool_name>\s*(?:<parameters>|<arguments>)(.*?)(?:</parameters>|</arguments>)', re.DOTALL)
    for m in tnre.finditer(text):
        rn = m.group(1).strip(); ct = m.group(2).strip()
        tn = resolve_tool_name(rn); k = (tn, ct)
        if k in seen: continue; seen.add(k)
        if tn in known_tools:
            try: a = json.loads(ct)
            except: a = _extract_xml_params(ct)
            calls.append(ToolCall(name=tn, arguments=a if a else {'raw': ct}, source_format='xml_tool_name', confidence=0.85))

    tare = re.compile(r'<tool>([^<]+)</tool>\s*<args>(.*?)</args>', re.DOTALL)
    for m in tare.finditer(text):
        rn = m.group(1).strip(); ct = m.group(2).strip()
        tn = resolve_tool_name(rn); k = (tn, ct)
        if k in seen: continue; seen.add(k)
        if tn in known_tools:
            try: a = json.loads(ct)
            except: a = {'raw': ct}
            calls.append(ToolCall(name=tn, arguments=a, source_format='xml_tool_args', confidence=0.85))

    bre = re.compile(r'<invoke\s+name="([^"]+)">(.*?)$', re.DOTALL)
    for m in bre.finditer(text):
        rn = m.group(1).strip(); bl = m.group(2).strip()
        tn = resolve_tool_name(rn); p = _extract_xml_params(bl)
        if p:
            k = (tn, json.dumps(p, sort_keys=True))
            if k not in seen:
                seen.add(k)
                if tn in known_tools:
                    calls.append(ToolCall(name=tn, arguments=p, source_format='xml_bare_invoke', confidence=0.75))

    # <tool_call><name>...</name><arguments>...</arguments></tool_call>
    tc_tag_re = re.compile(r'<tool_call>\s*<name>([^<]+)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>', re.DOTALL)
    for m in tc_tag_re.finditer(text):
        rn = m.group(1).strip(); ct = m.group(2).strip()
        tn = resolve_tool_name(rn); k = (tn, ct)
        if k in seen: continue; seen.add(k)
        if tn in known_tools:
            try: a = json.loads(ct)
            except: a = _extract_xml_params(ct)
            calls.append(ToolCall(name=tn, arguments=a if a else {'raw': ct}, source_format='xml_tool_call_tag', confidence=0.9))

    return calls
def _parse_function_call_syntax(text: str, known_tools: set) -> List[ToolCall]:
    calls = []
    pattern = r'(\w+)\s*\((.*?)\)'
    for match in re.finditer(pattern, text, re.DOTALL):
        func_name = match.group(1)
        args_str = match.group(2).strip()
        if func_name not in known_tools:
            continue
        args = {}
        if args_str:
            try:
                args = json.loads("{" + args_str + "}")
            except json.JSONDecodeError:
                key_val_pattern = r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|\d+(?:\.\d+)?|True|False|None|\[.*?\]|\{.*?\})'
                for kv in re.finditer(key_val_pattern, args_str):
                    key = kv.group(1)
                    val_str = kv.group(2)
                    try:
                        val = json.loads(val_str)
                    except json.JSONDecodeError:
                        val = val_str.strip('"').strip("'")
                    args[key] = val
        calls.append(ToolCall(
            name=func_name,
            arguments=args,
            source_format="function_call",
            confidence=0.75,
        ))
    return calls


def _heuristic_extract(text: str, known_tools: set) -> List[ToolCall]:
    calls = []
    for tool in known_tools:
        patterns = [
            rf'(?:use|call|invoke|run|execute)\s+{re.escape(tool)}\s+(?:with|using|on)\s+(.+?)(?:\.|$|\n)',
            rf'{re.escape(tool)}\s*\(([^)]*)\)',
            rf'["\']?{re.escape(tool)}["\']?\s*:\s*(\{{[^}}]+\}})',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                args_str = match.group(1).strip()
                args = {}
                try:
                    args = json.loads(args_str)
                except (json.JSONDecodeError, ValueError):
                    if "=" in args_str:
                        for part in args_str.split(","):
                            if "=" in part:
                                k, v = part.split("=", 1)
                                args[k.strip()] = v.strip().strip("\"'")
                calls.append(ToolCall(
                    name=tool,
                    arguments=args,
                    source_format="heuristic",
                    confidence=0.5,
                ))
    return calls


def normalize_tool_calls(response_text: str, known_tools: Optional[List[str]] = None) -> List[ToolCall]:
    if not response_text or not response_text.strip():
        return []
    # Strip <think>...</think> and reasoning blocks before tool parsing so thoughts don't trigger false tools
    response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)
    response_text = re.sub(r">\s*\*Thinking:\*.*?(?=\n\n|\Z)", "", response_text, flags=re.DOTALL)
    tools_set = set(known_tools) if known_tools else set()
    all_calls: List[ToolCall] = []
    seen = set()
    json_calls = _parse_json_protocol(response_text, tools_set)
    for c in json_calls:
        key = (c.name, json.dumps(c.arguments, sort_keys=True))
        if key not in seen:
            seen.add(key)
            all_calls.append(c)
    xml_calls = _parse_xml_tool_calls(response_text, tools_set)
    for c in xml_calls:
        key = (c.name, json.dumps(c.arguments, sort_keys=True))
        if key not in seen:
            seen.add(key)
            all_calls.append(c)
    func_calls = _parse_function_call_syntax(response_text, tools_set)
    for c in func_calls:
        key = (c.name, json.dumps(c.arguments, sort_keys=True))
        if key not in seen:
            seen.add(key)
            all_calls.append(c)
    if not all_calls and tools_set:
        heuristic_calls = _heuristic_extract(response_text, tools_set)
        for c in heuristic_calls:
            key = (c.name, json.dumps(c.arguments, sort_keys=True))
            if key not in seen:
                seen.add(key)
                all_calls.append(c)
    all_calls.sort(key=lambda c: c.confidence, reverse=True)
    return all_calls


def extract_final_answer(response_text: str) -> Optional[str]:
    if not response_text:
        return None
    patterns = [
        r'(?:final|answer|result|output)\s*(?:is|:)\s*["\']?(.+?)["\']?\s*(?:\.|$|\n)',
        r'(?:the)\s+(?:answer|result|final)\s+(?:is|:)\s*(.+?)(?:\.|$|\n)',
        r'(?:ANSWER|RESULT|FINAL)\s*[:=]\s*(.+?)(?:\.|$|\n)',
    ]
    for pattern in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return response_text.strip() if len(response_text.strip()) < 500 else None


def is_tool_call_response(response_text: str, known_tools: Optional[List[str]] = None) -> bool:
    if not response_text:
        return False
    tool_indicators = [
        r'"action"\s*:\s*"tool"',
        r'"tool"\s*:\s*"[^"]+"',
        r'"name"\s*:\s*"[^"]+"\s*,\s*"arguments"',
        r'<minimax:toolcall>',
        r'<tool_call>',
        r'<invoke\s+name=',
    ]
    for indicator in tool_indicators:
        if re.search(indicator, response_text):
            return True
    if known_tools:
        tools_set = set(known_tools)
        func_pattern = r'(\w+)\s*\('
        for match in re.finditer(func_pattern, response_text):
            if match.group(1) in tools_set:
                return True
    return False
