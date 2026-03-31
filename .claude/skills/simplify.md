---
name: simplify
description: Simplify recently modified code for clarity and maintainability while preserving functionality. Auto-triggered after coding tasks.
model: opus
---

## Code Simplifier Skill

### Core Rules
1. **Preserve functionality** — never change what code does, only how it reads
2. **Clarity over brevity** — readable code is better than terse code
3. **Avoid over-engineering** — no abstractions for single-use cases

### Project-Specific Simplification Targets

**`bot/collector.py`**
- Each `fetch_*` function should have one clear responsibility
- Error handling: always `except Exception as exc: logger.warning(...)` then return fallback dict
- Never use nested try/except — keep flat

**`bot/scheduler.py`**
- Job functions should be < 30 lines; extract helpers for long logic
- Always use `_sanitize_for_json()` before any JSONB write

**`bot/analyzer.py`**
- Claude prompts are long by design — do not shorten prompts
- The `_call_claude_json()` helper handles all Claude calls — use it everywhere

**Frontend components**
- Extract reusable logic to custom hooks in `src/hooks/`
- Price delta logic → `useDelta(current, previous)` pattern
- Market hours → computed in MarketTicker, not in every component

### Patterns to Apply
- Replace `if x is not None: return x; else: return None` → `return x`
- Replace long chains of `.get()` with safe default: `data.get("key") or default`
- Replace `float(str(val).replace(",",""))` duplication → use `_parse_float()`
- Replace repeated `await asyncio.get_event_loop().run_in_executor(None, lambda: ...)` → extract helper

### Do NOT Simplify
- SQL query logic (keep explicit for security audit visibility)
- JWT token creation (security-sensitive, keep verbose)
- Claude prompts (intentionally detailed)
- Error logging (keep full tracebacks)
