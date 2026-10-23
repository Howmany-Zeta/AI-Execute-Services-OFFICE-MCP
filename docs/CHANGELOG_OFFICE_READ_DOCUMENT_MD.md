# Changelog：`office_read_document` 阅读线出站（给 middleware / 调用方）

> **Office MCP 本仓库不改 middleware。** 请按本文改你们对 `office_read_document` 的解析。  
> 规格真源：[OFFICE_MCP_READ_EDIT_THREAD_PRD.md](./OFFICE_MCP_READ_EDIT_THREAD_PRD.md)  
> 开发者完整变更（含编辑线）：[CHANGELOG_READ_EDIT_THREAD.md](./CHANGELOG_READ_EDIT_THREAD.md)  
> 状态：**P0 + P1 已落地**（2026-10-23）

`office_read_word` / `office_read_presentation` / `office_read_pdf` / `office_read_spreadsheet` **出站不变**，仍用 `units` / `block_index` / `shape_index` 做编辑。不要把下面的变更套到这些工具上。

---

## 破坏性变更

`office_read_document` **不再返回** `elements[]`、`runs`、`index`。

| 以前（请删掉的解析） | 以后 |
|---|---|
| `data["elements"]` 数组 | 默认 `data["markdown"]` 字符串 |
| `element["text"]` / `element["runs"]` | 标准 Markdown（`#`、列表、pipe table、`![alt](media/…)`） |
| `element["index"]` 拿去 edit | **禁止**。阅读结果不能传给 `office_edit_*` |
| `element["page"]` | 正文里的 `[Page N]` 行；JSON 另有 `page_count` |

P0 **不并行**保留 `elements`。切完即无旧字段。

---

## 入参（阅读工具）

工具名仍是 `office_read_document`。`source_url` / `content_base64` / `source_path` 不变。

内容用 `format`（业界名，不再用 structured=富JSON、text=纯文本这种混名）：

| `format` | 你拿到的字 |
|---|---|
| `markdown`（默认） | 完整 Markdown |
| `plain` | 无标记纯文本 |
| `outline` | 仅标题 Markdown |

旧值 **`structured` / `text` 不再接受**（不是别名）。继续传会 `err`。请改成上表。`outline` 名字不变。

包装用 `options.accept`（MIME）：

| `accept` | 响应 |
|---|---|
| `application/json`（默认） | `{ markdown, media, page_count, title, _note, ... }`；`plain` 时字段为 `text` |
| `text/markdown` | 顶层就是 MD 字符串 |
| `text/plain` | 顶层就是纯文本 |
| `application/zip` | `content_base64`（`document.md` + `media/`） |

请改掉对 `format=structured` 必有 `elements` 的假设。阅读线没有 `structured` 这个值了。

---

## 默认 JSON 形状（你们现在最可能吃的）

```json
{
  "success": true,
  "title": "…",
  "markdown": "[Page 1]\n# …\n",
  "page_count": 3,
  "media": [],
  "_note": "For model reading only. Do not pass any index, page marker, or media URL to office_edit_*."
}
```

Markdown 约定：

- 页界：单独一行 `[Page N]`（1-based）。PPT=一页一幻灯片；Excel=一个 sheet 一页，sheet 名在 HTML 注释 `<!-- sheet: Name -->`，正文是 CSV。
- 标题 / 列表 / 表格：标准 MD。
- 图：`![alt](media/<filename>)`，元数据在 `media[]`（P1）。
- 扫描 PDF：有稳定 `pageStart` 才有 `[Page N]`，否则没有页标。
- **不要**从 MD 里解析 `block_index` / `shape_id`。

大文档：同步上限默认 `OFFICE_READ_MAX_PAGES=40`、`OFFICE_READ_MAX_SOURCE_BYTES=20MiB`。超限会 `isError`，用 **1-based** `options.page_range` 分段再调 **同一个** `office_read_document`。不要改调 `office_parse_document`。`OFFICE_READ_MAX_OUTPUT_BYTES=1MiB` 超限仍 `success`，正文截断并写 `_warnings`。

---

## 媒体（P1 已落地）

| `options.media_delivery` | 谁用 | `media[].url` |
|---|---|---|
| `fetch_token`（默认） | 同网 / 内部 | MCP 短 TTL fetch token |
| `caller_bucket` | 外部 | 调用方 `media_output_path`（`s3://` / `gs://` 目录）下的对象 |

---

## 建议你们改的代码

今天 middleware 若走 `_canonical_structured_elements` / `data.get("elements")` 再拼 `{n}\t{text}` preview：

1. **仅当 tool == `office_read_document`**：读 `markdown`（或 `text`），直接当 formatted 正文；页用 `[Page N]` 切，不要再造 `elements`。
2. **`office_read_word` 等**：继续解 `units` / `blocks` / `slides` / `pages`，逻辑可以不动。
3. 预览不要对阅读线再做 `3\t` 空行编号；MD 已是给人看的。
4. 任何「read_document → 把 index 填进 edit」的路径删掉。编辑必须先 `office_read_{category}` fine。

---

## 不变

- `office_read_*` / `office_edit_*` / `office_execute_builder` / `office_parse_document`
- parse 异步落 `canonical.md` 的 scholar-kg 契约
