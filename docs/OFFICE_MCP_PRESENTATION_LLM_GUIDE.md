# Office MCP Presentation — LLM 调用指南

面向 Agent / LLM 的 presentation（`.ppt` / `.pptx` / `.odp`）**精细化创建与编辑**操作说明。  
完整设计与实现计划见 [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md)。

> **M7 同步**：编辑定位用 `slide_index` / `shape_index`；layout 须与 `allowed_layouts` / fine read 的 `layouts[]` 精确一致（**ADR-016**）。**ADR-041～047** 已回写本文档。

---

## 1. 何时用哪个工具

| 任务 | 使用工具 | 不要用 |
|------|----------|--------|
| 读取 slide/形状结构 | `office_read_presentation` | `office_read_document`（仅 txt 粗读） |
| 从零创建 PPT | `office_create_presentation` | 直接 `office_execute_builder`（除非高级排版） |
| 改某一页标题/正文/插页 | `office_edit_presentation` | `office_edit_document` + Word 式 Search |
| 合并多个 PPT | `office_merge_presentations` | `office_merge_documents` |
| 模板填数据 | `office_apply_template_presentation` | `office_apply_template` |
| pptx → pdf | `office_call_api` convert | — |
| 手写 Animation / 复杂图表 | `office_execute_builder` | — |

---

## 2. 核心概念

### 2.1 索引约定

- **`slide_index`**：从 **0** 开始。第 1 页 = `0`。
- **`shape_index`**：页内形状顺序，从 **0** 开始；**仅**与最近一次 `office_read_presentation` 结果一致。
- 编辑前若文档可能已被修改，**必须重新 read**。

### 2.2 输出格式

- 新建或另存时，用 `output_path` 扩展名选择格式：`.pptx`（推荐）或 `.odp`。
- 读取支持 `.ppt`、`.pptx`、`.odp` 等（见升级文档中的扩展名列表）。

### 2.3 精读 vs 粗读

| `options.read_mode` | 行为 |
|---------------------|------|
| **`fine`**（默认） | Builder `SlidesToJSON`；**编辑前必须** |
| **`coarse`** | Conversion txt；仅预览，**不可**用于 edit 定位 |
| fine 失败 | 默认降级 coarse + `_note`（**ADR-044**）；可设 `allow_coarse_fallback: false` 强制报错 |

### 2.4 Layout 名称（ADR-016 / ADR-046 / ADR-047）

- **`office_read_presentation`** fine read 返回 **`layouts[]`**（SlidesToJSON 去重；**可能不完整** — 见 `_note`）。
- **`office_create_presentation`**：**必填** `options.allowed_layouts`（抄录 prior read 的 `layouts[]` 或 E2E fixture）。**v1 无** `template_path` — 有企业模板用 **`office_apply_template_presentation`** 或 read→create（**ADR-046**）。
- **`office_edit_presentation`** / **`add_slide`**：`layout` ∈ **`options.allowed_layouts`**（含 `add_slide` 时必填）。
- **`office_merge_presentations`**：仅当 `separator_slide=true` 时需 **`separator_layout`** + **`allowed_layouts`**（**ADR-042**）。
- 无 fuzzy、无 default fallback；非法 layout → 校验失败。
- 若 read 后 `layouts[]` 仅 1 项且 deck 有多页用途，**须** read 含多 layout 的 master 模板，勿猜测（尤其 **`.odp`**）。

### 2.5 定位符（编辑时）

优先级：

1. `slide_index` + `shape_index`（最精确）
2. `slide_index` + `match_text`（文本包含匹配）
3. `slide_index` + `role: "title" | "body"`（占位符角色）

---

## 3. 工作流示例

### 3.1 创建 3 页汇报 PPT

**Step 0（推荐）** — 若使用 `.odp` 或不确定 layout 名，先 read 模板或空白 deck 获取 `layouts[]`：

```json
{
  "tool": "office_read_presentation",
  "arguments": {
    "source_path": "gs://my-bucket/templates/blank-master.pptx",
    "format": "outline"
  }
}
```

从响应 `layouts[]` 抄录到 **`options.allowed_layouts`**（下方示例 layout 名适用于常见英文 pptx master）。

**Step 1 — Create**

```json
{
  "tool": "office_create_presentation",
  "arguments": {
    "output_path": "gs://my-bucket/reports/q1-review.pptx",
    "options": {
      "allowed_layouts": [
        "Title Slide",
        "Title and Content",
        "Section Header",
        "Two Content"
      ]
    },
    "slides": [
      {
        "layout": "Title Slide",
        "title": "Q1 Business Review",
        "subtitle": "Confidential"
      },
      {
        "layout": "Title and Content",
        "title": "Highlights",
        "bullets": [
          "Revenue exceeded plan by 8%",
          "Two new enterprise customers",
          "Product NPS +6"
        ]
      },
      {
        "layout": "Title and Content",
        "title": "Next Steps",
        "bullets": ["Expand APAC", "Ship v2.0 in Q2"]
      }
    ]
  }
}
```

### 3.2 读取后再编辑

**Step 1 — Read**

```json
{
  "tool": "office_read_presentation",
  "arguments": {
    "source_path": "gs://my-bucket/reports/q1-review.pptx",
    "format": "structured"
  }
}
```

**Step 2 — Edit**（假设 read 显示 slide 1 标题 shape_index=0）

```json
{
  "tool": "office_edit_presentation",
  "arguments": {
    "source_path": "gs://my-bucket/reports/q1-review.pptx",
    "output_path": "gs://my-bucket/reports/q1-review-v2.pptx",
    "options": {
      "allowed_layouts": ["Title Slide", "Title and Content", "Section Header", "Two Content"]
    },
    "operations": [
      {
        "op": "set_title",
        "slide_index": 0,
        "text": "Q1 Business Review — Final"
      },
      {
        "op": "set_bullets",
        "slide_index": 1,
        "items": [
          "Revenue +8% vs plan",
          "Enterprise wins: ACME, Globex",
          "NPS 62 (+6 YoY)"
        ]
      },
      {
        "op": "add_slide",
        "after_index": 2,
        "layout": "Title and Content",
        "title": "Thank You",
        "items": ["Questions?"]
      }
    ]
  }
}
```

### 3.3 按文本模糊改某一页

当 shape_index 不确定，但知道旧文案：

```json
{
  "op": "set_text",
  "slide_index": 2,
  "match_text": "Draft timeline",
  "text": "Approved timeline — March launch"
}
```

### 3.4 模板填充

```json
{
  "tool": "office_apply_template_presentation",
  "arguments": {
    "template_path": "gs://my-bucket/templates/corporate-deck.pptx",
    "output_path": "gs://my-bucket/decks/acme-intro.pptx",
    "data": {
      "company_name": "ACME Corp",
      "presenter": "Jane Doe",
      "date": "2026-06-21",
      "slide_1_title": "ACME — Company Overview"
    }
  }
}
```

占位符在模板文本框中写 `{{company_name}}`；按页键名用 `slide_1_title`（见 [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md) §4.5）。

### 3.5 合并两个文件

```json
{
  "tool": "office_merge_presentations",
  "arguments": {
    "source_paths": [
      "gs://my-bucket/part-a.pptx",
      "gs://my-bucket/part-b.pptx"
    ],
    "output_path": "gs://my-bucket/combined.pptx",
    "options": { "separator_slide": false }
  }
}
```

启用分隔页时（**ADR-042**）须先 read 抄录 `layouts[]`，再传 `separator_slide: true`、`separator_layout` 与 `allowed_layouts`：

```json
{
  "options": {
    "separator_slide": true,
    "separator_layout": "Title Slide",
    "allowed_layouts": ["Title Slide", "Title and Content"]
  }
}
```

### 3.6 导出 PDF

```json
{
  "tool": "office_call_api",
  "arguments": {
    "action": "convert",
    "params": {
      "url": "<fetchable pptx url>",
      "filetype": "pptx",
      "outputtype": "pdf",
      "key": "<unique-uuid>"
    }
  }
}
```

---

## 4. `office_edit_presentation` 操作速查

| op | 必填字段 | 说明 |
|----|----------|------|
| `set_text` | `slide_index`, `text`, 及 `shape_index` 或 `match_text` | 改形状内文本 |
| `set_title` | `slide_index`, `text` | 改标题占位符 |
| `set_bullets` | `slide_index`, `items` | 正文 bullet 列表 |
| `add_slide` | `after_index`, `layout`（∈ `allowed_layouts`） | 插入新页；可选 **`title`**, **`subtitle`**, **`items`**（**ADR-041**；勿用 `bullets`） |
| `delete_slide` | `slide_index` | 删除页 |
| `duplicate_slide` | `slide_index`, `after_index` | 复制页 |
| `move_slide` | `from_index`, `to_index` | 调整顺序 |
| `set_notes` | `slide_index`, `text` | 演讲者备注 |
| `replace_image` | `slide_index`, `shape_index`, `url` | 换图 |
| `remove_shape` | `slide_index`, `shape_index` | 删形状 |

`operations` **按数组顺序执行**。

---

## 5. 常见错误

| 错误做法 | 后果 | 正确做法 |
|----------|------|----------|
| 用 `office_read_document` 的 index 编辑 PPT | 改错页/形状 | 用 `office_read_presentation` + `slide_index` |
| 对 PPT 调用 `office_merge_documents` | Builder 失败（Word API） | `office_merge_presentations` |
| 不 re-read 就沿用旧 shape_index | 越界或改错 | 每次 edit 前 read，或改用 match_text |
| 猜测 layout 名（尤其 odp） | create/add_slide 校验失败 | 先 read 获取 `layouts[]` → `allowed_layouts` |
| `add_slide` 传 `bullets` 字段 | 被 schema 忽略 | 使用 **`items`**（**ADR-041**） |
| create 不传 `allowed_layouts` | 校验失败 | 必填；抄录 prior read（**ADR-016**） |
| output_path 无扩展名 | 保存格式不明 | 始终带 `.pptx` 或 `.odp` |
| 在 `edit_script` 里用 `Api.GetDocument()` 编辑 pptx | 脚本错误 | Presentation 用 `Api.GetPresentation()` |

---

## 6. 高级：直接写 Builder 脚本

仅当声明式 operations 不够用时：

```javascript
builder.OpenFile("https://...", "pptx");
var pres = Api.GetPresentation();
var slide = pres.GetSlideByIndex(0);
// ... ONLYOFFICE Presentation API ...
builder.SaveFile("pptx", "out.pptx");
builder.CloseFile();
```

通过 **`office_execute_builder`** 提交完整脚本（含 OpenFile/SaveFile）。**勿**对 pptx 使用 `office_edit_document`（Word API）。

参考：[ONLYOFFICE Presentation API](https://api.onlyoffice.com/docs/office-api/usage-api/presentation-api/)

---

## 7. 实现状态

| 工具 | 文档 | 代码（M4 架构） | ADR 收尾代码 |
|------|------|-----------------|--------------|
| `office_read_presentation` | ✅ | ✅ unit | ⏳ PT-047–048、**PT-053**（047 `_note`） |
| `office_create_presentation` | ✅ | ✅ unit | ✅ ADR-046（无 template_path） |
| `office_edit_presentation` | ✅ | ✅ unit | ⏳ PT-045–046 |
| `office_merge_presentations` | ✅ | ✅ unit | ⏳ PT-049 |
| `office_apply_template_presentation` | ✅ | ✅ unit | — |

**E2E（DS）**：⏳ **PT-037–044**。详见 [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md) §8.1。
