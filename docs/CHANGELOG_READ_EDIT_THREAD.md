# 开发者变更：阅读线 / 编辑线收束

> 规格真源：[OFFICE_MCP_READ_EDIT_THREAD_PRD.md](./OFFICE_MCP_READ_EDIT_THREAD_PRD.md)  
> middleware 专用出站说明：[CHANGELOG_OFFICE_READ_DOCUMENT_MD.md](./CHANGELOG_OFFICE_READ_DOCUMENT_MD.md)  
> 读者：Office MCP 实现、调用方、模型编排  
> 本仓库不改 middleware。

三条线互不借用：

| 线 | 工具 | 给谁 | 出站 |
|---|---|---|---|
| 阅读 | `office_read_document` | 模型理解正文 | Markdown / plain / zip，**无编辑地址** |
| 编辑 | `office_read_{category}` + `office_edit_{category}` | 精细改文档 | locator + 文本 + 已识别格式 |
| 自定义 | `office_execute_builder` / `office_edit_word_script` | 开发者脚本 | 文件字节，MCP 不解释 |

`office_parse_document` **不退役**（scholar-kg 异步落库）。大文档继续用阅读线 + `page_range`。

---

## 1. 阅读线：实际变更与影响

工具名仍是 `office_read_document`。`source_url` / `content_base64` / `source_path` 不变。

### 1.1 破坏性

| 以前 | 以后 | 调用方要改 |
|---|---|---|
| `format=structured` → `elements[]` + `runs` | `format=markdown`（默认）→ `markdown` 字符串 | 删掉对 `elements` / `index` / `runs` 的解析 |
| `format=text` → 纯文本 | `format=plain` | 改枚举；旧值 **`err`，无别名** |
| `format=outline` | 仍叫 `outline`，但是标题 **MD** | 按 MD 标题解析，不要当 JSON 大纲 |
| `element.index` / `shape_id` 当 edit | **禁止** | 编辑必须先 `office_read_{category}` fine |

`structured`、`text` 传入直接失败：`format must be markdown, plain, or outline`。

### 1.2 入参

**内容 `format`：** `markdown`（默认）| `plain` | `outline`

**包装 `options.accept`：**

| 值 | 响应 |
|---|---|
| `application/json`（默认） | `{ title, markdown\|text, page_count, media, pages?, _note, _warnings? }` |
| `text/markdown` | 顶层 MD 字符串 |
| `text/plain` | 顶层纯文本 |
| `application/zip` | `content_base64`：`document.md` + `media/` |

**其它 options：**

| 字段 | 作用 |
|---|---|
| `page_range` | 1-based `[start, end]`，超同步上限后续读 |
| `media_delivery` | `fetch_token`（默认，同网）\| `caller_bucket`（外部，必填 `media_output_path`） |
| `media_output_path` | `s3://` / `gs://` 目录 |

同步上限（配置）：`OFFICE_READ_MAX_PAGES`（默认 40）、`OFFICE_READ_MAX_SOURCE_BYTES`（默认 20MiB）。超限 `isError`，文案只提 `page_range`，不提 parse。输出超 `OFFICE_READ_MAX_OUTPUT_BYTES`（默认 1MiB）仍 `success`，截断并写 `_warnings`。

`_note` 固定：阅读结果不得传入 `office_edit_*`。

### 1.3 正文约定

```markdown
[Page 1]
# 标题
## 小节
段落。**粗** *斜*

- 列表

| A | B |
| --- | --- |
| 1 | 2 |

![图题](media/doc_<id>_<hash>_01.png)

[Page 2]
```

| 类型 | 投影 |
|---|---|
| Word / 数字 PDF | `[Page N]` + 标题/列表/表/强调 |
| PPT | 一幻灯片 = `[Page N]` |
| Excel | 一 sheet = `[Page N]`，注释 `<!-- sheet: Name -->`，正文 CSV（显示值，不公式） |
| 扫描 PDF | DAI OCR → MD；有稳定 `pageStart` 才写 `[Page N]` |

JSON 默认可另给 `pages[].{ page, name, csv }`（Excel）。MD **不含** `block_index` / `shape_index` / `shape_id`。

### 1.4 媒体

抽出 PNG / JPEG / GIF / SVG。命名 `doc_<stable_id>_<hash8>_<seq>.<ext>`。正文 `![alt](media/...)`。单张失败不整篇失败，留空图 + `_warnings`。

`media[]`：`name`、`content_type`、`bytes`、`url`、`page`。zip 包内已含图，与 `media_delivery` 无关。

### 1.5 对调用方的影响（按角色）

| 角色 | 影响 |
|---|---|
| middleware / preview | 只对 `office_read_document` 读 `markdown`/`text`；不要再拼 `{n}\t{text}`。canonical read **不动** |
| 模型编排 | 阅读用 document；编辑用 category fine。禁止 MD 页标 / media URL 进 edit |
| scholar-kg | 继续 `office_parse_document`，本变更不替换 |
| 编辑集成 | 不受阅读线字段删除影响，但不要再把 document 的 `index` 当 locator |

---

## 2. 编辑线总则

工具：`office_read_word|presentation|spreadsheet|pdf`（`format=structured` + `read_mode=fine`）+ 对应 `office_edit_*`。

- 每个可改节点：**同一对象**上带 locator、text、已识别 style。不做「格式包 + id」。
- locator 字段名不改：`block_index` / `slide_index`（0-based）/ `shape_index` / A1 / `page_index`。
- `read_mode=coarse`、PDF `engine=document_ai`、阅读线 MD **不能**当 edit 地址。
- 空节点省略且 **不重编号**。
- 未进本轮、未拍板的对象 **不得写进 TOOL_DEF**。
- `office_create_*` 的字段不自动等于 edit op。

下面「已有」= 今天就能用；「本轮」= P2 要接上；「已写死、稍后」= 名字定了但本轮不实现、不进 TOOL_DEF；「未拍板」= 禁止发明字段。

---

## 3. Word（`office_read_word` / `office_edit_word`）

**目标：** 用 `block_index`（→ `GetElement`）或 `heading_path` / `match_text` 改正文、表、节、页眉页脚。阅读 sidecar 的 runs **不能**当地址。

### 3.1 对象与地址

| 对象 | 地址 | 本轮读字段 | 本轮写 |
|---|---|---|---|
| 段落 / 标题 | `block_index`；标题另有 `heading_path` | 已有 `type`、`text`、`style_name`。补 `runs[]`+`run_index`（`bold`/`italic`/`underline`/`font_name`/`font_size_pt`）、段上 `align`、`list_type`/`list_level` | 已有 `set_block_text`、`set_heading`、`insert_paragraph`、`apply_style`。补 `set_run_format`、`set_paragraph_format`、`set_list`、`move_block` |
| 表格 | 表的 `block_index` + `row`/`col` | 已有 `rows` 字符串网格。补单元格 `text`；格内格式同 run/段 | 已有 `insert_table`。补 `set_cell_text`、增删行列、`delete_table` |
| 页眉 / 页脚 / 页码 | `section_index`，**只 default** | 节上 `header`/`footer` 文本；页码是其中 PAGE 域 | `set_header`、`set_footer`（页码是字段，不单开插页码） |
| 图片 | `block_index`，文档内序号（**不是**阅读线 media URL） | `type=image`、`alt`、尺寸 pt | `insert_image`、`replace_image` |
| 超链接 | `block_index` + `run_index` | run 上 `hyperlink` | `set_hyperlink`、`remove_hyperlink` |

### 3.2 已有 op（保持）

`search_replace`、`set_block_text`、`set_heading`、`insert_paragraph`、`insert_bullets`、`insert_table`、`delete_block`（**表不可删**，ADR-010）、`apply_style`、`add_page_break`、`insert_section_break`、`insert_toc`。

回读约定（落地时写进 description）：

- `set_block_text` = 整段 `SetText`，清掉 `runs[]`。改字和改格式必须两个 op。
- `apply_style` 只写 `style_name`，不写 bold/字号。
- `insert_bullets` 只是字前加「•」，**不是** Word 列表；真列表走 `set_list`。
- `search_replace` 范围（是否含页眉页脚）要写死，与 `block_index` 一致。

### 3.3 本轮要补的 op / 字段

| op / 字段 | 定位 | 写入 |
|---|---|---|
| `set_run_format` | `block_index` + `run_index` 或 `match_text` | 本轮：`bold`、`italic`、`underline`、`font_name`、`font_size_pt`（闭集另有 strike/highlight/font_color，本轮可不写） |
| `set_paragraph_format` | 段 | 只 `align`（`left`/`center`/`right`/`justify`）和 `style_name` |
| `set_list` | 段 | `list_type=bullet\|number`、`list_level` |
| `set_cell_text` | `block_index` + `row` + `col` | 格内文字 |
| `insert_table_row` / `delete_table_row` / `insert_table_column` / `delete_table_column` / `delete_table` | 表 `block_index` + `row`/`col` | 行列 |
| `set_header` / `set_footer` | `section_index` | 文本；页码位置/格式/起始号为字段 |
| `insert_image` / `replace_image` | 锚点 / `block_index` | `source_url` 或字节 |
| `set_hyperlink` / `remove_hyperlink` | `run_index` | URL |
| `move_block` | 源 `block_index` | 目标 `block_index` 或 `heading_path` |

### 3.4 本轮不做（不得进 TOOL_DEF）

图表、文本框、分栏、批注、脚注/尾注、first/even 页眉页脚、合并格、底纹、边框、`heading` 4–6 的完整约定。P3 才做 first/even，且读必须同阶段给出 variant。

---

## 4. PPT（`office_read_presentation` / `office_edit_presentation`）

**目标：** 用 0-based `slide_index` + 原始 `shape_index`（`GetAllShapes()`，过滤后不重编号）改页与形状。禁止阅读线 1-based `slide_index` 和 `shape_id`（`s1-1`）。

### 4.1 对象与地址

| 对象 | 地址 | 本轮读 | 本轮写 |
|---|---|---|---|
| 幻灯片 | `slide_index` | 已有。`layouts[]` 已对齐 ADR-016 | 已有 `add_slide`（`layout` 必须抄 `layouts[]`）、`delete_slide`、`duplicate_slide`、`move_slide` |
| 形状 | `slide_index` + `shape_index` | **本轮：** `type` 闭集 `text` / `image` / `shape`（废弃 `kind`）。图片和空文本框保留原序号。装饰形状仍省略。图片优先于文本框 | 已有 `set_text`、`set_title`、`set_bullets`、`replace_image`、`remove_shape` |
| 占位符 | 同上；`role` = `title`/`body`/`subtitle` | 已有 `placeholder_type`（只读原始值）、`role` | op 收 `role` 或 `shape_index`，不收 `placeholder_type`。多 body 必须带 `shape_index` |
| 备注 | 只有 `slide_index`（不是 shape） | **本轮：** 默认返回非空 `notes`（`include_notes` 默认 `true`）。空则省略 | 已有 `set_notes` |

### 4.2 已有 op（保持）

`set_text`、`set_title`、`set_bullets`、`add_slide`、`delete_slide`、`duplicate_slide`、`move_slide`、`set_notes`、`replace_image`、`remove_shape`。

`replace_image` 用自己的 `url` + 精细读 `shape_index`，不用阅读线 media URL。编辑侧不接受创建侧别名 `bullets`，规范名是 `items`。

### 4.3 本轮只做这两件读

1. 保留图片、空文本框的 **原始** `shape_index`；`type` ∈ {`text`,`image`,`shape`}。
2. 精细读默认带上非空 `notes`。

P2 **不**把 sidecar 的 `runs` / 几何接到 `shape_index`。`layouts[]` 已有，本轮不新做。

### 4.4 已写死、本轮不实现（不进 TOOL_DEF）

| 能力 | 读字段 | 写 op | 何时 |
|---|---|---|---|
| Run 格式 | `runs[]`+`run_index`，闭集同 Word | `set_run_format`（本轮写入集同 Word） | 稍后。`set_text` 整段替换会清 runs |
| 几何 / 插文本框 | `x_pt` `y_pt` `width_pt` `height_pt` | `set_shape_geometry`、`insert_textbox`（插完再读，不承诺新 `shape_index`） | 稍后 |
| 框内对齐 | shape 上 `align` | `set_paragraph_format` | 稍后。形状相对幻灯片对齐、组合 **排除** |
| 填充 / 线 | `fill_color` `line_color` `line_width_pt` | `set_shape_fill` / `set_shape_line` | 排除本轮；`highlight` ≠ 填色 |
| 母版 | `layout_name` + `shape_index`（`layout_name` ∈ 该次 `layouts[]`） | 与读同阶段的母版 op | **P3**。不引入 `master_index` |

---

## 5. Excel（`office_read_spreadsheet` / `office_edit_spreadsheet`）

**目标：** 用 `sheet_name`/`sheet_index` + A1 改格子。阅读线 CSV **不能**回写。

### 5.1 对象与地址（已有 + 已写死）

| 对象 | 地址 | 读 | 写 |
|---|---|---|---|
| 工作表 | `sheet_index`（工作簿 0-based，过滤不重编号）或 `name`。都给时 **`sheet_name` 优先** | 已有 `sheets[]`、`used_range`、`headers`（= 本次 `rows[0]`，不是 edit 地址） | 已有 `add_sheet`（只 `name`）、`delete_sheet`（必须带表）、`rename_sheet`（必须 `sheet_name`+`new_name`）、`copy_sheet`。新表 **不承诺** `sheet_index` |
| 单元格值 | A1 `cell` / `range`。原点 = 本次 `used_range` 左上角，**不是** `rows[r][c]` | 默认显示值 | `set_cell`（`value`）、`set_range`、`clear_range`（**只清值和公式**） |
| 公式 | 同上 `cell` | 不另设 `formula` 字段。`include_formulas=true` 时该格 `rows` 换成公式字符串（保留 `=`） | `set_formula`（`cell`+`formula`）。与 `set_cell` 不混用 |
| 行插入/删除 | 工作表 **1-based** `at_row` / `from_row` | — | `insert_rows`、`delete_rows`。不能用 `r+1`，除非 used_range 从第 1 行起 |

`rows[r][c]` → A1：解析 `used_range` 左上角 `(row0,col0)`，列 = `col0+c`，行 = `row0+r+1`。`options.range` 先裁再改 `used_range`。禁止把 `r`/`c` 当 op 的 `row`/`col`（ADR-015）。

### 5.2 已有 op（保持）

`set_cell`、`set_range`、`clear_range`、`insert_rows`、`delete_rows`、`add_sheet`、`delete_sheet`、`rename_sheet`、`set_formula`、`copy_sheet`。

### 5.3 已写死、P2 不实现（不进 TOOL_DEF）

`include_styles=true` 时 sheet 另给 `cell_styles[]`（16 字段，不进 `rows`）+ `column_widths[]` + `row_heights[]`。

写入：`set_cell_style`（`cell`/`range`，缺省保持，`null` 清单项）、`clear_format`（只清 16 字段）、`set_column_width`、`set_row_height`。

16 字段：`number_format`、`fill_color`、`border_*`、`border_color`、`bold`、`italic`、`underline`、`strike`、`font_name`、`font_size_pt`、`font_color`、`align`、`vertical_align`。`fill_color` ≠ Word `highlight`。

`clear_range` 落地样式后改为只清内容，格式留下。

### 5.4 未拍板（禁止发明字段）

合并区、图表、数据验证、条件格式。

---

## 6. PDF（`office_read_pdf` / `office_edit_pdf` / `office_fill_pdf_form`）

**目标：** 只用 DS fine 的 0-based `page_index`（+ 现有页级 op）。DAI / coarse / `[Page N]` **不是** locator。

### 6.1 对象与地址

| 对象 | 地址 | 读 | 写 |
|---|---|---|---|
| 页 | `page_index` | 已有 `pages[]`/`blocks` | `add_page`、`delete_page`（后面页号前移，必须再读）、`rotate_page`（`90/180/270`；再读暂无 `degrees`） |
| 段 / 表（只读网格） | `page_index` + `block_index` | `type=paragraph\|table`，`text` 或 `rows` | **没有**收 `block_index` 的改块 op。`add_paragraph` 追加页末。`set_page_text` **整页重建**，旧 `block_index` 作废 |
| 批注 | 无稳定 id | 仅 `include_annotations=true`：`kind`（DS 类名）+ `text`，无 `rect` | `add_annotation`：`kind`∈{`freetext`,`highlight`} + `rect`。读写 `kind` **不是**同一闭集 |
| 表单 | 字段 `name` | `form_fields[]`：`name`、`type`、`value` | `office_fill_pdf_form` 按 `name` 写 `value`。无 `page_index` |

### 6.2 已有 op（保持）

`add_paragraph`、`set_page_text`、`add_page`、`delete_page`、`rotate_page`、`add_annotation`；表单 `office_fill_pdf_form`。

`add_paragraph` / `set_page_text` 可写 `align`（`left`/`center`/`right`）。无字体族/字号。`bold` 在 create / `set_page_text` 块上，不在 `add_paragraph`。

### 6.3 本轮 / P3

PDF 样式、块改写、单元格、图替换、书签：**没有一行同时具备同名读字段和 op**。本轮与 P3 **都不写进 TOOL_DEF**，直到三边对齐。

---

## 7. Builder（不变）

| 工具 | 入 | 出 |
|---|---|---|
| `office_execute_builder` | `script` 或 `.docbuilder` `url` + 可选 `argument` | 生成文件 |
| `office_edit_word_script` | 已有 Word + 中间 JS（MCP 注 Open/Save/Close） | 改后的 Word |
| `office_call_api` | convert / forcesave / info | API 原样 |

自定义 JSON **不会**变成官方 `markdown` 或 `units[]`。

---

## 8. 阶段对照（实现排期）

| 阶段 | 做 | 不做 |
|---|---|---|
| **P0** | 阅读线切 MD；`format`/`accept`；页标；Excel 多 CSV；DAI 扫描；同步上限 + `page_range` | 不留 `elements[]` |
| **P1** | 抽 media；`fetch_token` / `caller_bucket`；zip | — |
| **P2** | Word：§3.3。PPT：§4.3 两件读。Excel/PDF 样式不实现 | PPT runs/几何；Excel `cell_styles`；PDF 新 op；未拍板项 |
| **P3** | Word first/even（读+编同阶段）；PPT 母版（`layout_name`+`shape_index` + 同阶段写 op） | 整份 §5 backlog；形状对齐/组合；Excel 合并/图/校验；PDF 未对齐行 |

---

## 9. 回归与误用

1. 现有 `office_edit_*` 用 **fine structured** 的旧 locator 必须仍能打中（P2 只加字段，不改序号规则）。
2. 单测：阅读线拒 `structured`/`text`；MD 无 locator 字段；编辑线 coarse/DAI 的 `_locator_note` 仍禁止 edit。
3. 误用矩阵：

| 误用 | 正确 |
|---|---|
| `office_read_document` 的 `[Page N]` → `page_index` | `office_read_pdf` fine |
| 阅读线 `![…](media/…)` → `replace_image` | 精细读 `shape_index` / `block_index` + 自己的 `url` |
| document 的 `s1-1` → PPT edit | `office_read_presentation` 的 `shape_index` |
| `rows[0][0]` 当 `A1` | 用该次 `used_range` 换算 |
| 大文档改调 parse | 同一 `office_read_document` + `page_range` |
