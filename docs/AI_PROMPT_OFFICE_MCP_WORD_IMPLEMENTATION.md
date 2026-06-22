# Office MCP Word — UPGRADE 收尾 + v1.1 — AI Prompt Sequence

将下方 prompt **按顺序**复制到 AI 会话（Cursor Agent 等）。**一次只跑一个 Batch**；本文件 **仅覆盖未完成 Task**（WT-037–WT-049、WT-DOC-04）。WT-001–036 架构交付已完成，**勿重复实现**。

**按文件任务（未完成）：** [`OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md) — Group H–K  
**Word 实现设计：** [`OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md)  
**规格 / E2E 清单：** [`OFFICE_MCP_WORD_UPGRADE.md`](./OFFICE_MCP_WORD_UPGRADE.md) §4.3、§7.2  
**LLM 字段名：** [`OFFICE_MCP_WORD_LLM_GUIDE.md`](./OFFICE_MCP_WORD_LLM_GUIDE.md)（`search_string` / `replace_string`）  
**E2E 参考：** [`tests/office_mcp/test_e2e_office_tools.py`](../tests/office_mcp/test_e2e_office_tools.py)、[`tests/env_test.py`](../tests/env_test.py)

**范围（必做）：**

| Batch | Tasks | 内容 |
|-------|-------|------|
| **H — E2E** | WT-037 – WT-042 | 替换 `test_e2e_word_tools.py` placeholder；Gate **W-E2E** |
| **I — Schema** | WT-043 – WT-045 | `page_size`/`title`、edit `TOOL_DEF` 与 Pydantic 对齐 |
| **J — v1.1** | WT-046 – WT-048 | insert 定位、search_replace scope、W4 op（**必做，非 optional**） |
| **K — 卫生** | WT-049、WT-DOC-04 | 测试命名、文档 Gate 同步 |

**前置（已满足，仅核对）：**

- `word/` 六工具 + legacy 别名已在 `registry.py`
- `poetry run pytest tests/office_mcp/word/ -v -m "not e2e"` 全绿
- `tests/office_mcp/word/test_e2e_word_tools.py` 仍为 **placeholder skip**

**真源优先级：** ADR（已采纳）→ Word IMPLEMENTATION_DESIGN → **本 tasks 文档** → UPGRADE

---

## 0. Session Bootstrap Prompt（仅首次）

```
You are completing Office MCP Word UPGRADE follow-up — tasks WT-037 through WT-049 and WT-DOC-04 ONLY.

DO NOT re-implement WT-001–036 (word/ tree, registry, unit tests already done).

Required reading:
- docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md (Group H–K ONLY)
- docs/OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md (§5 schemas, §7 builder, §11 tests)
- docs/OFFICE_MCP_WORD_UPGRADE.md (§4.3 edit ops, §7.2 E2E list)
- docs/OFFICE_MCP_WORD_LLM_GUIDE.md
- tests/office_mcp/test_e2e_office_tools.py (_call_tool_via_mcp pattern)
- tests/env_test.py (E2EConfig, .env.test)

Global constraints:
1. One prompt = one batch per docs/AI_PROMPT_OFFICE_MCP_WORD_IMPLEMENTATION.md Appendix A.
2. Do NOT git commit unless I explicitly ask.
3. Surgical changes — touch word/, tests/office_mcp/word/, and docs listed in WT-DOC-04 only.
4. Do NOT modify core/ except ADR-029 bugfix (prefer zero core changes).
5. word/* MUST NOT import presentation|spreadsheet|pdf.
6. office_read_document: coarse behavior FROZEN (WT-NA-01 / OT-NA-05) — no transparent fine forwarding.
7. Edit operations use search_string / replace_string (NOT search/replace).
8. v1.1 (WT-046–048) is REQUIRED in this prompt sequence — not optional stretch goals.
9. E2E: use MCP HTTP tools/call via pattern in test_e2e_office_tools.py; config from .env.test (E2E_SOURCE_PATH, E2E_MCP_URL, DOCUMENTSERVER_*).
10. When DS unreachable, e2e may skip per ADR-021 — but implementation must NOT hardcode pytest.skip("placeholder"); use documentserver_reachable() skipif at module level only.
11. After each batch, mark completed WT-* as [x] in OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md.

Precondition check:
- poetry run pytest tests/office_mcp/word/ -v -m "not e2e"  # must pass
- test -f aiecs/tools/office_tool/word/tools/read.py
- test -f tests/office_mcp/word/test_e2e_word_tools.py
- grep -q "pytest.skip.*placeholder" tests/office_mcp/word/test_e2e_word_tools.py && echo "OK: placeholder still present (to replace)"

Reply "Ready for WT-prep" — do not write code yet.
```

---

## 1. Task WT-prep — 基线 + E2E 环境

```
[TASK WT-prep] Baseline; confirm .env.test; inventory placeholder E2E

1. poetry run pytest tests/office_mcp/word/ -v -m "not e2e"  # must pass

2. Read tests/env_test.py E2EConfig — document which vars are set:
   E2E_SOURCE_PATH / E2E_SOURCE_PATHS / E2E_TEMPLATE_PATH / E2E_MCP_URL / DOCUMENTSERVER_URL / JWT

3. Confirm test_e2e_office_tools.py has _call_tool_via_mcp — reuse or extract shared helper for word e2e (minimal: import/call same pattern).

4. List open tasks WT-037–049 from docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md Group H–K.

Do NOT implement E2E yet.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
test -f .env.test && echo "OK: .env.test exists" || echo "WARN: no .env.test — E2E needs local config"
rg "placeholder" tests/office_mcp/word/test_e2e_word_tools.py
rg "_call_tool_via_mcp" tests/office_mcp/test_e2e_office_tools.py | head -2
```

---

## 2. Batch T-WT-E2E-A — Tasks WT-037 – WT-038（docx + odt 闭环）

```
[TASK WT-037–038] Implement real Word E2E: docx create/read/edit + odt round-trip

Implement WT-037 and WT-038 from docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md Group H.

File: tests/office_mcp/word/test_e2e_word_tools.py

WT-037 — docx:
1. Remove unconditional pytest.skip("placeholder") from test body.
2. test_e2e_create_read_edit_word_docx:
   - office_create_word → gs:// or configured output_path .docx
   - office_read_word fine structured → assert blocks/unit_count
   - office_edit_word with search_string/replace_string (or set_heading)
   - office_read_word again → assert change visible

WT-038 — odt:
3. test_e2e_odt_create_edit_roundtrip:
   - output_path ends with .odt
   - create → edit → output still .odt

Use _call_tool_via_mcp from test_e2e_office_tools.py (import or shared conftest helper).
Use unique output paths (uuid) under E2E bucket prefix to avoid collisions.
Keep @pytest.mark.word @pytest.mark.e2e and documentserver_reachable skipif.

Add unit-level tests only if needed for helpers — prefer E2E in this file.

Mark WT-037, WT-038 [x] in tasks doc when done.
Do NOT git commit unless I ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/word/test_e2e_word_tools.py -v -m "word and e2e" -k "docx or odt" 2>&1 | tail -30
! rg "placeholder" tests/office_mcp/word/test_e2e_word_tools.py | rg "pytest.skip" && echo "FAIL: placeholder skip remains" || echo "OK"
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
```

---

## 3. Batch T-WT-E2E-B — Tasks WT-039 – WT-041（merge / legacy / read_document）

```
[TASK WT-039–041] Word E2E: merge odt, legacy aliases, read_document coarse

Implement WT-039, WT-040, WT-041 from tasks doc Group H.

In tests/office_mcp/word/test_e2e_word_tools.py (or split files if cleaner):

WT-039 — test_e2e_merge_word_odt:
- Two source docx from E2E_SOURCE_PATHS or create two small docs first
- office_merge_word → output_path *.odt
- Assert success; optional read_word verify page/block count

WT-040 — legacy smoke (via MCP call_tool names):
- office_merge_documents → same as merge_word path
- office_apply_template with E2E_TEMPLATE_PATH + data dict
- office_edit_document with minimal edit_script (Search-based, not GetElement index)

WT-041 — test_e2e_read_document_docx_coarse:
- office_read_document on docx source
- Assert coarse/html path (NOT fine ToJSON blocks from read_word)
- Must NOT regress to forwarding office_read_word fine read

Reference UPGRADE §7.2 cases 5–6 and §9.

Mark WT-039–041 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/word/test_e2e_word_tools.py -v -m "word and e2e" 2>&1 | tail -40
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
```

---

## 4. Task WT-042 — Gate W-E2E

```
[TASK WT-042] Close Gate W-E2E

1. All WT-037–041 marked [x] in OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md
2. Update tasks doc bottom checklist: W-E2E line → [x]
3. Brief note in test file module docstring: required .env.test vars

Verification: full word e2e suite runs without placeholder skip (may skip entire module if DS down — OK per ADR-021).
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/word/ -v -m "word and e2e"
grep "W-E2E" docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md | head -5
```

---

## 5. Batch T-WT-SCHEMA — Tasks WT-043 – WT-045

```
[TASK WT-043–045] Schema / Builder / TOOL_DEF alignment

Implement WT-043 through WT-045 from tasks doc Group I.

WT-043 page_size:
- Implement in word/builder/create.py using ONLYOFFICE Document API for A4/Letter page size IF documented in DS API;
- OR remove page_size from WordCreateOptions + office_create_word TOOL_DEF + UPGRADE/LLM guide (pick ONE; document in PR).
- Add test in test_create_word.py or test_schemas.py.

WT-044 title:
- Same pattern: implement doc title property in build_create_script OR remove from schema/docs.

WT-045 edit TOOL_DEF:
- Expand word/tools/edit.py inputSchema operations items to match edit_ops.py:
  op enum, search_string, replace_string, block_index, heading_path, match_text, text, style_name, items, rows, after (start|end), block_type
- Keep consistent with LLM guide.

Run: poetry run pytest tests/office_mcp/word/ -v -m "not e2e"

Mark WT-043–045 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
rg "search_string" aiecs/tools/office_tool/word/tools/edit.py
python3 -c "
from aiecs.tools.office_tool.word.tools.edit import TOOL_DEF
import json
props = TOOL_DEF['inputSchema']['properties']['operations']['items']['properties']
assert 'search_string' in props, list(props.keys())
print('OK: TOOL_DEF has search_string')
"
```

---

## 6. Batch T-WT-V11 — Tasks WT-046 – WT-048（v1.1 · 必做）

```
[TASK WT-046–048] v1.1 capability — REQUIRED (not optional)

Implement WT-046, WT-047, WT-048 from tasks doc Group J.

WT-046 — word/builder/edit.py + edit_ops.py if needed:
- insert_bullets, insert_table: honor after / block_index / heading_path (reuse _bind_block_target / insert after locator)
- insert_paragraph: extend after beyond start/end if schema allows object locator — align schema + builder + tests
- Update OFFICE_MCP_WORD_LLM_GUIDE.md: remove "v1 append only" where fixed
- test_edit_builder.py + test_edit_word.py cases

WT-047 — search_replace scope:
- Add optional heading_path or scope field to EditOperation (Pydantic validator)
- builder/edit.py: limit SearchAndReplace to subtree when scope/heading_path set (document-level fallback OK if DS API limited — document behavior in test)
- test_schemas.py + test_edit_builder.py

WT-048 — W4 operations (minimal viable set — pick implementable subset):
- Add at least ONE new op with schema + builder + unit test, e.g.:
  - insert_page_break after locator (improve add_page_break positioning), OR
  - insert_image with url/path (if storage pattern exists), OR
  - section_break / footnote stub with clear {isError} if DS unsupported
- Document scope in UPGRADE §8 W4 row + IMPLEMENTATION_DESIGN
- Do NOT expand into full footnote CRUD (UPGRADE §1.3 still out of scope for full CRUD)

All v1.1 work stays in word/ + tests/office_mcp/word/ + docs.

Mark WT-046–048 [x].
Run full word unit tests.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
poetry run pytest tests/office_mcp/word/test_edit_builder.py tests/office_mcp/word/test_schemas.py -v
# If E2E covers new ops:
poetry run pytest tests/office_mcp/word/ -v -m "word and e2e" -k "edit" 2>&1 | tail -20
```

---

## 7. Batch T-WT-HYGIENE — Tasks WT-049、WT-DOC-04

```
[TASK WT-049–DOC-04] Test naming + documentation Gate sync

WT-049:
- Align global OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md OT-062 description with actual filenames
  OR rename tests/office_mcp/word/test_office_apply_template.py → test_apply_template_word.py (and edit_document similarly) — pick minimal churn.

WT-DOC-04:
- OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md §2.2 / §11.3: E2E ✅ after WT-042; v1.1 ✅ after WT-048
- OFFICE_MCP_WORD_UPGRADE.md §8.1: E2E + v1.1 status rows
- OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md: Group J header = 必做; all WT-037–049 [x]; checklist all [x]
- Global tasks OT-067 footnote: Word DS E2E complete (WT-042)

Mark WT-049, WT-DOC-04 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
grep -c "\[ \]" docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md | head -1
# Expect only template lines in "完成定义" section, not open tasks
rg "WT-0(3[7-9]|[4-9][0-9])" docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md | rg "\[ \]" || echo "OK: no open WT-037+ tasks"
```

---

## 8. Task WT-T — Definition of Done

```
[TASK WT-T] Word UPGRADE + v1.1 wrap-up

Verify docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md Group H–K all [x].

1. Unit: poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
2. E2E: poetry run pytest tests/office_mcp/word/ -v -m "word and e2e" (PASS or ADR-021 skip — no placeholder)
3. Schema: search_string in TOOL_DEF; page_size/title resolved (implemented or removed consistently)
4. v1.1: insert positioning + search_replace scope + WT-048 W4 op documented
5. Docs synced (WT-DOC-04)
6. word isolated: ! rg "presentation|spreadsheet|pdf" imports in word/

Output report:
- Tasks WT-037–049 status
- E2E env requirements (.env.test keys)
- v1.1 behavior summary (what changed for LLM callers)
- Files touched

Do NOT git commit unless I explicitly ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
poetry run pytest tests/office_mcp/word/ -v -m "word and e2e"
! rg "from aiecs.tools.office_tool.(presentation|spreadsheet|pdf)" aiecs/tools/office_tool/word/
```

---

## Appendix A — Recommended execution order

| Step | Prompt | Tasks | Gate |
|------|--------|-------|------|
| 0 | Bootstrap | — | — |
| 1 | §1 WT-prep | env + baseline | — |
| 2 | §2 | **WT-037–038** | E2E docx/odt |
| 3 | §3 | **WT-039–041** | E2E merge/legacy/coarse |
| 4 | §4 | **WT-042** | **W-E2E** |
| 5 | §5 | **WT-043–045** | Schema |
| 6 | §6 | **WT-046–048** | **v1.1 必做** |
| 7 | §7 | **WT-049, WT-DOC-04** | Docs |
| 8 | §8 WT-T | DoD | 终验收 |

**顺序约束：** E2E（H）→ Schema（I）→ **v1.1（J，必做）** → 卫生（K）。v1.1 若改 edit schema，须在 WT-045 之后或同 PR 更新 TOOL_DEF。

---

## Appendix B — Fix prompt template

```
Word task WT-{XXX} verification failed.

Failed command output:
<paste output>

Fix ONLY within WT-{XXX} / batch scope per docs/OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md Group H–K.
Do NOT re-do WT-001–036.
Do NOT change office_read_document coarse behavior (WT-NA-01).
Do NOT modify core/ unless ADR-029 bugfix.
Use search_string / replace_string for edit ops.
Re-run this step's verification commands only.
Mark [x] in tasks doc when fixed.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix C — Single-session continuous prompt（高级）

```
Follow docs/AI_PROMPT_OFFICE_MCP_WORD_IMPLEMENTATION.md Appendix A (steps 0–8) for WT-037–049 ONLY.
Skip WT-001–036 entirely.
Treat WT-046–048 (v1.1) as REQUIRED.
After each batch: run verification, mark [x] in OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md, continue.
Finish with WT-T report.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix D — `.env.test` 参考（E2E）

| 变量 | 用途 |
|------|------|
| `DOCUMENTSERVER_URL` | DS healthcheck |
| `DOCUMENTSERVER_JWT_SECRET` | Builder/Conversion |
| `E2E_MCP_URL` | MCP `tools/call` HTTP |
| `E2E_MCP_PUBLIC_URL` | DS 拉 script 可达地址 |
| `E2E_SOURCE_PATH` | 单 docx 源 |
| `E2E_SOURCE_PATHS` | merge 多源（逗号或 JSON） |
| `E2E_TEMPLATE_PATH` | apply_template |

**维护：** 随 [`OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_WORD_IMPLEMENTATION_TASKS_BY_FILE.md) Group H–K 更新。
