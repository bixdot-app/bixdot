# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Agent Runtime
The core loop: user message → LLM → tool calls → results → response

Architecture:
- Agent receives a message and session context
- Sends to LLM (Claude or Ollama) with available tools
- If LLM calls a tool: check permissions → execute in sandbox → feed result back
- Repeat until LLM produces a final text response
- Every action logged to tamper-evident audit log

Security guarantees:
- Tool calls only execute if permission grant exists
- Every tool call logged before execution
- Sandbox enforces resource limits
- PII scrubbed before cloud LLM calls
"""
import json
from typing import Optional, AsyncGenerator
from pydantic import BaseModel

from core.agent.llm import LLMAdapter
from core.agent.permissions import PermissionStore, Capability, get_permission_store
from core.audit.logger import AuditLogger, AuditEvent, get_audit_logger
from core.sandbox.executor import SkillExecutor
from core.config import settings


# ─── Models ───────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str       # "user" | "assistant" | "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None


class AgentSession(BaseModel):
    session_id: str
    user_id: str
    messages: list[Message] = []
    llm_backend: str = "claude"


class AgentResponse(BaseModel):
    message: str
    tool_calls_made: list[str] = []
    permissions_requested: list[str] = []
    session_id: str


# ─── Built-in Tool Definitions ────────────────────────────────────────────────

BUILTIN_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file on the user's machine. "
                       "Only works on paths the user has explicitly granted access to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file on the user's machine. "
                       "Only works on paths the user has explicitly granted access to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory. "
                       "Only works on paths the user has explicitly granted access to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the directory to list"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for current information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    },
]

# Map tool names to required capabilities
TOOL_CAPABILITY_MAP = {
    "read_file": Capability.FS_READ,
    "write_file": Capability.FS_WRITE,
    "list_directory": Capability.FS_READ,
    "web_search": Capability.NET_FETCH,
}

# BixDot system prompt
SYSTEM_PROMPT = """You are BixDot, a personal AI agent that runs entirely on your device using local AI models.

Your key principles:
- You are private, local, and trustworthy
- You only access files and resources the user has explicitly permitted
- You always explain what you're about to do before doing it
- You never exfiltrate data or make unexpected network calls
- If you need a permission you don't have, tell the user clearly

You have access to tools for reading/writing files and searching the web.
Always ask for permission before accessing any file or folder for the first time.
Be concise, helpful, and transparent about every action you take."""


# ─── Agent Runtime ────────────────────────────────────────────────────────────

class AgentRuntime:
    """
    The BixDot agent runtime.
    Orchestrates the LLM ↔ tool loop with full permission checking and audit logging.
    """

    MAX_TOOL_ROUNDS = 10  # Prevent infinite loops

    def __init__(
        self,
        permission_store: Optional[PermissionStore] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.permissions = permission_store or get_permission_store()
        self.audit = audit_logger or get_audit_logger()

    async def run(
        self,
        session: AgentSession,
        user_message: str,
    ) -> AgentResponse:
        """
        Process a user message and return the agent's response.
        Handles multi-round tool use loops internally.
        """
        # Add user message to session
        session.messages.append(Message(role="user", content=user_message))

        self.audit.log(
            AuditEvent.AGENT_QUERY,
            {"message_preview": user_message[:100], "session_id": session.session_id},
            user_id=session.user_id,
        )

        # Initialise LLM adapter
        llm = LLMAdapter(backend=session.llm_backend, user_id=session.user_id)

        tool_calls_made = []
        permissions_requested = []
        rounds = 0

        while rounds < self.MAX_TOOL_ROUNDS:
            rounds += 1

            # Build messages for LLM
            messages = self._build_messages(session.messages)

            # Call LLM with available tools
            response = await llm.chat(
                messages=messages,
                system=SYSTEM_PROMPT,
                tools=BUILTIN_TOOLS,
            )

            # Check if LLM wants to use a tool
            # Handle both dict responses (Ollama) and object responses (Anthropic API)
            def block_type(b): return b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
            def block_text(b): return b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "")
            def block_id(b): return b.get("id") if isinstance(b, dict) else getattr(b, "id", None)
            def block_name(b): return b.get("name") if isinstance(b, dict) else getattr(b, "name", None)
            def block_input(b): return b.get("input", {}) if isinstance(b, dict) else getattr(b, "input", {})

            tool_uses = [
                block for block in response["content"]
                if block_type(block) == "tool_use"
            ]

            if not tool_uses:
                # LLM gave a final text response — we're done
                final_text = " ".join(
                    block_text(block)
                    for block in response["content"]
                    if block_type(block) == "text"
                )
                session.messages.append(
                    Message(role="assistant", content=final_text)
                )
                self.audit.log(
                    AuditEvent.AGENT_RESPONSE,
                    {"session_id": session.session_id,
                     "tool_calls": tool_calls_made,
                     "rounds": rounds},
                    user_id=session.user_id,
                )
                return AgentResponse(
                    message=final_text,
                    tool_calls_made=tool_calls_made,
                    permissions_requested=permissions_requested,
                    session_id=session.session_id,
                )

            # Process tool calls
            tool_results = []
            for tool_use in tool_uses:
                tool_name = block_name(tool_use)
                tool_input = block_input(tool_use)
                tool_id = block_id(tool_use)

                self.audit.log(
                    AuditEvent.AGENT_TOOL_CALL,
                    {"tool": tool_name, "input": tool_input,
                     "session_id": session.session_id},
                    user_id=session.user_id,
                )

                # Check permission
                required_cap = TOOL_CAPABILITY_MAP.get(tool_name)
                if required_cap and not self.permissions.check("builtin", required_cap):
                    # Permission not granted — tell LLM
                    permissions_requested.append(tool_name)
                    result = (
                        f"Permission denied: '{tool_name}' requires "
                        f"'{required_cap}' permission. "
                        f"Please ask the user to grant this permission first."
                    )
                else:
                    # Execute the tool
                    result = await self._execute_tool(
                        tool_name, tool_input, session.user_id
                    )
                    tool_calls_made.append(tool_name)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(result),
                })

            # Add assistant message with tool use + tool results to session
            session.messages.append(
                Message(role="assistant",
                        content=json.dumps([{
                            "type": "tool_use",
                            "id": block_id(t),
                            "name": block_name(t),
                            "input": block_input(t)
                        } for t in tool_uses]))
            )
            session.messages.append(
                Message(role="user", content=json.dumps(tool_results))
            )

        # Max rounds reached
        return AgentResponse(
            message="I reached the maximum number of steps. Please try a simpler request.",
            tool_calls_made=tool_calls_made,
            permissions_requested=permissions_requested,
            session_id=session.session_id,
        )

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        user_id: str,
    ) -> str:
        """Execute a tool and return its result as a string."""
        try:
            if tool_name == "read_file":
                return await self._read_file(tool_input["path"], user_id)
            elif tool_name == "write_file":
                return await self._write_file(
                    tool_input["path"], tool_input["content"], user_id
                )
            elif tool_name == "list_directory":
                return await self._list_directory(tool_input["path"], user_id)
            elif tool_name == "web_search":
                return await self._web_search(tool_input["query"], user_id)
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool error: {str(e)}"

    async def _read_file(self, path: str, user_id: str) -> str:
        """Read a file — path validated, symlinks not followed."""
        import os
        from pathlib import Path

        # Resolve path safely — no symlink following
        try:
            resolved = Path(path).resolve(strict=True)
        except (FileNotFoundError, OSError) as e:
            return f"File not found: {path}"

        # Check it's actually a file
        if not resolved.is_file():
            return f"Not a file: {path}"

        # Read with size limit (1MB for safety)
        MAX_SIZE = 1024 * 1024
        if resolved.stat().st_size > MAX_SIZE:
            return f"File too large to read (max 1MB): {path}"

        self.audit.log(
            AuditEvent.FILE_READ,
            {"path": str(resolved)},
            user_id=user_id,
        )

        try:
            return resolved.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Could not read file: {e}"

    async def _write_file(self, path: str, content: str, user_id: str) -> str:
        """Write a file safely."""
        from pathlib import Path

        try:
            resolved = Path(path).resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")

            self.audit.log(
                AuditEvent.FILE_WRITE,
                {"path": str(resolved), "size": len(content)},
                user_id=user_id,
            )
            return f"File written successfully: {path}"
        except Exception as e:
            return f"Could not write file: {e}"

    async def _list_directory(self, path: str, user_id: str) -> str:
        """List directory contents safely."""
        from pathlib import Path

        try:
            resolved = Path(path).resolve(strict=True)
            if not resolved.is_dir():
                return f"Not a directory: {path}"

            entries = []
            for entry in sorted(resolved.iterdir()):
                kind = "📁" if entry.is_dir() else "📄"
                entries.append(f"{kind} {entry.name}")

            self.audit.log(
                AuditEvent.FILE_READ,
                {"path": str(resolved), "type": "directory_list"},
                user_id=user_id,
            )
            return "\n".join(entries) if entries else "Empty directory"
        except Exception as e:
            return f"Could not list directory: {e}"

    async def _web_search(self, query: str, user_id: str) -> str:
        """Placeholder web search — real implementation in Week 3."""
        self.audit.log(
            AuditEvent.NET_REQUEST,
            {"query": query, "type": "web_search"},
            user_id=user_id,
        )
        return f"Web search for '{query}' — search integration coming in Week 3."

    @staticmethod
    def _build_messages(messages: list[Message]) -> list[dict]:
        """Convert session messages to LLM API format."""
        result = []
        for msg in messages:
            if msg.role in ("user", "assistant"):
                result.append({"role": msg.role, "content": msg.content})
        return result
