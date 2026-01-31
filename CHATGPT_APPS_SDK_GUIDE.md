# ChatGPT Apps SDK: Python Backend Guide

Technical reference for building ChatGPT Apps (MCP-based widgets) with **Python/FastAPI** backend.

Based on the [official OpenAI Apps SDK examples](https://github.com/openai/openai-apps-sdk-examples).

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Dependencies](#dependencies)
- [MCP Server Setup](#mcp-server-setup)
- [Tool Registration](#tool-registration)
- [Resource Registration (Widget HTML)](#resource-registration-widget-html)
- [FastAPI Application Factory](#fastapi-application-factory)
- [CORS Configuration](#cors-configuration)
- [Key Gotchas](#key-gotchas)
- [Configuration Reference](#configuration-reference)

---

## Architecture Overview

```
ChatGPT                          Your Server
┌────────────────┐               ┌──────────────────────┐
│  User message  │───────────────>│  FastAPI + FastMCP   │
│       ↓        │               │                      │
│  LLM calls     │               │  1. Tool called      │
│  MCP tool      │<──────────────│  2. Returns:         │
│       ↓        │               │     structuredContent│
│  Fetches HTML  │───────────────>│     + _meta          │
│  resource      │<──────────────│  3. Returns HTML     │
│       ↓        │               └──────────────────────┘
│  Renders in    │
│  iframe with   │
│  toolOutput =  │
│  structuredContent
└────────────────┘
```

**Key insight**: `window.openai.toolOutput` in the widget **IS** the `structuredContent` from your MCP tool response.

---

## Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "mcp>=1.23.0",
    "pydantic>=2.10.0",
]
```

---

## MCP Server Setup

```python
# mcp_server.py
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="your-app-name",
        stateless_http=True,  # REQUIRED for ChatGPT Apps
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,  # For dev with ngrok
        ),
    )
    return mcp
```

**Critical**: `stateless_http=True` is required. ChatGPT does not maintain MCP sessions.

---

## Tool Registration

```python
from mcp.types import CallToolResult, TextContent

TEMPLATE_URI = "ui://widget/main.html"

def _widget_meta():
    """Metadata that tells ChatGPT this tool renders a widget."""
    return {
        "openai/outputTemplate": TEMPLATE_URI,
        "openai/toolInvocation/invoking": "Loading...",
        "openai/toolInvocation/invoked": "Ready",
        "openai/widgetAccessible": True,  # REQUIRED for widget to render!
    }


def register_tools(mcp):
    @mcp.tool(meta=_widget_meta())
    async def your_tool(
        query: str,
        limit: int = 10,
    ) -> CallToolResult:
        """Description shown to the LLM for tool selection."""
        data = {"items": [...], "total": 42}

        return CallToolResult(
            structuredContent={"type": "your-type", "data": data},
            content=[TextContent(type="text", text="Tool completed")],
            _meta=_widget_meta(),
        )
```

### Tool Meta Fields

| Key | Type | Description |
|-----|------|-------------|
| `openai/outputTemplate` | `string` | URI of widget HTML resource (`ui://widget/name.html`) |
| `openai/toolInvocation/invoking` | `string` | Status text while tool runs |
| `openai/toolInvocation/invoked` | `string` | Status text when complete |
| `openai/widgetAccessible` | `boolean` | **REQUIRED for widget to render!** |

### Type Hints → JSON Schema

| Python | JSON Schema |
|--------|-------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `bool` | `{"type": "boolean"}` |
| `Literal["a", "b"]` | `{"enum": ["a", "b"]}` |
| `Optional[T]` | nullable T |

---

## Resource Registration (Widget HTML)

```python
from functools import lru_cache
from pathlib import Path

WIDGET_DIR = Path(__file__).resolve().parent.parent / "public"
TEMPLATE_URI = "ui://widget/main.html"
MIME_TYPE = "text/html+skybridge"


@lru_cache(maxsize=1)
def _load_widget_html() -> str:
    return (WIDGET_DIR / "widget.html").read_text(encoding="utf-8")


def register_resources(mcp):
    @mcp.resource(TEMPLATE_URI, name="Main widget", mime_type=MIME_TYPE)
    async def widget_template() -> str:
        return _load_widget_html()
```

### Resource Requirements

| Field | Value | Notes |
|-------|-------|-------|
| URI | `ui://widget/name.html` | Must use `ui://` scheme |
| MIME type | `text/html+skybridge` | Required for ChatGPT |
| HTML | Self-contained | All JS/CSS must be inlined |

---

## FastAPI Application Factory

```python
# app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .mcp_server import create_mcp_server

def create_app() -> FastAPI:
    mcp = create_mcp_server()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="Your App", lifespan=lifespan)
    
    # Add CORS middleware here
    
    # Mount MCP at "/" (makes endpoint available at /mcp)
    app.mount("/", mcp.streamable_http_app())
    
    return app
```

---

## CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

def add_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "mcp-session-id"],
        expose_headers=["mcp-session-id"],
    )
```

---

## Key Gotchas

### 1. `openai/widgetAccessible: True` is REQUIRED

Without this flag, ChatGPT **will not render your widget** — only text response shows.

```python
def _widget_meta():
    return {
        "openai/outputTemplate": TEMPLATE_URI,
        "openai/toolInvocation/invoking": "Loading...",
        "openai/toolInvocation/invoked": "Ready",
        "openai/widgetAccessible": True,  # <-- REQUIRED!
    }
```

Must be in both:
- Tool registration: `@mcp.tool(meta=_widget_meta())`
- Tool result: `CallToolResult(..., _meta=_widget_meta())`

### 2. `stateless_http=True` is REQUIRED

ChatGPT does not maintain MCP sessions.

### 3. Widget HTML must be self-contained

External `<script src="...">` and `<link href="...">` are blocked by CSP. Inline everything.

### 4. Chrome 142+ local network access flag

If widget doesn't appear with local server:

1. Go to `chrome://flags/`
2. Find `#local-network-access-check`
3. Set to **Disabled**
4. Restart Chrome

### 5. Use `@lru_cache` for widget HTML

```python
@lru_cache(maxsize=1)
def _load_widget_html() -> str:
    return (WIDGET_DIR / "widget.html").read_text(encoding="utf-8")
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8787` | Server port |
| `BASE_URL` | `http://localhost:{PORT}` | Public URL (for ngrok) |

### Complete Minimal Example

```python
# mcp_server.py
from functools import lru_cache
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from pydantic import Field

WIDGET_DIR = Path(__file__).resolve().parent.parent / "public"
TEMPLATE_URI = "ui://widget/main.html"
MIME_TYPE = "text/html+skybridge"


@lru_cache(maxsize=1)
def _load_widget_html() -> str:
    return (WIDGET_DIR / "widget.html").read_text(encoding="utf-8")


def _widget_meta():
    return {
        "openai/outputTemplate": TEMPLATE_URI,
        "openai/toolInvocation/invoking": "Loading...",
        "openai/toolInvocation/invoked": "Ready",
        "openai/widgetAccessible": True,
    }


def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="your-app",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    @mcp.resource(TEMPLATE_URI, name="Widget", mime_type=MIME_TYPE)
    async def widget_resource() -> str:
        return _load_widget_html()

    @mcp.tool(meta=_widget_meta())
    async def your_tool(
        message: str = Field(..., description="Message to display"),
    ) -> CallToolResult:
        """Your tool description for the LLM."""
        return CallToolResult(
            structuredContent={"message": message},
            content=[TextContent(type="text", text=f"Message: {message}")],
            _meta=_widget_meta(),
        )

    return mcp
```

---

## Links

- [OpenAI Apps SDK Examples](https://github.com/openai/openai-apps-sdk-examples)
- [kitchen_sink_server_python](https://github.com/openai/openai-apps-sdk-examples/blob/main/kitchen_sink_server_python/main.py) — Reference Python server
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
