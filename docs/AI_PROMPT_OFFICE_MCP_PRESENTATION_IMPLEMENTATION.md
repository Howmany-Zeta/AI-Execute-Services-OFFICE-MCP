# Office MCP Presentation — UPGRADE 收尾 — AI Prompt Sequence

将下方 prompt **按顺序**复制到 AI 会话（Cursor Agent 等）。**一次只跑一个 Batch**；本文件 **仅覆盖未完成 Task**（PT-037–PT-053）。PT-001–036 架构交付与 **PT-DOC-04** 文档同步已完成，**勿重复实现**。

**按文件任务（未完成）：** [`OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md) — Group I–K  
**Presentation 实现设计：** [`OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md)  
**规格 / E2E 清单：** [`OFFICE_MCP_PRESENTATION_UPGRADE.md`](./OFFICE_MCP_PRESENTATION_UPGRADE.md) §4.3、§7.2  
**LLM 字段名：** [`OFFICE_MCP_PRESENTATION_LLM_GUIDE.md`](./OFFICE_MCP_PRESENTATION_LLM_GUIDE.md)（`slide_index` / `shape_index` + `layouts[]` / `allowed_layouts`）  
**E2E 参考：** [`tests/office_mcp/test_e2e_office_tools.py`](../tests/office_mcp/test_e2e_office_tools.py)、[`tests/env_test.py`](../tests/env_test.py)

**范围（必做）：**

| Batch | Tasks | 内容 |
|-------|-------|------|
| **I — E2E** | PT-037 – PT-044 | 替换 `test_e2e_presentation_tools.py` placeholder；Gate **P-E2E** |
| **J — Schema** | PT-045 – PT-046 | **ADR-041** `add_slide` 字段 + **ADR-043** `TOOL_DEF` ↔ `edit_ops.py`（**同批**） |
| **J′ — Read** | PT-047 – PT-048、**PT-053** | **ADR-044** fallback；**ADR-045** sidecar range；**ADR-047** `_note` |
| **J″ — Merge** | PT-049 | **ADR-042** `separator_layout` + `allowed_layouts` |
| **K — Builder** | PT-050 – PT-052 | `test_presentation_builder`、odp schema；PT-052 可选 M4 registry |

**前置（已满足，仅核对）：**

- `presentation/` 五 canonical 工具已在 `registry.py`（M4 **13/17**；当前 repo M6 **23/27** 含 pres×5）
- `poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"` 全绿（31 tests）
- **无** presentation legacy MCP 别名
- `tests/office_mcp/presentation/test_e2e_presentation_tools.py` 仍为 **placeholder skip**
- **PT-DOC-04** ✅（ADR-041～047 已写入 UPGRADE / DESIGN / LLM 指南）

**真源优先级：** ADR（已采纳，含 **ADR-041–047** Presentation 收尾）→ Presentation IMPLEMENTATION_DESIGN §14 → **本 tasks 文档** → UPGRADE

---

## 0. Session Bootstrap Prompt（仅首次）

```
You are completing Office MCP Presentation UPGRADE follow-up — tasks PT-037 through PT-053 ONLY.

DO NOT re-implement PT-001–036 (presentation/ tree, registry, unit tests already done).
DO NOT re-do PT-DOC-04 (ADR-041～047 docs already synced).

Required reading:
- docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md (Group I–K ONLY)
- docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md (§5 schemas, §7 builder, §10 tests, §14 gap index)
- docs/OFFICE_MCP_PRESENTATION_UPGRADE.md (§4.3 edit ops, §7.2 E2E list, §8.1 status)
- docs/OFFICE_MCP_PRESENTATION_LLM_GUIDE.md
- docs/ADR.md — ADR-002, 006, 008, 009, 016, 024–025, 028–029, **041–047**
- tests/office_mcp/test_e2e_office_tools.py (_call_tool_via_mcp pattern)
- tests/office_mcp/presentation/fixtures/layouts_pptx.json / layouts_odp.json (ADR-016 E2E)
- tests/env_test.py (E2EConfig, .env.test)

Global constraints:
1. One prompt = one batch per docs/AI_PROMPT_OFFICE_MCP_PRESENTATION_IMPLEMENTATION.md Appendix A.
2. Do NOT git commit unless I explicitly ask.
3. Surgical changes — touch presentation/, tests/office_mcp/presentation/, and post-E2E doc lines in tasks/global OT only.
4. Do NOT modify core/ except ADR-029 bugfix (prefer zero core changes).
5. presentation/* MUST NOT import word|spreadsheet|pdf.
6. office_read_document: pptx/ppt/odp txt coarse behavior FROZEN (PT-NA-01 / OT-NA-05) — no transparent fine forwarding.
7. Edit/create use slide_index / shape_index + layout from layouts[] (ADR-016) — NOT office_read_document index.
8. create / add_slide / merge separator: options.allowed_layouts REQUIRED (ADR-046: no template_path on create).
9. add_slide optional fields: title / subtitle / items (ADR-041) — NOT bullets on EditOperation.
10. No presentation legacy MCP aliases (ADR-024).
11. E2E: MCP HTTP tools/call via test_e2e_office_tools.py pattern; config from .env.test.
12. Builder uses Api.GetPresentation() — NEVER Api.GetDocument() on pptx (PT-NA-02).
13. Do NOT leave unconditional pytest.skip("placeholder") in E2E test bodies after PT-037+.
14. After each batch, mark completed PT-* as [x] in OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md.

Precondition check:
- poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"  # must pass
- test -f aiecs/tools/office_tool/presentation/tools/read.py
- test -f tests/office_mcp/presentation/test_e2e_presentation_tools.py
- rg "pytest.skip.*placeholder" tests/office_mcp/presentation/test_e2e_presentation_tools.py && echo "OK: placeholder still present (to replace)"

Reply "Ready for PT-prep" — do not write code yet.
```

---

## 1. Task PT-prep — 基线 + E2E 环境

```
[TASK PT-prep] Baseline; confirm .env.test; inventory open tasks

1. poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"  # must pass

2. Read tests/env_test.py E2EConfig — document which vars are set:
   E2E_SOURCE_PATH / E2E_SOURCE_PATHS / E2E_TEMPLATE_PATH / E2E_MCP_URL / DOCUMENTSERVER_URL / JWT
   Note: .env.test may point at docx — presentation E2E often create decks in-test (unique gs:// or s3:// output paths).

3. Confirm test_e2e_office_tools.py has _call_tool_via_mcp — reuse for presentation E2E.

4. Load tests/office_mcp/presentation/fixtures/layouts_pptx.json for create/add_slide allowed_layouts in E2E.

5. List open tasks PT-037–053 from docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md Group I–K.

6. Read ADR-041–047 summaries in docs/ADR.md for upcoming schema/read batches.

Do NOT implement E2E yet.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
test -f .env.test && echo "OK: .env.test exists" || echo "WARN: no .env.test — E2E needs local config"
rg "placeholder" tests/office_mcp/presentation/test_e2e_presentation_tools.py
rg "_call_tool_via_mcp" tests/office_mcp/test_e2e_office_tools.py | head -2
python3 -c "import json; from pathlib import Path; p=Path('tests/office_mcp/presentation/fixtures/layouts_pptx.json'); print('layouts:', len(json.loads(p.read_text())))"
```

---

## 2. Batch T-PT-E2E-A — Tasks PT-037 – PT-038（pptx create/read + edit）

```
[TASK PT-037–038] Implement real Presentation E2E: pptx create/read + edit re-read

Implement PT-037 and PT-038 from docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md Group I.

File: tests/office_mcp/presentation/test_e2e_presentation_tools.py

Replace placeholder skip with real tests. Module docstring: required .env.test vars.

PT-037 — test_e2e_create_read_presentation_pptx:
1. Remove unconditional pytest.skip("placeholder") from implemented tests.
2. office_create_presentation — 3 slides, output_path unique *.pptx
   - options.allowed_layouts from fixtures/layouts_pptx.json (or prior read layouts[])
   - layouts per slide from allowed list (e.g. Title Slide, Title and Content, Blank)
3. office_read_presentation fine structured → assert slide_count / unit_count == 3
4. assert layouts[] non-empty (ADR-016)

PT-038 — test_e2e_edit_presentation_pptx:
5. office_edit_presentation on deck from PT-037 (or shared fixture helper):
   - set_title on slide 0
   - set_bullets on slide 1 (items list)
   - add_slide with layout ∈ prior read layouts[]; pass options.allowed_layouts
6. office_read_presentation fine again → assert title/bullets/new slide visible
7. success alone NOT sufficient for PT-038 [x]

Use _call_tool_via_mcp from test_e2e_office_tools.py.
Use unique output paths (uuid) under E2E bucket prefix.
Keep @pytest.mark.presentation @pytest.mark.e2e and documentserver_reachable skipif.

Mark PT-037, PT-038 [x] when done.
Do NOT git commit unless I ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/presentation/test_e2e_presentation_tools.py -v -m "presentation and e2e" -k "create or edit" 2>&1 | tail -30
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
! rg "pytest.skip.*placeholder" tests/office_mcp/presentation/test_e2e_presentation_tools.py && echo "OK: no placeholder skip" || echo "FAIL"
```

---

## 3. Batch T-PT-E2E-B — Tasks PT-039 – PT-041（merge / template / odp）

```
[TASK PT-039–041] Presentation E2E: merge, template, odp round-trip

Implement PT-039, PT-040, PT-041 from tasks doc Group I.

In tests/office_mcp/presentation/test_e2e_presentation_tools.py:

PT-039 — test_e2e_merge_presentations:
- Two source pptx (create two small decks in-test OR E2E_SOURCE_PATHS if pptx configured)
- Record each source slide_count via office_read_presentation fine
- office_merge_presentations → output_path *.pptx
- **必须**：office_read_presentation fine on merged output → assert slide_count == sum(source counts) when no collision
- Assert merge handler success — success alone NOT sufficient for PT-039 [x]

PT-040 — test_e2e_apply_template_presentation:
- E2E_TEMPLATE_PATH pptx (or create template deck in-test) + data with {{company_name}} or slide_1_title
- **必须**：handler success
- **推荐**：re-read fine 断言 placeholder 替换可见

PT-041 — test_e2e_odp_create_edit_roundtrip (P4 / ADR-016):
- output_path ends with .odp
- create with options.allowed_layouts from fixtures/layouts_odp.json
- edit (set_title) → save still .odp

Reference UPGRADE §7.2; DESIGN §10.3 #3–5.

Mark PT-039–041 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/test_e2e_presentation_tools.py -v -m "presentation and e2e" -k "merge or template or odp" 2>&1 | tail -40
rg "slide_count|unit_count" tests/office_mcp/presentation/test_e2e_presentation_tools.py
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
```

---

## 4. Batch T-PT-E2E-C — Tasks PT-042 – PT-043（legacy / forbid path）

```
[TASK PT-042–043] Presentation E2E: legacy read_document + forbid office_edit_document on pptx

PT-042 — test_e2e_read_document_pptx_coarse:
- Create or use a pptx source path
- office_read_document on pptx → assert txt/coarse elements path
- Must NOT transparently forward office_read_presentation fine slides[]
- PT-NA-01 frozen behavior

PT-043 — test_presentation_edit_document_rejects_pptx (or equivalent name):
- **必须**：automated test in test_e2e_presentation_tools.py OR tests/office_mcp/test_integration.py
- Call office_edit_document with pptx source_path + minimal edit → assert {isError} or failure (Word oDoc API)
- Module docstring alone is NOT sufficient for PT-043 [x]

Mark PT-042, PT-043 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/test_e2e_presentation_tools.py -v -m "presentation and e2e" -k "read_document or edit_document" 2>&1 | tail -25
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
```

---

## 5. Task PT-044 — Gate P-E2E

```
[TASK PT-044] Close Gate P-E2E

1. PT-037–043 all [x] in OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md
2. Update tasks doc bottom checklist: P-E2E line → [x]
3. Update IMPLEMENTATION_DESIGN §3.2 P1/P2/P4 E2E rows → ✅
4. Update OFFICE_MCP_PRESENTATION_UPGRADE.md §8.1 P-E2E row → ✅
5. Module docstring in test_e2e_presentation_tools.py: required .env.test vars

Verification: full presentation e2e suite without placeholder skip in test bodies (module may skip if DS down — OK per ADR-021).

Mark PT-044 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e"
grep "P-E2E" docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md | head -5
! rg "pytest.skip.*placeholder" tests/office_mcp/presentation/test_e2e_presentation_tools.py && echo "OK"
```

---

## 6. Batch T-PT-SCHEMA — Tasks PT-045 + PT-046（同批）

```
[TASK PT-045–046] add_slide schema + TOOL_DEF single source (ADR-041, ADR-043)

Implement PT-045 AND PT-046 together — mark both [x] only when both pass.

PT-046 (ADR-041) — presentation/schemas/edit_ops.py + builder/edit.py:
- Add optional title, subtitle, items on EditOperation (add_slide only; validator)
- builder/edit.py: subtitle placeholder SetText; items → body bullets (use items not bullets)
- Remove dead op.title path inconsistency

PT-045 (ADR-043) — presentation/tools/edit.py:
- Regenerate inputSchema.operations.items from EditOperation.model_json_schema() (ADR-002)
- op enum must list all 10 OpName values
- Must include ADR-041 fields after PT-046 lands

Files: schemas/edit_ops.py, builder/edit.py, tools/edit.py
Tests: tests/office_mcp/presentation/test_schemas.py — add_slide with title/items accepted

**Do NOT mark PT-045 [x] before PT-046 schema fields exist.**

Run: poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"

After PT-046 lands: re-run PT-038 E2E (or add test asserting add_slide with optional title/items in script/schema).

Mark PT-045, PT-046 [x] together.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/test_schemas.py tests/office_mcp/presentation/test_edit_presentation.py -v
python3 -c "
from aiecs.tools.office_tool.presentation.tools.edit import TOOL_DEF
from aiecs.tools.office_tool.presentation.schemas.edit_ops import OpName
props = TOOL_DEF['inputSchema']['properties']['operations']['items']['properties']
assert 'op' in props and 'title' in props, list(props.keys())
enum = props['op'].get('enum') or props['op'].get('anyOf', [{}])[0].get('enum', [])
assert set(enum) == set(OpName.__args__), (enum, OpName.__args__)
print('OK: TOOL_DEF op enum + title')
"
```

---

## 7. Batch T-PT-READ — Tasks PT-047 – PT-048、PT-053

```
[TASK PT-047–048, PT-053] Read: coarse fallback + sidecar slide_range + layouts _note

PT-047 (ADR-044) — presentation/schemas/read.py + tools/read.py:
- PresentationReadOptions.allow_coarse_fallback: bool = True
- Fine sidecar failure + allow true → convert_and_fetch coarse + read_mode=coarse + COARSE_NOTE
- allow false → err(sidecar_err) (current behavior)
- Unit test: tests/office_mcp/presentation/test_read_presentation.py mock both paths

PT-048 (ADR-045) — presentation/parser/slides.py + tools/read.py:
- build_slides_extract_body(start, end) replacing static SLIDES_TOJSON_EXTRACT_BODY
- Handler computes start/end from options.slide_range (inclusive 0-based) before read_sidecar_json
- layouts[] still full deck dedupe (ADR-047 parse)；apply_slide_range retained
- Unit test: test_slides_parser.py or test_read_presentation.py asserts range in extract body

PT-053 (ADR-047) — presentation/tools/read.py:
- When fine structured and len(layouts) <= 1 and slide_count > 0: append to extra._note:
  "layouts[] may be incomplete if deck uses few layouts; read a multi-layout template master for full enum (ADR-047)."
- Must coexist with _locator_note and ADR-044 coarse _note (do not overwrite)
- Unit test: test_read_presentation.py mock triggers _note condition

Sync UPGRADE §4.1 if behavior text changed.

Mark PT-047, PT-048, PT-053 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/test_read_presentation.py tests/office_mcp/presentation/test_slides_parser.py -v
rg "allow_coarse_fallback|build_slides_extract_body|layouts\[\] may be incomplete" aiecs/tools/office_tool/presentation/
```

---

## 8. Batch T-PT-MERGE — Task PT-049

```
[TASK PT-049] Merge separator layout (ADR-042)

Implement PT-049 from tasks doc Group J.

PresentationMergeOptions (schemas/edit_ops.py or slide_spec.py):
- separator_layout: str | None
- allowed_layouts: list[str] | None
- When separator_slide=true: separator_layout AND allowed_layouts required; separator_layout ∈ allowed_layouts

Files:
- slide_spec.py: validate_merge_separator_layout()
- builder/merge.py: pres.AddSlide(separator_layout) — delete hardcoded "Blank"
- tools/merge.py: handler validation + TOOL_DEF options

Unit: tests/office_mcp/presentation/test_merge_presentations.py asserts separator_layout in script body

Mark PT-049 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/test_merge_presentations.py -v
! rg 'AddSlide\("Blank"\)' aiecs/tools/office_tool/presentation/builder/merge.py && echo "FAIL: Blank hardcoded" || echo "OK"
```

---

## 9. Batch T-PT-BUILDER — Tasks PT-050 – PT-052

```
[TASK PT-050–052] Builder tests + odp schema + optional M4 registry

PT-050 — tests/office_mcp/presentation/test_presentation_builder.py:
- Assert build_edit_script body for: set_bullets, duplicate_slide, move_slide, set_notes,
  replace_image, remove_shape, match_text/role resolution
- Cover PT-046 add_slide title/subtitle/items lines if not already

PT-051 — tests/office_mcp/presentation/test_schemas.py:
- layouts_odp.json enum accept/reject cases
- duplicate_slide / move_slide / set_notes required-field validators

PT-052 (recommended) — tests/office_mcp/test_registry.py:
- Add TestRegistryM4 or slice assert CANONICAL_MODULES[8:13] are presentation×5
- Optional: assert len(collect_office_tools())==13 when testing M4 slice only

Mark PT-050–052 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/presentation/test_presentation_builder.py tests/office_mcp/presentation/test_schemas.py -v
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
poetry run pytest tests/office_mcp/test_registry.py -v -k "M4 or presentation" 2>&1 | tail -15
```

---

## 10. Task PT-T — Definition of Done

```
[TASK PT-T] Presentation UPGRADE wrap-up

Verify docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md Group I–K all [x].

1. Unit: poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
2. E2E: poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e" (PASS or ADR-021 skip — no placeholder)
3. Schema: add_slide title/subtitle/items (ADR-041); TOOL_DEF (ADR-043); merge separator (ADR-042)
4. Read: allow_coarse_fallback (ADR-044); sidecar slide_range (ADR-045); layouts incomplete _note (ADR-047 / PT-053)
5. Builder tests + odp schema (PT-050–051)
6. Update OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md OT-099 / G2 footnote: Presentation DS E2E complete (PT-044)
7. presentation isolated: ! rg "word|spreadsheet|pdf" imports in presentation/

Output report:
- Tasks PT-037–053 status
- E2E env requirements (.env.test keys)
- ADR-041–047 behavior summary for LLM callers
- Files touched

Do NOT git commit unless I explicitly ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e"
! rg "from aiecs.tools.office_tool.(word|spreadsheet|pdf)" aiecs/tools/office_tool/presentation/
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools
p={'office_read_presentation','office_create_presentation','office_edit_presentation',
   'office_merge_presentations','office_apply_template_presentation'}
assert p <= {t['name'] for t in collect_office_tools()}
print('OK: presentation×5 in registry')
"
rg "PT-0(3[7-9]|[4-9][0-9]|5[0-3])" docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md | rg "\[ \]" || echo "OK: no open PT-037+ tasks"
```

---

## Appendix A — Recommended execution order

| Step | Prompt | Tasks | Gate |
|------|--------|-------|------|
| 0 | Bootstrap | — | — |
| 1 | §1 PT-prep | env + baseline | — |
| 2 | §2 | **PT-037–038** | E2E pptx create/edit |
| 3 | §3 | **PT-039–041** | E2E merge/template/odp |
| 4 | §4 | **PT-042–043** | legacy + forbid path |
| 5 | §5 | **PT-044** | **P-E2E** |
| 6 | §6 | **PT-045 + PT-046** | TOOL_DEF + add_slide（**同批**） |
| 7 | §7 | **PT-047–048 + PT-053** | Read fallback + sidecar + ADR-047 `_note` |
| 8 | §8 | **PT-049** | Merge separator ADR-042 |
| 9 | §9 | **PT-050–052** | Builder tests / registry |
| 10 | §10 PT-T | DoD | 终验收 |

**顺序约束：** E2E（I）→ **PT-045–046 同批**（完成后重跑 PT-038 或补 add_slide+items 断言）→ Read（PT-047–048、**PT-053**）→ Merge（PT-049）→ Builder（K）。**禁止**在 PT-046 之前单独将 PT-045 标 `[x]`。

---

## Appendix B — Fix prompt template

```
Presentation task PT-{XXX} verification failed.

Failed command output:
<paste output>

Fix ONLY within PT-{XXX} / batch scope per docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md Group I–K.
Do NOT re-do PT-001–036 or PT-DOC-04.
Do NOT change office_read_document txt coarse behavior (PT-NA-01).
Do NOT use office_edit_document on pptx (PT-NA-02).
Do NOT modify core/ unless ADR-029 bugfix.
Use slide_index / shape_index + layouts[] / allowed_layouts (ADR-016).
Re-run this step's verification commands only.
Mark [x] in tasks doc when fixed.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix C — Single-session continuous prompt（高级）

```
Follow docs/AI_PROMPT_OFFICE_MCP_PRESENTATION_IMPLEMENTATION.md Appendix A (steps 0–10) for PT-037–053 ONLY.
Skip PT-001–036 and PT-DOC-04 entirely.
PT-045 and PT-046 must complete in the same batch before marking either [x].
After each batch: run verification, mark [x] in OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md, continue.
Finish with PT-T report.
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
| `E2E_SOURCE_PATH` | 单源（可为 docx — presentation 测试常 in-test create pptx） |
| `E2E_SOURCE_PATHS` | merge 多源 |
| `E2E_TEMPLATE_PATH` | apply_template pptx（若非 pptx，测试中 create 模板 deck） |

**Layout fixtures（无 prior read 时）：**

- pptx：`tests/office_mcp/presentation/fixtures/layouts_pptx.json`
- odp：`tests/office_mcp/presentation/fixtures/layouts_odp.json`

**维护：** 随 [`OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md) Group I–K 更新。

---

## Appendix E — Task ID 覆盖矩阵（未完成部分）

| Task | TASKS Group | AI_PROMPT | 备注 |
|------|-------------|-----------|------|
| PT-037–038 | I | §2 | pptx create/read + edit |
| PT-039–041 | I | §3 | merge **必须** re-read 断言 slide_count |
| PT-042–043 | I | §4 | PT-043 **必须** 自动化断言 `office_edit_document`+pptx 失败 |
| PT-044 | I | §5 | P-E2E Gate |
| PT-045 | J | §6（与 PT-046） | ADR-043 TOOL_DEF |
| PT-046 | J | §6（与 PT-045） | ADR-041 add_slide fields |
| PT-047–048 | J′ | §7 | ADR-044/045 |
| PT-053 | J′ | §7 | ADR-047 `_note` |
| PT-049 | J″ | §8 | ADR-042 merge separator |
| PT-050–052 | K | §9 | builder / odp schema / M4 registry |
| PT-NA-01–06 | H | §0 Bootstrap | 约束级覆盖 |
| PT-001–036 | A–F | — | ⛔ 已完成 |
| PT-DOC-01–04 | G/L | — | ⛔ 已完成 |

**未完成 PT 共 17 项**（PT-037–043、045–049、050–052、053）：prompt 均有对应 batch，无遗漏 Task ID。
