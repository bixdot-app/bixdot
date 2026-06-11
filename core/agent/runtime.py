# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Agent Runtime

Uses a two-phase approach compatible with llama3.2 via Ollama:

Phase 1 — Tool Detection:
  Send user message with tool definitions. If llama3.2 calls a tool,
  execute it and collect the result.

Phase 2 — Synthesis:
  Send tool results back as context and ask the model to give a
  final plain-text answer. This avoids the loop where smaller models
  keep calling tools instead of responding.
"""
import os
from pathlib import Path
from pydantic import BaseModel

from core.agent.llm import LLMAdapter
from core.agent.permissions import Capability, get_permission_store
from core.audit.logger import AuditEvent, get_audit_logger
from core.agent.paths import resolve_path, get_system_context


# ─── Models ───────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class AgentSession(BaseModel):
    session_id: str
    user_id: str
    messages: list[Message] = []
    llm_backend: str = "ollama"

class AgentResponse(BaseModel):
    message: str
    tool_calls_made: list[str] = []
    permissions_requested: list[str] = []
    session_id: str


# ─── Tool Definitions ─────────────────────────────────────────────────────────

BUILTIN_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the text contents of a file. Requires fs:read permission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full file path. Use ~ for home directory."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write text to a file. Creates file if needed. Requires fs:write permission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full file path."},
                "content": {"type": "string", "description": "Text content to write."}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory. Requires fs:read permission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path. Use ~ for home directory."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "search_files",
        "description": "Find files by name pattern. Requires fs:read permission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to search."},
                "pattern": {"type": "string", "description": "Pattern like '*.pdf', '*.txt', 'report*'"}
            },
            "required": ["directory", "pattern"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for current information. Requires net:fetch permission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Results (1-5)", "default": 3}
            },
            "required": ["query"]
        }
    },
    {
        "name": "run_command",
        "description": (
            "Run a safe terminal command from the allowlist. "
            "ONLY use when user explicitly asks to run a command, check a version, or use a specific CLI tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run (e.g. 'python --version', 'git status', 'pip list')",
                },
                "cwd":     {"type": "string", "description": "Working directory (optional, defaults to home)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "get_events",
        "description": (
            "Get upcoming calendar events. "
            "Only use when user asks about their calendar, schedule, or upcoming events."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to look (default 7)",
                    "default": 7,
                }
            }
        }
    },
    {
        "name": "create_event",
        "description": (
            "Create a new calendar event. "
            "Only use when user explicitly asks to create/add/schedule an event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":            {"type": "string",  "description": "Event title"},
                "date":             {"type": "string",  "description": "Date in YYYY-MM-DD format"},
                "time":             {"type": "string",  "description": "Time in HH:MM format (24h)"},
                "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 60)"},
                "description":      {"type": "string",  "description": "Optional event description"},
                "location":         {"type": "string",  "description": "Optional location"}
            },
            "required": ["title", "date", "time"]
        }
    },
    {
        "name": "remember",
        "description": (
            "Save a fact, preference, or note to persistent memory. "
            "Use when user says 'remember that', 'note that', 'I prefer', 'my name is', "
            "'always use', 'never use', or shares personal information to keep."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content":  {"type": "string", "description": "The fact or preference to remember"},
                "category": {"type": "string", "description": "Category: general, preference, fact, task, person, project", "default": "general"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "recall",
        "description": (
            "Search memory for relevant facts the user has shared. "
            "Use when user asks what you know about them, or when context from past conversations would help."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in memory"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_documents",
        "description": "List documents the user has uploaded for chat.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "search_document",
        "description": (
            "Search an uploaded document for relevant content. "
            "Use when user asks about a file, PDF, report, or uploaded document."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "What to find in the document"},
                "doc_id": {"type": "string", "description": "Document ID (optional — searches all docs if omitted)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_github_repos",
        "description": "List the user's GitHub repositories. Use when user asks about their repos.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "list_github_issues",
        "description": "List open issues for a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":  {"type": "string", "description": "Repository in owner/repo format"},
                "state": {"type": "string", "description": "Issue state: open, closed, all", "default": "open"}
            },
            "required": ["repo"]
        }
    },
    {
        "name": "read_github_issue",
        "description": "Read the full details of a GitHub issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":         {"type": "string",  "description": "Repository in owner/repo format"},
                "issue_number": {"type": "integer", "description": "Issue number"}
            },
            "required": ["repo", "issue_number"]
        }
    },
    {
        "name": "deep_research",
        "description": (
            "Perform deep research on a topic: plans sub-queries, searches the web, "
            "fetches pages, and synthesises a comprehensive report. "
            "Use for 'research', 'investigate', 'deep dive', 'comprehensive report', "
            "'find out everything about', 'in depth analysis'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The research question or topic"}
            },
            "required": ["question"]
        }
    },
]

TOOL_CAPABILITY_MAP = {
    "read_file":          Capability.FS_READ,
    "write_file":         Capability.FS_WRITE,
    "list_directory":     Capability.FS_READ,
    "search_files":       Capability.FS_READ,
    "web_search":         Capability.NET_FETCH,
    "run_command":        Capability.EXEC_SHELL,
    "get_events":         Capability.CALENDAR_READ,
    "create_event":       Capability.CALENDAR_WRITE,
    "remember":           Capability.MEMORY_WRITE,
    "recall":             Capability.MEMORY_READ,
    "list_documents":     Capability.DOCS_READ,
    "search_document":    Capability.DOCS_READ,
    "list_github_repos":  Capability.GITHUB_READ,
    "list_github_issues": Capability.GITHUB_READ,
    "read_github_issue":  Capability.GITHUB_READ,
    "deep_research":      Capability.NET_FETCH,
}

def get_system_prompt() -> str:
    """Build system prompt with actual filesystem context."""
    ctx = get_system_context()
    return f"""You are BixDot, a personal AI agent running on the user's device using Ollama.
No data leaves this machine.

CRITICAL — TOOL USE RULES (read carefully):
- Only call a tool when the user EXPLICITLY asks you to read a file, list a folder, search files,
  write a file, or search the web.
- For normal conversation, questions, sharing personal facts, or opinions — respond directly. Do NOT call any tool.
- Examples where you must NOT use tools:
  * "my favourite colour is blue" → just acknowledge it
  * "I love my dog Hazel" → just respond warmly
  * "what do you think about X" → just answer
  * "tell me a joke" → just tell one
- Examples where you SHOULD use tools:
  * "what files are in my Documents?" → use list_directory
  * "search the web for Ollama news" → use web_search
  * "read my notes.txt file" → use read_file
  * "create a file called todo.txt" → use write_file

When you have tool results, summarise them clearly and concisely.

{ctx}

When the user asks about their Documents, Downloads, Desktop, Videos, Pictures or Music,
use the exact paths listed above. Do not guess paths."""

# ─── Block helpers ─────────────────────────────────────────────────────────────

def _type(b):  return b.get("type")  if isinstance(b, dict) else getattr(b, "type",  None)
def _text(b):  return b.get("text","") if isinstance(b, dict) else getattr(b, "text",  "")
def _id(b):    return b.get("id")    if isinstance(b, dict) else getattr(b, "id",    None)
def _name(b):  return b.get("name")  if isinstance(b, dict) else getattr(b, "name",  None)
def _input(b): return b.get("input",{}) if isinstance(b, dict) else getattr(b, "input", {})



# ─── Message Classifier ───────────────────────────────────────────────────────

# Keywords that signal the user wants a tool-based action
_TOOL_KEYWORDS = (
    # filesystem
    "read", "open", "load", "show me", "what's in", "whats in",
    "list", "folder", "directory", "files in", "file in",
    "find file", "search file", "search for file",
    "write", "create file", "save file", "make file", "create a file",
    "delete file", "rename",
    # web
    "search the web", "search web", "google", "look up", "lookup",
    "find out", "what is the latest", "latest news", "current news",
    "web search", "browse",
    # terminal
    "run", "execute", "command", "terminal", "cmd", "shell",
    "python ", "pip ", "git ", "node ", "npm ", "ollama ",
    "version", "--version", "-v",
    # calendar
    "calendar", "schedule", "event", "appointment", "meeting",
    "what's on", "whats on", "my day", "upcoming", "remind",
    "book", "create event", "add event", "new event", "schedule a",
    # memory
    "remember", "recall", "note that", "keep in mind", "i prefer",
    "my name is", "always use", "never use", "forget",
    "what do you know about", "what have i told you",
    # documents
    "document", "pdf", "upload", "my file", "that report", "the report",
    "summarise", "summarize", "extract from", "what does the", "according to",
    # github
    "github", "repo", "repository", "issue", "pull request", "pr",
    "commit", "branch", "my repos", "open issues",
    # research
    "research", "investigate", "deep dive", "comprehensive", "report on",
    "find out everything", "in depth", "analyse", "analyze",
)

def _needs_tools(message: str) -> bool:
    """
    Return True only if the message clearly requests a file or web action.
    For everything else (chat, questions, personal statements) return False.
    This prevents llama3.2 from calling tools on conversational messages.
    """
    lower = message.lower()
    return any(kw in lower for kw in _TOOL_KEYWORDS)

# ─── Agent Runtime ────────────────────────────────────────────────────────────

class AgentRuntime:
    MAX_TOOL_ROUNDS = 5

    def __init__(self, permission_store=None, audit_logger=None):
        self.permissions = permission_store or get_permission_store()
        self.audit       = audit_logger       or get_audit_logger()

    async def run(self, session: AgentSession, user_message: str) -> AgentResponse:
        session.messages.append(Message(role="user", content=user_message))
        self.audit.log(AuditEvent.AGENT_QUERY,
                       {"preview": user_message[:100], "session_id": session.session_id},
                       user_id=session.user_id)

        llm = LLMAdapter(backend=session.llm_backend, user_id=session.user_id)
        tool_calls_made      = []
        permissions_requested = []
        collected_results    = []   # gather tool results before synthesis
        rounds = 0

        # ── Memory injection: prepend relevant memories before Phase 1 ───────
        try:
            from core.skills.memory.store import search_memories
            memories = search_memories(session.user_id, user_message, limit=5)
            if memories:
                memory_ctx = "Relevant memories about this user:\n" + "\n".join(
                    f"- [{m['category']}] {m['content']}" for m in memories
                )
                # Inject as a system-level user turn at the start of history
                if not session.messages or session.messages[0].content != memory_ctx:
                    session.messages.insert(len(session.messages) - 1,
                                            Message(role="user", content=f"[MEMORY CONTEXT]\n{memory_ctx}"))
                    session.messages.insert(len(session.messages) - 1,
                                            Message(role="assistant", content="Noted, I have that context."))
        except Exception:
            pass  # Memory errors must never break the main agent loop

        # ── Phase 1: tool calling loop ───────────────────────────────────────
        while rounds < self.MAX_TOOL_ROUNDS:
            rounds += 1

            messages = [{"role": m.role, "content": m.content}
                        for m in session.messages]

            # Only give the model tools if the message actually needs them.
            # Passing tools to llama3.2 for conversational messages causes it
            # to call tools inappropriately — stripping them forces plain text.
            active_tools = BUILTIN_TOOLS if _needs_tools(user_message) else None
            response = await llm.chat(
                messages=messages,
                system=get_system_prompt(),
                tools=active_tools,
            )

            # Filter out null/invalid tool calls that confused models emit for plain conversation
            tool_uses = [
                b for b in response["content"]
                if _type(b) == "tool_use"
                and _name(b) not in (None, "null", "", "none")
            ]

            # No tool calls → model gave a final answer
            if not tool_uses:
                final_text = " ".join(
                    _text(b) for b in response["content"] if _type(b) == "text"
                ).strip()
                # Guard: if model returned raw JSON or tool artifact, treat as empty
                if final_text.startswith('{"') or final_text.startswith("{'"):
                    final_text = ""

                if not final_text and collected_results:
                    # Model gave empty response but we have results — synthesise
                    final_text = await self._synthesise(
                        llm, user_message, collected_results
                    )

                if not final_text:
                    final_text = "Done."

                session.messages.append(Message(role="assistant", content=final_text))
                self.audit.log(AuditEvent.AGENT_RESPONSE,
                               {"tools_used": tool_calls_made, "rounds": rounds},
                               user_id=session.user_id)
                return AgentResponse(
                    message=final_text,
                    tool_calls_made=tool_calls_made,
                    permissions_requested=permissions_requested,
                    session_id=session.session_id,
                )

            # Execute tools
            for tool_use in tool_uses:
                tool_name  = _name(tool_use)
                tool_input = _input(tool_use)

                self.audit.log(AuditEvent.AGENT_TOOL_CALL,
                               {"tool": tool_name, "input": tool_input},
                               user_id=session.user_id)

                required_cap = TOOL_CAPABILITY_MAP.get(tool_name)
                if required_cap and not self.permissions.check("builtin", required_cap):
                    permissions_requested.append(required_cap.value)
                    # Return immediately — UI will ask user to grant then retry
                    return AgentResponse(
                        message="Permission required.",
                        tool_calls_made=tool_calls_made,
                        permissions_requested=list(set(permissions_requested)),
                        session_id=session.session_id,
                    )

                result = await self._execute_tool(tool_name, tool_input, session.user_id)
                tool_calls_made.append(tool_name)
                collected_results.append({"tool": tool_name, "result": result})

            # After tools: synthesise immediately rather than looping
            # This prevents llama3.2 from going into a tool-calling loop
            final_text = await self._synthesise(llm, user_message, collected_results)
            session.messages.append(Message(role="assistant", content=final_text))
            self.audit.log(AuditEvent.AGENT_RESPONSE,
                           {"tools_used": tool_calls_made, "rounds": rounds},
                           user_id=session.user_id)
            return AgentResponse(
                message=final_text,
                tool_calls_made=tool_calls_made,
                permissions_requested=permissions_requested,
                session_id=session.session_id,
            )

        # Fallback
        return AgentResponse(
            message="I took too many steps. Please try a simpler request.",
            tool_calls_made=tool_calls_made,
            permissions_requested=permissions_requested,
            session_id=session.session_id,
        )

    async def _synthesise(self, llm: LLMAdapter, original_question: str,
                          results: list[dict]) -> str:
        """
        After tools run, ask the model to give a clean final answer.
        No tools passed — forces a text response.
        """
        context = "\n\n".join(
            f"[{r['tool']} result]\n{r['result']}" for r in results
        )
        synthesis_prompt = (
            f"The user asked: {original_question}\n\n"
            f"Here are the results from the tools you used:\n\n"
            f"{context}\n\n"
            f"Now give the user a clear, helpful answer based on these results."
        )
        response = await llm.chat(
            messages=[{"role": "user", "content": synthesis_prompt}],
            system=get_system_prompt(),
            tools=None,  # No tools — forces plain text answer
        )
        text = " ".join(
            _text(b) for b in response["content"] if _type(b) == "text"
        ).strip()
        return text or context[:500]  # Fallback: return raw result

    # ── Tool execution ────────────────────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, tool_input: dict, user_id: str) -> str:
        try:
            if tool_name == "read_file":
                return await self._read_file(tool_input.get("path", ""), user_id)
            elif tool_name == "write_file":
                return await self._write_file(
                    tool_input.get("path", ""), tool_input.get("content", ""), user_id)
            elif tool_name == "list_directory":
                return await self._list_directory(tool_input.get("path", "~"), user_id)
            elif tool_name == "search_files":
                return await self._search_files(
                    tool_input.get("directory", "~"), tool_input.get("pattern", "*"), user_id)
            elif tool_name == "web_search":
                return await self._web_search(
                    tool_input.get("query", ""), tool_input.get("max_results", 3), user_id)
            elif tool_name == "run_command":
                return await self._run_command(tool_input.get("command",""), tool_input.get("cwd"), user_id)
            elif tool_name == "get_events":
                days = int(tool_input.get("days_ahead", 7))
                return await self._get_events(days, user_id)
            elif tool_name == "create_event":
                return await self._create_event(tool_input, user_id)
            elif tool_name == "remember":
                return await self._remember(tool_input.get("content", ""), tool_input.get("category", "general"), user_id)
            elif tool_name == "recall":
                return await self._recall(tool_input.get("query", ""), user_id)
            elif tool_name == "list_documents":
                return await self._list_documents(user_id)
            elif tool_name == "search_document":
                return await self._search_document(tool_input.get("query", ""), tool_input.get("doc_id"), user_id)
            elif tool_name == "list_github_repos":
                return await self._list_github_repos(user_id)
            elif tool_name == "list_github_issues":
                return await self._list_github_issues(tool_input.get("repo", ""), tool_input.get("state", "open"), user_id)
            elif tool_name == "read_github_issue":
                return await self._read_github_issue(tool_input.get("repo", ""), int(tool_input.get("issue_number", 0)), user_id)
            elif tool_name == "deep_research":
                return await self._deep_research(tool_input.get("question", ""), user_id)
            return f"Unknown tool: {tool_name}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Tool error: {e}"

    def _resolve(self, path: str) -> Path:
        return resolve_path(path)

    def _is_safe_path(self, p: Path) -> bool:
        """Block paths outside the user's home directory to prevent traversal attacks."""
        try:
            p.resolve().relative_to(Path.home())
            return True
        except ValueError:
            return False

    async def _read_file(self, path: str, user_id: str) -> str:
        if not path:
            return "Error: no path"
        try:
            p = self._resolve(path)
            if not self._is_safe_path(p):
                self.audit.log(AuditEvent.PERMISSION_DENIED,
                               {"tool": "read_file", "path": str(p), "reason": "outside home"},
                               user_id=user_id)
                return "Access denied: path outside home directory"
            if not p.exists():
                return f"Not found: {path}"
            if not p.is_file():
                return f"Not a file: {path}"
            if p.stat().st_size > 1_048_576:
                return "File too large (max 1MB)"
            self.audit.log(AuditEvent.FILE_READ, {"path": str(p)}, user_id=user_id)
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Read error: {e}"

    async def _write_file(self, path: str, content: str, user_id: str) -> str:
        if not path:
            return "Error: no path"
        try:
            p = self._resolve(path)
            if not self._is_safe_path(p):
                self.audit.log(AuditEvent.PERMISSION_DENIED,
                               {"tool": "write_file", "path": str(p), "reason": "outside home"},
                               user_id=user_id)
                return "Access denied: path outside home directory"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            self.audit.log(AuditEvent.FILE_WRITE, {"path": str(p), "size": len(content)}, user_id=user_id)
            return f"Written: {p} ({len(content):,} chars)"
        except Exception as e:
            return f"Write error: {e}"

    async def _list_directory(self, path: str, user_id: str) -> str:
        try:
            p = self._resolve(path or "~")
            if not self._is_safe_path(p):
                return "Access denied: path outside home directory"
            if not p.exists():
                return f"Not found: {path}"
            if not p.is_dir():
                return f"Not a directory: {path}"
            entries = []
            for e in sorted(p.iterdir()):
                if e.is_dir():
                    entries.append(f"📁 {e.name}/")
                else:
                    sz = e.stat().st_size
                    entries.append(f"📄 {e.name} ({sz:,} B)" if sz < 1024 else f"📄 {e.name} ({sz//1024:,} KB)")
            self.audit.log(AuditEvent.FILE_READ, {"path": str(p), "count": len(entries)}, user_id=user_id)
            return f"{p}:\n" + ("\n".join(entries) if entries else "(empty)")
        except Exception as e:
            return f"List error: {e}"

    async def _search_files(self, directory: str, pattern: str, user_id: str) -> str:
        import fnmatch
        try:
            p = self._resolve(directory)
            if not self._is_safe_path(p):
                return "Access denied: path outside home directory"
            if not p.is_dir():
                return f"Not a directory: {directory}"
            matches = []
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if fnmatch.fnmatch(f.lower(), pattern.lower()):
                        matches.append(str(Path(root) / f))
                if len(matches) >= 50:
                    break
            self.audit.log(
                AuditEvent.FILE_READ,
                {"dir": str(p), "pattern": pattern, "found": len(matches)},
                user_id=user_id,
            )
            if not matches:
                return f"No files matching '{pattern}' in {p}"
            return f"Found {len(matches)} file(s):\n" + "\n".join(matches[:50])
        except Exception as e:
            return f"Search error: {e}"

    async def _web_search(self, query: str, max_results: int, user_id: str) -> str:
        self.audit.log(AuditEvent.NET_REQUEST, {"query": query}, user_id=user_id)
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=min(int(max_results), 5)))
            if not results:
                return f"No results for: {query}"
            out = f"Search results for '{query}':\n\n"
            for i, r in enumerate(results, 1):
                href = r.get('href', r.get('url', ''))
                out += f"{i}. {r.get('title','')}\n   {href}\n   {r.get('body','')[:200]}\n\n"
            return out.strip()
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Search error: {type(e).__name__}: {e}"

    async def _run_command(self, command: str, cwd: str | None, user_id: str) -> str:
        from core.skills.terminal.sandbox import run_command
        self.audit.log(AuditEvent.AGENT_TOOL_CALL, {"tool": "terminal", "command": command}, user_id=user_id)
        result = run_command(command, cwd)
        if result["blocked"]:
            return f"⛔ Blocked: {result['blocked']}"
        out = ""
        if result["stdout"]:
            out += result["stdout"]
        if result["stderr"]:
            out += ("\n" if out else "") + f"[stderr] {result['stderr']}"
        if not out:
            out = f"(exit {result['exit']})"
        return out.strip()

    async def _get_events(self, days_ahead: int, user_id: str) -> str:
        try:
            from core.skills.calendar.store import load_active_provider
            from core.skills.calendar.google_cal import GoogleCalendarProvider
            from core.skills.calendar.ical_cal import ICalProvider

            result = load_active_provider(user_id)
            if not result:
                return "No calendar connected. Please set one up in Settings \u2192 Calendar."

            name, config = result
            if name == "google":
                provider = GoogleCalendarProvider(config)
            elif name == "ical":
                provider = ICalProvider(config)
            else:
                return f"Unknown calendar provider: {name}"

            events = await provider.get_events(days_ahead=days_ahead)
            if not events:
                return f"No events in the next {days_ahead} days."

            lines = [f"You have {len(events)} upcoming event(s):"]
            for e in events:
                lines.append(f"\u2022 {e.friendly()}")
                if e.location:
                    lines.append(f"  \U0001f4cd {e.location}")

            if hasattr(provider, 'to_config'):
                from core.skills.calendar.store import save_provider
                save_provider(user_id, name, provider.to_config())

            return "\n".join(lines)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Calendar error: {type(e).__name__}: {e}"

    async def _remember(self, content: str, category: str, user_id: str) -> str:
        if not content.strip():
            return "Error: nothing to remember"
        try:
            from core.skills.memory.store import save_memory
            save_memory(user_id, content.strip(), category)
            self.audit.log(AuditEvent.AGENT_TOOL_CALL, {"tool": "remember", "category": category}, user_id=user_id)
            return f"Remembered: {content[:100]}"
        except Exception as e:
            return f"Memory error: {e}"

    async def _recall(self, query: str, user_id: str) -> str:
        try:
            from core.skills.memory.store import search_memories
            memories = search_memories(user_id, query, limit=10)
            if not memories:
                return "No relevant memories found."
            lines = [f"[{m['category']}] {m['content']}" for m in memories]
            return "Memories:\n" + "\n".join(lines)
        except Exception as e:
            return f"Recall error: {e}"

    async def _list_documents(self, user_id: str) -> str:
        try:
            from core.skills.documents.store import load_documents
            docs = load_documents(user_id)
            if not docs:
                return "No documents uploaded yet."
            lines = [f"- {d['filename']} (id: {d['id']}, {d['size_bytes']//1024} KB)" for d in docs]
            return f"{len(docs)} document(s):\n" + "\n".join(lines)
        except Exception as e:
            return f"Documents error: {e}"

    async def _search_document(self, query: str, doc_id: str | None, user_id: str) -> str:
        try:
            from core.skills.documents.store import load_documents, load_document
            from core.skills.documents.parser import chunk_text, search_chunks
            if doc_id:
                doc = load_document(doc_id, user_id)
                docs = [doc] if doc else []
            else:
                docs = [load_document(d["id"], user_id) for d in load_documents(user_id)]
                docs = [d for d in docs if d]
            if not docs:
                return "No documents found."
            all_relevant = []
            for doc in docs:
                chunks = chunk_text(doc["text_content"])
                relevant = search_chunks(chunks, query, top_k=3)
                for chunk in relevant:
                    all_relevant.append(f"[{doc['filename']}]\n{chunk}")
            if not all_relevant:
                return f"No relevant content found for: {query}"
            return "\n\n---\n\n".join(all_relevant[:5])
        except Exception as e:
            return f"Document search error: {e}"

    async def _list_github_repos(self, user_id: str) -> str:
        try:
            from core.skills.github.store import load_github_token
            from core.skills.github.client import GitHubClient
            token = load_github_token(user_id)
            if not token:
                return "GitHub not connected. Please connect via Settings → GitHub."
            repos = await GitHubClient(token).list_repos()
            if not repos:
                return "No repositories found."
            lines = [f"- {r['full_name']} ({'private' if r['private'] else 'public'}) — {r.get('description','')}" for r in repos]
            return f"{len(repos)} repo(s):\n" + "\n".join(lines)
        except Exception as e:
            return f"GitHub error: {e}"

    async def _list_github_issues(self, repo: str, state: str, user_id: str) -> str:
        try:
            from core.skills.github.store import load_github_token
            from core.skills.github.client import GitHubClient
            token = load_github_token(user_id)
            if not token:
                return "GitHub not connected."
            issues = await GitHubClient(token).list_issues(repo, state=state)
            if not issues:
                return f"No {state} issues in {repo}."
            lines = [f"#{i['number']} {i['title']} ({', '.join(i['labels']) or 'no labels'})" for i in issues]
            return f"{len(issues)} {state} issue(s) in {repo}:\n" + "\n".join(lines)
        except Exception as e:
            return f"GitHub error: {e}"

    async def _read_github_issue(self, repo: str, issue_number: int, user_id: str) -> str:
        try:
            from core.skills.github.store import load_github_token
            from core.skills.github.client import GitHubClient
            token = load_github_token(user_id)
            if not token:
                return "GitHub not connected."
            issue = await GitHubClient(token).get_issue(repo, issue_number)
            return (f"#{issue['number']}: {issue['title']}\n"
                    f"State: {issue['state']} | Author: {issue['user']} | Labels: {', '.join(issue['labels']) or 'none'}\n"
                    f"Created: {issue['created_at']}\n\n{issue.get('body', '(no body)')}")
        except Exception as e:
            return f"GitHub error: {e}"

    async def _deep_research(self, question: str, user_id: str) -> str:
        if not question.strip():
            return "Error: question is required for research"
        try:
            from core.skills.research.researcher import deep_research
            llm = LLMAdapter(backend="ollama", user_id=user_id)
            self.audit.log(AuditEvent.NET_REQUEST, {"tool": "deep_research", "question": question[:100]}, user_id=user_id)
            return await deep_research(question, llm, user_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Research error: {e}"

    async def _create_event(self, tool_input: dict, user_id: str) -> str:
        try:
            from datetime import datetime, timedelta
            from core.skills.calendar.store import load_active_provider, save_provider
            from core.skills.calendar.google_cal import GoogleCalendarProvider
            result = load_active_provider(user_id)
            if not result:
                return "No calendar connected. Please set one up in Settings → Calendar."
            name, config = result
            if name != "google":
                return "Event creation is only available with Google Calendar. Local .ics files are read-only."
            provider = GoogleCalendarProvider(config)
            title    = tool_input.get("title", "New Event")
            date     = tool_input.get("date", "")
            time     = tool_input.get("time", "09:00")
            duration = int(tool_input.get("duration_minutes", 60))
            desc     = tool_input.get("description", "")
            location = tool_input.get("location", "")
            if not date:
                return "Please specify a date (YYYY-MM-DD format)."
            start = datetime.fromisoformat(f"{date}T{time}:00+00:00")
            end   = start + timedelta(minutes=duration)
            event = await provider.create_event(title, start, end, desc, location)
            save_provider(user_id, name, provider.to_config())
            return f"✓ Created: {event.friendly()}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Create event error: {type(e).__name__}: {e}"
