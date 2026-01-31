# ChatGPT Apps SDK: FastAPI + React Cookiecutter Guide

Technical reference for building ChatGPT Apps (MCP-based widgets) with a **Python/FastAPI** backend and **React** frontend.

Based on the [official OpenAI Apps SDK examples](https://github.com/openai/openai-apps-sdk-examples) and real-world implementation findings.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Backend: FastAPI + MCP](#backend-fastapi--mcp)
  - [Dependencies](#dependencies)
  - [MCP Server Setup](#mcp-server-setup)
  - [FastAPI Application Factory](#fastapi-application-factory)
  - [Tool Registration](#tool-registration)
  - [Resource Registration (Widget HTML)](#resource-registration-widget-html)
  - [CORS Configuration](#cors-configuration)
  - [OAuth 2.1 with PKCE](#oauth-21-with-pkce)
  - [Static File Serving](#static-file-serving)
- [Frontend: React Widget](#frontend-react-widget)
  - [Widget Entry Point Pattern](#widget-entry-point-pattern)
  - [The window.openai API](#the-windowopenai-api)
  - [Hooks: useOpenAiGlobal](#hooks-useopenaiglobal)
  - [Reading Tool Output](#reading-tool-output)
  - [Vite Single-File Build](#vite-single-file-build)
  - [The script Escape Problem](#the-script-escape-problem)
- [Data Flow: End to End](#data-flow-end-to-end)
- [Key Gotchas and Lessons Learned](#key-gotchas-and-lessons-learned)
- [Widget Limitations (ChatGPT Platform)](#widget-limitations-chatgpt-platform)
- [Configuration Reference](#configuration-reference)
- [Links and References](#links-and-references)

---

## Architecture Overview

```
ChatGPT                          Your Server
┌────────────────┐               ┌──────────────────────┐
│                │  MCP/HTTP      │  FastAPI + FastMCP    │
│  User message  │───────────────>│                      │
│       ↓        │               │  1. Tool called       │
│  LLM calls     │               │  2. Returns:          │
│  MCP tool      │<──────────────│     structuredContent │
│       ↓        │               │     + _meta (template)│
│  Fetches HTML  │───────────────>│                      │
│  resource      │<──────────────│  3. Returns HTML      │
│       ↓        │               │     (self-contained)  │
│  Renders in    │               └──────────────────────┘
│  iframe with   │
│  toolOutput =  │
│  structuredContent
│       ↓        │
│  Widget reads  │
│  window.openai │
│  .toolOutput   │
└────────────────┘
```

**Key insight**: `window.openai.toolOutput` **IS** the `structuredContent` from the MCP tool response. There is no extra wrapping.

---

## Project Structure

```
project-root/
├── server_py/
│   ├── pyproject.toml
│   └── src/
│       └── server/
│           ├── __init__.py
│           ├── main.py              # Entry point, uvicorn runner
│           ├── app.py               # FastAPI application factory
│           ├── config.py            # PORT, BASE_URL from env
│           ├── mcp_server.py        # FastMCP instance + tool/resource registration
│           ├── auth/
│           │   ├── oauth_server.py  # OAuth 2.1 endpoints (APIRouter)
│           │   ├── middleware.py    # FastAPI Depends() for auth
│           │   └── token_store.py   # In-memory token/client/code storage
│           ├── tools/
│           │   ├── marketplace.py   # register_marketplace_tools(mcp)
│           │   ├── knowledge.py     # register_knowledge_tools(mcp)
│           │   ├── commerce.py      # register_commerce_tools(mcp)
│           │   └── files.py         # register_file_tools(mcp)
│           ├── resources/
│           │   └── templates.py     # MCP resources (widget HTML, config)
│           ├── data/
│           │   ├── products.py      # Mock data + helpers
│           │   ├── knowledge_base.py
│           │   ├── media.py
│           │   ├── capabilities.py
│           │   └── limitations.py
│           ├── middleware/
│           │   └── cors.py          # CORS + ngrok middleware
│           └── routes/
│               ├── api.py           # Protected API endpoints
│               └── health.py        # Health check + root info
│
├── web/
│   ├── package.json
│   ├── vite.config.js               # Main SPA dev config
│   ├── vite.overview.config.js      # Single-file widget build config
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html                   # SPA entry (dev/standalone)
│   ├── overview-widget.html         # Widget entry (for Vite build)
│   ├── src/
│   │   ├── main.jsx                 # SPA entry point
│   │   ├── overview-widget.jsx      # Standalone widget entry point
│   │   ├── App.jsx
│   │   ├── lib/
│   │   │   └── openai-hooks.js      # React hooks for window.openai
│   │   └── components/
│   │       ├── widgets/
│   │       │   └── WidgetRouter.jsx # Routes structuredContent.type → component
│   │       └── ...
│   └── dist/
│       ├── overview-widget.html     # Built widget (self-contained HTML)
│       ├── index.html               # Built SPA
│       └── assets/                  # Built SPA assets
```

---

## Backend: FastAPI + MCP

### Dependencies

```toml
# pyproject.toml
[project]
name = "your-app"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "mcp>=1.23.0",
    "pydantic>=2.10.0",
    "python-multipart>=0.0.18",
]
```

| Package | Purpose |
|---|---|
| `mcp` | Official MCP Python SDK. Provides `FastMCP`, `CallToolResult`, transport layers |
| `fastapi` | HTTP framework. Hosts MCP transport, OAuth, static files, API routes |
| `uvicorn` | ASGI server |
| `pydantic` | Data validation. MCP SDK uses it for tool argument schemas |
| `python-multipart` | Required by FastAPI for form data (OAuth token endpoint) |

### MCP Server Setup

```python
# mcp_server.py
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="your-app-name",
        stateless_http=True,  # REQUIRED for ChatGPT Apps
        transport_security=TransportSecuritySettings(
            # Disable for dev with ngrok; configure properly for production
            enable_dns_rebinding_protection=False,
        ),
    )

    # Register tools and resources
    register_your_tools(mcp)
    register_resources(mcp)

    return mcp
```

**Critical**: `stateless_http=True` is required. Without it, the MCP SDK expects persistent sessions which ChatGPT does not maintain.

For production with specific allowed hosts:

```python
TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["your-domain.com"],
    allowed_origins=["https://your-domain.com"],
)
```

### FastAPI Application Factory

```python
# app.py
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.applications import Starlette

from .mcp_server import create_mcp_server


def create_lifespan(session_manager):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with session_manager.run():
            yield
    return lifespan


def create_app() -> FastAPI:
    # 1. Create MCP server and get HTTP transport app
    mcp = create_mcp_server()
    mcp_http_app = mcp.streamable_http_app()
    session_manager = mcp._session_manager

    # 2. Create FastAPI app with MCP session lifecycle
    app = FastAPI(
        title="Your App",
        lifespan=create_lifespan(session_manager),
    )

    # 3. Configure middleware (CORS, etc.)
    configure_middleware(app)

    # 4. Register routes (health, API, OAuth)
    register_routes(app)

    # 5. Mount static files for widget assets
    mount_static_files(app)

    # 6. Mount MCP sub-app LAST (catch-all at "/")
    mcp_http_app.router.lifespan_context = None  # Avoid double init
    app.mount("/", mcp_http_app)

    return app
```

**Important**: Mount MCP at `"/"` **last**. The MCP sub-app has a route at `/mcp` internally, so mounting at `"/"` makes the final path `/mcp`. Since it's a catch-all mount, it must come after all other routes.

### Tool Registration

Tools use the `@mcp.tool()` decorator. Python type hints generate JSON Schema automatically.

```python
# tools/your_tools.py
import json
from typing import Literal, Optional
from mcp.types import CallToolResult, TextContent

TEMPLATE_URI = "ui://widget/main.html"


def _widget_meta():
    """Metadata that tells ChatGPT this tool renders a widget."""
    return {
        "openai/outputTemplate": TEMPLATE_URI,          # Links to HTML resource
        "openai/toolInvocation/invoking": "Loading...",  # Status while running
        "openai/toolInvocation/invoked": "Widget ready", # Status when done
        "openai/widgetAccessible": True,                 # Widget can call tools
    }


def register_your_tools(mcp):
    @mcp.tool(
        meta=_widget_meta(),  # Tool-level meta (shown in tool listing)
    )
    def your_widget_tool(
        query: str,
        mode: Optional[Literal["simple", "detailed"]] = "simple",
        limit: Optional[int] = 10,
    ) -> CallToolResult:
        """Description shown to the LLM for tool selection."""
        data = {"items": [...], "total": 42}

        return CallToolResult(
            # structuredContent becomes window.openai.toolOutput in the widget
            structuredContent={
                "type": "your-widget-type",
                "data": data,
            },
            # Text fallback for non-widget clients
            content=[TextContent(type="text", text=json.dumps(data, indent=2))],
            # Invocation-level meta
            _meta=_widget_meta(),
        )
```

**Type hint → JSON Schema mapping:**

| Python | JSON Schema | Example |
|---|---|---|
| `str` | `{"type": "string"}` | `name: str` |
| `int` | `{"type": "integer"}` | `limit: int = 10` |
| `float` | `{"type": "number"}` | `price: float` |
| `bool` | `{"type": "boolean"}` | `confirm: bool` |
| `Literal["a", "b"]` | `{"enum": ["a", "b"]}` | `mode: Literal["inline", "pip"]` |
| `Optional[T]` | nullable T | `query: Optional[str] = None` |
| `list[Item]` | `{"type": "array", "items": ...}` | `items: list[CheckoutItem]` |
| `Annotated[int, Field(ge=1, le=10)]` | `{"minimum": 1, "maximum": 10}` | Constrained values |

For complex tool arguments, use Pydantic models:

```python
from pydantic import BaseModel, Field

class CheckoutItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=10)

@mcp.tool()
def create_checkout(items: list[CheckoutItem]) -> CallToolResult:
    ...
```

### Resource Registration (Widget HTML)

The widget HTML resource is the core of the rendering pipeline. ChatGPT fetches this HTML and renders it in an iframe.

```python
# resources/templates.py
from functools import lru_cache
from pathlib import Path

WIDGET_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "web" / "dist"
TEMPLATE_URI = "ui://widget/main.html"
MIME_TYPE = "text/html+skybridge"


@lru_cache(maxsize=None)
def load_widget_html():
    """Load pre-built self-contained HTML from disk."""
    path = WIDGET_DIR / "your-widget.html"
    if path.exists():
        return path.read_text(encoding="utf8")
    return '<html><body><p style="color:red">Widget not built.</p></body></html>'


def register_resources(mcp):
    @mcp.resource(TEMPLATE_URI, name="Main widget", mime_type=MIME_TYPE)
    def widget_template() -> str:
        """Widget HTML template rendered in ChatGPT iframe."""
        return load_widget_html()
```

**Critical details:**

| Field | Value | Notes |
|---|---|---|
| URI | `ui://widget/name.html` | Must use `ui://` scheme |
| MIME type | `text/html+skybridge` | Required for ChatGPT to recognize as widget |
| HTML content | Self-contained | All JS/CSS must be inlined. No external requests. |

**Why self-contained?** ChatGPT loads widget HTML in a sandboxed iframe. External `<script src="...">` and `<link href="...">` requests are blocked by CSP. The official examples use Vite to build single-file HTML with everything inlined.

### CORS Configuration

MCP over HTTP requires specific CORS headers:

```python
# middleware/cors.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def configure_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Accept",
            "mcp-session-id",                # Required for MCP protocol
            "ngrok-skip-browser-warning",     # Dev convenience
        ],
        expose_headers=["mcp-session-id"],    # Client needs to read this
    )
```

The `mcp-session-id` header is part of the MCP streamable HTTP transport protocol.

### OAuth 2.1 with PKCE

ChatGPT MCP connections support OAuth 2.1. Required endpoints:

```
GET  /.well-known/oauth-protected-resource     # Resource metadata
GET  /.well-known/oauth-authorization-server    # Auth server metadata
POST /oauth/register                           # Dynamic client registration (RFC 7591)
GET  /oauth/authorize                          # Authorization page (HTML)
POST /oauth/authorize                          # Handle login + consent
POST /oauth/token                              # Token exchange
POST /oauth/revoke                             # Token revocation (RFC 7009)
```

**Authorization server metadata** (minimum required fields):

```python
@router.get("/.well-known/oauth-authorization-server")
def auth_server_metadata(request: Request):
    base = get_base_url(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "scopes_supported": ["read", "write"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic"],
    }
```

**PKCE verification** (S256):

```python
import hashlib
import base64

def verify_pkce(code_verifier: str, stored_code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return computed == stored_code_challenge
```

### Static File Serving

For development and the standalone SPA:

```python
from fastapi.staticfiles import StaticFiles

def mount_static_files(app: FastAPI):
    web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

    assets_path = web_dist / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    if web_dist.exists():
        app.mount("/widget", StaticFiles(directory=str(web_dist), html=True), name="widget")
```

Note: Static file mounts are for the development SPA. The widget HTML served via MCP resource is self-contained and does not rely on these mounts.

---

## Frontend: React Widget

### Widget Entry Point Pattern

Each widget should be a **standalone entry point** — not a monolithic SPA. The official examples build each widget into its own self-contained HTML file.

```jsx
// src/your-widget.jsx
import React, { useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';

// Hook to subscribe to window.openai globals
function useOpenAiGlobal(key) {
  return useSyncExternalStore(
    (onChange) => {
      const handler = () => onChange();
      window.addEventListener('openai:set_globals', handler, { passive: true });
      return () => window.removeEventListener('openai:set_globals', handler);
    },
    () => window.openai?.[key] ?? null,
    () => null
  );
}

function YourWidget() {
  const toolOutput = useOpenAiGlobal('toolOutput');
  const data = toolOutput?.data;

  if (!data) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>{data.title}</h1>
      {/* Render your widget content */}
    </div>
  );
}

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<YourWidget />);
}
```

Corresponding HTML template for Vite:

```html
<!-- your-widget.html -->
<!doctype html>
<html>
<head><meta charset="UTF-8"></head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/your-widget.jsx"></script>
</body>
</html>
```

### The window.openai API

ChatGPT injects the `window.openai` object into the widget iframe. Key properties and methods:

| Property/Method | Type | Description |
|---|---|---|
| `window.openai.toolOutput` | `object` | The `structuredContent` from the MCP tool response |
| `window.openai.theme` | `"light" \| "dark"` | Current ChatGPT theme |
| `window.openai.displayMode` | `"inline" \| "fullscreen" \| "pip"` | Current display mode |
| `window.openai.widgetState` | `object` | Persisted widget state (4k token limit) |
| `window.openai.locale` | `string` | User's locale (e.g. `"en-US"`) |
| `window.openai.callTool(name, args)` | `Promise` | Call an MCP tool from the widget |
| `window.openai.setWidgetState(state)` | `void` | Persist widget state |
| `window.openai.requestDisplayMode({mode})` | `Promise` | Request display mode change |
| `window.openai.requestFileUpload(opts)` | `Promise` | Request file upload dialog |
| `window.openai.openDownloadUrl(url, name)` | `Promise` | Trigger file download |
| `window.openai.openExternal({href})` | `Promise` | Open external link |
| `window.openai.sendFollowUpMessage({prompt})` | `Promise` | Send follow-up chat message |
| `window.openai.requestModal({title, params})` | `Promise` | Open modal dialog |

**Events:**

| Event | When | Detail |
|---|---|---|
| `openai:set_globals` | Any global changes | `{globals: {key: value}}` |

### Hooks: useOpenAiGlobal

The official pattern uses `useSyncExternalStore` (React 18+) to subscribe to `window.openai` changes:

```javascript
// lib/openai-hooks.js
import { useSyncExternalStore } from 'react';

const SET_GLOBALS_EVENT = 'openai:set_globals';

export function useOpenAiGlobal(key) {
  return useSyncExternalStore(
    // subscribe
    (onChange) => {
      if (typeof window === 'undefined') return () => {};
      const handler = (event) => {
        if (event.detail?.globals?.[key] === undefined) return;
        onChange();
      };
      window.addEventListener(SET_GLOBALS_EVENT, handler, { passive: true });
      return () => window.removeEventListener(SET_GLOBALS_EVENT, handler);
    },
    // getSnapshot (client)
    () => (typeof window !== 'undefined' ? window.openai?.[key] ?? null : null),
    // getServerSnapshot (SSR)
    () => null
  );
}
```

**Do NOT use:**
- `setInterval` polling
- `openai:change` event (does not exist)
- `useEffect` with `window.openai` reads (race conditions)

### Reading Tool Output

```jsx
function MyWidget() {
  // toolOutput IS the structuredContent from the MCP response
  const toolOutput = useOpenAiGlobal('toolOutput');

  // Your structuredContent shape: { type: "...", data: {...} }
  const data = toolOutput?.data;
  if (!data) return <Loading />;

  return <YourComponent data={data} />;
}
```

### Vite Single-File Build

The widget HTML must be **self-contained** — all JS and CSS inlined into one HTML file. This requires a custom Vite plugin:

```javascript
// vite.widget.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve, join } from 'path';
import { readFileSync, writeFileSync } from 'fs';

function viteSingleFile() {
  let outDir;
  return {
    name: 'vite-single-file',
    enforce: 'post',

    configResolved(config) {
      outDir = config.build.outDir;
    },

    generateBundle(_, bundle) {
      const htmlKey = Object.keys(bundle).find(k => k.endsWith('.html'));
      if (!htmlKey) return;
      let html = bundle[htmlKey].source;

      // Inline CSS
      for (const [key, chunk] of Object.entries(bundle)) {
        if (!key.endsWith('.css')) continue;
        const filename = key.split('/').pop();
        const escaped = filename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        html = html.replace(
          new RegExp(`<link[^>]+href="[^"]*${escaped}"[^>]*/?>`),
          `<style>${chunk.source}</style>`
        );
        delete bundle[key];
      }

      // Inline JS
      for (const [key, chunk] of Object.entries(bundle)) {
        if (!key.endsWith('.js')) continue;
        const filename = key.split('/').pop();
        const escaped = filename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        html = html.replace(
          new RegExp(`<script[^>]+src="[^"]*${escaped}"[^>]*></script>`),
          `<script type="module">${chunk.code}</script>`
        );
        delete bundle[key];
      }

      bundle[htmlKey].source = html;
    },

    // CRITICAL: Escape </script> inside inlined JS
    closeBundle() {
      const htmlPath = join(outDir, 'your-widget.html');
      let html;
      try { html = readFileSync(htmlPath, 'utf8'); } catch { return; }

      html = html.replace(
        /(<script type="module">)([\s\S]*)(<\/script>)\s*<\/head>/,
        (_, open, code, _close) => {
          const safe = code.replace(/<\/script>/gi, '<\\/script>');
          return `${open}${safe}</script>\n</head>`;
        }
      );

      writeFileSync(htmlPath, html);
    }
  };
}

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: 'dist',
    emptyOutDir: false,          // Don't delete other build outputs
    rollupOptions: {
      input: resolve(__dirname, 'your-widget.html'),
    },
    cssCodeSplit: false,
    modulePreload: false,        // No modulepreload polyfill
    sourcemap: false,
  },
});
```

Build command in `package.json`:

```json
{
  "scripts": {
    "build:widget": "vite build --config vite.widget.config.js"
  }
}
```

### The `</script>` Escape Problem

React DOM's minified code contains literal `</script>` strings (used for innerHTML processing). When you inline the JS into `<script>...</script>`, the browser's HTML parser sees the `</script>` inside the JS and **prematurely closes the script tag**. The rest of the JS source spills out as visible text.

**Fix**: The `closeBundle` hook in the Vite plugin above replaces `</script>` with `<\/script>` inside the inlined JS. The HTML parser does not recognize `<\/script>` as a closing tag, but the JS engine interprets `\/` as just `/`.

The regex uses **greedy** `[\s\S]*` (not `[\s\S]*?`) to match up to the LAST `</script>` before `</head>` — that last one is the real closing tag.

---

## Data Flow: End to End

1. **User sends message** in ChatGPT
2. **LLM decides** to call your MCP tool based on the tool description
3. **ChatGPT sends** MCP `tools/call` request to your server at `/mcp`
4. **Your tool function runs**, returns `CallToolResult` with:
   - `structuredContent`: data for the widget
   - `content`: text fallback
   - `_meta`: includes `openai/outputTemplate` pointing to `ui://widget/main.html`
5. **ChatGPT reads** `_meta["openai/outputTemplate"]` → fetches the MCP resource at that URI
6. **Your resource function** returns the self-contained HTML (read from disk)
7. **ChatGPT renders** the HTML in a sandboxed iframe
8. **ChatGPT sets** `window.openai.toolOutput = structuredContent` and fires `openai:set_globals`
9. **React reads** `toolOutput` via `useSyncExternalStore` and renders the widget

---

## Key Gotchas and Lessons Learned

### 1. Widget HTML MUST be self-contained

External `<script src="...">` and `<link href="...">` will not load inside the ChatGPT iframe. Inline everything.

### 2. `</script>` inside inlined JS breaks rendering

React DOM contains literal `</script>` in its minified source. You must escape these to `<\/script>` after inlining. Without this, the widget shows raw JS code as text.

### 3. `stateless_http=True` is required

Without this, FastMCP expects persistent sessions. ChatGPT does not maintain MCP sessions.

### 4. Path resolution for widget HTML

When using `Path(__file__).resolve().parent...` to locate `web/dist/`, count the `.parent` calls carefully:

```
server_py/src/server/resources/templates.py
         ^   ^      ^         ^
         4   3      2         1 (parent from __file__)
```

5 `.parent` calls from `templates.py` reaches `project-root/`.

### 5. `window.openai.toolOutput` IS the structuredContent

No extra `.structuredContent` wrapper. If your tool returns:

```python
structuredContent={"type": "overview", "data": {...}}
```

Then `window.openai.toolOutput` is `{"type": "overview", "data": {...}}`.

### 6. Use `useSyncExternalStore`, not polling

The official SDK uses `useSyncExternalStore` + `openai:set_globals` event. Do not use `setInterval` or custom event names.

### 7. One widget per entry point

Build each widget as a separate Vite entry. A monolithic SPA that imports all components will be large and fragile. If any import fails, the entire widget crashes with no visible error.

### 8. `@lru_cache` for widget HTML loading

The HTML file doesn't change at runtime. Cache it to avoid disk reads on every request:

```python
@lru_cache(maxsize=None)
def load_widget_html():
    return (WIDGET_DIR / "widget.html").read_text(encoding="utf8")
```

### 9. Mount MCP sub-app last

The MCP sub-app is a Starlette mount at `/`. If mounted before other routes, it will shadow them.

### 10. Debug mode toggle

Keep a `DEBUG_MODE` flag in your resource module. When `True`, serve a trivial inline HTML that dumps `window.openai.toolOutput` — useful for verifying the pipeline works before debugging React issues.

```python
DEBUG_MODE = False  # Set True to test pipeline

def _build_debug_html():
    return """<!doctype html>
<html><body>
  <h1 style="color:green">Pipeline Works</h1>
  <pre id="d"></pre>
  <script>
    var d = document.getElementById('d');
    function show() {
      d.textContent = JSON.stringify(window.openai?.toolOutput || 'null', null, 2);
    }
    show();
    window.addEventListener('openai:set_globals', show);
  </script>
</body></html>"""
```

---

## Widget Limitations (ChatGPT Platform)

**Strict (enforced):**

| Limitation | Detail |
|---|---|
| No inline scripts in HTML | Use `<script type="module">` with inlined code |
| No `eval()` / `Function()` | CSP blocks dynamic code evaluation |
| No `localStorage` / `sessionStorage` | Use `window.openai.setWidgetState()` instead |
| No audio/video autoplay | Must be user-initiated |
| Widget state limit | 4k tokens maximum for `setWidgetState` |
| Max 2 primary action buttons | Per widget render |
| No nested scrolling | No scrollable containers inside the widget |
| CSP sandbox | Strict content security policy on the iframe |

**Recommendations:**

| Recommendation | Detail |
|---|---|
| Carousel items | 3-8 items recommended |
| No auto-refresh | Avoid `setInterval` polling for data |
| Inline height limit | Inline widgets have max height ~400px |

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8787` | Server port |
| `BASE_URL` | `http://localhost:{PORT}` | Public URL (set when behind proxy/ngrok) |
| `MCP_ALLOWED_HOSTS` | (none) | Comma-separated allowed hosts for transport security |
| `MCP_ALLOWED_ORIGINS` | (none) | Comma-separated allowed origins |

### Tool Meta Fields

| Key | Type | Description |
|---|---|---|
| `openai/outputTemplate` | `string` | URI of the widget HTML resource (e.g. `ui://widget/main.html`) |
| `openai/toolInvocation/invoking` | `string` | Status text shown while tool is running |
| `openai/toolInvocation/invoked` | `string` | Status text shown when tool completes |
| `openai/widgetAccessible` | `boolean` | Whether widget can call tools via `window.openai.callTool` |

### MCP Resource Fields

| Field | Value |
|---|---|
| URI scheme | `ui://` for widget HTML |
| MIME type | `text/html+skybridge` for widget HTML |

---

## Links and References

### Official

- [OpenAI Apps SDK Examples (GitHub)](https://github.com/openai/openai-apps-sdk-examples) — Official reference implementations
  - [`kitchen_sink_server_python/main.py`](https://github.com/openai/openai-apps-sdk-examples/blob/main/kitchen_sink_server_python/main.py) — Canonical Python MCP server
  - [`shopping_cart_python/main.py`](https://github.com/openai/openai-apps-sdk-examples/blob/main/shopping_cart_python/main.py) — Stateful widget with `widgetSessionId`
  - [`authenticated_server_python/main.py`](https://github.com/openai/openai-apps-sdk-examples/blob/main/authenticated_server_python/main.py) — OAuth + widget
  - [`src/use-openai-global.ts`](https://github.com/openai/openai-apps-sdk-examples/blob/main/src/use-openai-global.ts) — Official `useOpenAiGlobal` hook
  - [`src/types.ts`](https://github.com/openai/openai-apps-sdk-examples/blob/main/src/types.ts) — TypeScript types for `window.openai`
  - [`build-all.mts`](https://github.com/openai/openai-apps-sdk-examples/blob/main/build-all.mts) — Vite build orchestrator (per-widget)

### MCP Protocol

- [MCP Specification](https://spec.modelcontextprotocol.io/) — Full protocol specification
- [MCP Python SDK (GitHub)](https://github.com/modelcontextprotocol/python-sdk) — `mcp` package source
- [MCP Python SDK (PyPI)](https://pypi.org/project/mcp/) — Package page

### FastAPI

- [FastAPI Documentation](https://fastapi.tiangolo.com/) — Framework docs
- [FastAPI CORS Middleware](https://fastapi.tiangolo.com/tutorial/cors/) — CORS setup reference
- [FastAPI Static Files](https://fastapi.tiangolo.com/tutorial/static-files/) — Static file serving

### Vite

- [Vite Documentation](https://vite.dev/) — Build tool docs
- [`@vitejs/plugin-react`](https://github.com/vitejs/vite-plugin-react) — React plugin for Vite
- [Vite Build Options](https://vite.dev/config/build-options) — Build configuration reference

### OAuth 2.1

- [RFC 6749 — OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749) — Base spec
- [RFC 7636 — PKCE](https://datatracker.ietf.org/doc/html/rfc7636) — Proof Key for Code Exchange
- [RFC 7591 — Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591)
- [RFC 7009 — Token Revocation](https://datatracker.ietf.org/doc/html/rfc7009)
