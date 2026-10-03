import json
import pytest
from unittest.mock import MagicMock, patch

from calc_terminal.tool_call_normalizer import (
    normalize_tool_calls,
    resolve_tool_name,
    _repair_json_str,
)
from calc_terminal.workflow_engine import workflow_engine
from calc_terminal import agent
from calc_terminal.agent_runtime import AgentRuntime


class TestAgentMultitaskingAndRecovery:
    def test_user_truncated_writefile_snippet(self):
        user_snippet = '''
> 🔧 **listdirectory**  `portfolio/src/components/workspace` — ✔ completed

> 🔧 **readfile**  `portfolio/src/data/portfolio.ts` — ✔ completed

{"action": "tool", "tool": "writefile", "args": {"path": "portfolio/src/components/workspace/Workspace.tsx", "content": "import React, { useState } from 'react';\\nimport { motion } from 'framer-motion';\\n\\nexport const Workspace = () => {\\n  const [activeTab, setActiveTab] = useState('projects');\\n  return <div>{activeTab}</div>;\\n};\\n activeTab === tab.id\\n                    ? 'text-ac
'''
        calls = normalize_tool_calls(user_snippet, ["write_file", "list_directory", "read_file"])
        assert len(calls) == 1
        assert calls[0].name == "write_file"
        assert calls[0].arguments["path"] == "portfolio/src/components/workspace/Workspace.tsx"
        assert "export const Workspace" in calls[0].arguments["content"]

    def test_nested_braces_in_code_args(self):
        text = '{"action": "tool", "tool": "write_file", "args": {"path": "app.ts", "content": "function test() { if (true) { return { a: 1 }; } }"}}'
        calls = normalize_tool_calls(text, ["write_file"])
        assert len(calls) == 1
        assert calls[0].name == "write_file"
        assert calls[0].arguments["path"] == "app.ts"
        assert calls[0].arguments["content"] == "function test() { if (true) { return { a: 1 }; } }"

    def test_multitasking_multiple_tool_calls_normalized(self):
        text = '''
        {"action": "tool", "tool": "read_file", "args": {"path": "a.txt"}}
        {"action": "tool", "tool": "read_file", "args": {"path": "b.txt"}}
        {"action": "tool", "tool": "list_directory", "args": {"path": "src"}}
        '''
        calls = normalize_tool_calls(text, ["read_file", "list_directory"])
        assert len(calls) == 3
        assert calls[0].name == "read_file" and calls[0].arguments["path"] == "a.txt"
        assert calls[1].name == "read_file" and calls[1].arguments["path"] == "b.txt"
        assert calls[2].name == "list_directory" and calls[2].arguments["path"] == "src"

    def test_workflow_engine_execute_weak_model_action_tool_wrapper(self):
        executed = []

        def mock_executor(tool, args):
            executed.append((tool, args))
            return f"Wrote {args.get('path')}"

        intention = {
            "action": "tool",
            "tool": "writefile",
            "args": {"path": "src/components/workspace/Workspace.tsx", "content": "export const X = 1;"}
        }
        res = workflow_engine.execute_weak_model_action(intention, tool_executor=mock_executor)
        assert res["status"] == "success"
        assert len(executed) == 1
        assert executed[0][0] == "write_file"
        assert executed[0][1]["path"] == "src/components/workspace/Workspace.tsx"

    def test_workflow_engine_parse_weak_model_intention_truncated(self):
        truncated_intention = 'Here is the tool: {"action": "tool", "tool": "write_file", "args": {"path": "test.txt", "content": "hello world'
        extracted = workflow_engine.parse_weak_model_intention(truncated_intention)
        assert extracted is not None
        assert extracted.get("action") == "tool"
        assert extracted.get("tool") == "write_file"
        assert extracted.get("args", {}).get("path") == "test.txt"

    def test_agent_extract_json_recovery(self):
        text = 'Thinking: done\n```json\n{"action": "tool", "tool": "calc", "args": {"expr": "100 * 2"'
        res = agent._extract_json(text)
        assert res is not None
        assert res.get("action") == "tool"
        assert res.get("tool") == "calc"
        assert res.get("args", {}).get("expr") == "100 * 2"

    def test_agent_runtime_extract_json_recovery(self):
        runtime = AgentRuntime({})
        text = 'Result: {"action": "final", "text": "Multitasking completed'
        res = runtime._extract_json(text)
        assert res is not None
        assert res.get("action") == "final"
        assert "Multitasking completed" in res.get("text", "")

    def test_agent_runtime_multitasking_batch_execution(self):
        tools_run = []
        tools = {
            "read_file": {
                "desc": "read a file",
                "run": lambda args: tools_run.append(("read_file", args.get("path"))) or f"content of {args.get('path')}",
            },
            "list_directory": {
                "desc": "list files",
                "run": lambda args: tools_run.append(("list_directory", args.get("path"))) or "file1, file2",
            },
        }
        runtime = AgentRuntime(tools, max_steps=4)
        query_calls = 0

        def mock_query(prompt, system_prompt=None):
            nonlocal query_calls
            query_calls += 1
            if query_calls == 1:
                return (
                    '{"action": "tool", "tool": "read_file", "args": {"path": "file1.txt"}}\n'
                    '{"action": "tool", "tool": "list_directory", "args": {"path": "src"}}'
                )
            return '{"action": "final", "text": "All tasks done!"}'

        final_text, steps, meta = runtime.run("Inspect project files", mock_query, "system prompt")
        assert "All tasks done!" in final_text
        assert len(tools_run) == 2
        assert tools_run[0] == ("read_file", "file1.txt")
        assert tools_run[1] == ("list_directory", "src")
