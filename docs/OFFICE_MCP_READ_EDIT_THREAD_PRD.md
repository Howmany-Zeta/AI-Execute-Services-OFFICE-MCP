# Office MCP 解析 & 编辑线程收束 PRD

> **状态**：草案（目标态；未实施）  
> **范围**：`AI-Execute-Services-OFFICE-MCP` 读 / 编 / Builder  
> **原则**：对外工具名与入参契约不变，变内部行为与出站语义  
> **读者**：产品、Office MCP 实现、middleware / 模型调用方

本文把现有混在一起的三条能力收成三条线，并写清**现状 → 目标**。as-built 事实来自当前源码，不是愿望。

---

## 1. 问题

现在调用方看到的是同一套 `format=structured|text|outline`，底下却是三种不同东西：

| 实际出站 | 今天落在哪 | 样式 | 编辑地址 |
|---|---|---|---|
| 纯文本 | 各 read 的 `format=text` | 无 | 无 |
| 富语义 / 部分 run 样式 | `office_read_document` structured（Word/PPT sidecar；PDF=DAI） | Word/PPT 有 `runs` | **无**（`index` 禁止 `GetElement`） |
| 可定位薄包 | `office_read_{word,presentation,pdf,spreadsheet}` fine structured | **基本无** | 有（fine + 非 DAI） |

后果：

1. `format=structured` 在 legacy 与 canonical 上不是同一种包。
2. 模型容易拿 `office_read_document` 的 `index` / `shape_id` 去 edit。
3. 要编辑的人拿不到 run / 页眉 / 母版；要阅读的人拿到 JSON 树而不是干净 MD。
4. 图片被 Word sidecar 直接跳过；Excel 走 csv `elements`；PDF DAI 与 DS 页块混用。
5. `office_parse_document` 已有异步 markdown，和 `office_read_document` 再叠一层。

---

## 2. 目标与非目标

### 2.1 目标

对外收成三条线，职责互不借用：

```
阅读理解  →  office_read_document          → 干净 MD（+ 可选 media）
精细编辑  →  office_read_{category} fine   → 全格式 + 编辑地址
自定义    →  office_execute_builder
            office_edit_word_script        → 开发者脚本，MCP 不解释语义
```

1. **工具名、入参主体不变**（`source_url` / `content_base64` 仍在）。阅读线 `format` 只接受新名，见 §4.2。旧 `structured`/`text` **不收**，调用方自己改。
2. `office_read_document` **只用于模型阅读**。出站统一为干净 MD；说明与 `_note` 写死：不能用于 `office_edit_*`。
3. 各 `office_read_{category}` **只用于编辑准备**：源文档结构 + 样式 + 与 `office_edit_*` 对齐的地址。
4. Builder 网关保持独立，不接入官方 MD / units 契约。

### 2.2 非目标（本 PRD 不做）

- 不改 `list_tools` 工具集合，不新增「office_read_markdown」一类名字。
- 不把 `office_read_document` 转调 canonical fine（继续遵守 ADR §11.2 行为隔离，只换它自己的内部投影）。
- 不让 Builder 自定义脚本的 JSON 自动变成官方 `units[]`。
- 不在本阶段做「格式包 + 正文包 + id 对连」的双包协议。编辑线把 **locator + text + style 写在同一对象上**。
- 不在本 PRD 实施编辑 op 全集（§6 能力表里「待补充」先对齐再开独立 PRD）。

### 2.3 「对外接口不变」口径

| 不变 | 允许变 |
|---|---|
| 工具名 | `office_read_document` 的 **structured 出站体**（`elements[]` → MD 契约） |
| 入参：`source_*`、`content_base64` | 阅读线 `format` **只**接受 `markdown` / `plain` / `outline`。传入 `structured`/`text` → `err` |
| `office_read_*` / `office_edit_*` / Builder 名字 | 编辑线 **补** 样式字段，不改现有 locator 字段名 |
| `list_tools` 仍不暴露 legacy 名 | description / `_note` 改成「只读 MD」 |

**明确打破的只有一件：** `office_read_document` 不再返回 `elements[]`+`runs`，P0 **直接切 MD**（不并行双字段）。本仓库不改 middleware；出 [CHANGELOG](./CHANGELOG_OFFICE_READ_DOCUMENT_MD.md) 供其它团队改。canonical `units` / `block_index` 字段名保持。

---

## 3. 三条线

### 线 A — 阅读（`office_read_document`）

**对外说法：** 只给模型理解文档内容。禁止把任何下标、页码、图片 URL 当作 `office_edit_*` 参数。

内部一律投影成 Markdown（Excel 为 CSV 文本，按页包装，见 §4.4）。

### 线 B — 编辑（`office_read_{category}` + `office_edit_{category}`）

**对外说法：** 读完即可改。出站必须同时有：

- 编辑地址（与 Builder / A1 / 页块对齐）
- 该地址上的可见文本
- 该地址上已识别的格式（目标态；今天大部分没有）

`read_mode=coarse`、PDF `engine=document_ai` **继续不能**当 edit locator。

### 线 C — Builder（`office_execute_builder` / `office_edit_word_script`）

开发者自带脚本。MCP 只跑 DS `/docbuilder`，回 **文件**（`content_base64` / `output_path`）。不保证、不解析为 MD 或 `units[]`。

---

## 4. 线 A：阅读 MD 契约

### 4.1 页标与标准 MD

默认正文（Word / PPT / 数字 PDF）：

```markdown
[Page 1]
# 标题
## 小节
正文段落。

- 列表项
- 列表项

| 列A | 列B |
| --- | --- |
| 1 | 2 |

![图题](media/doc_<id>_<hash>_01.png)

[Page 2]
...
```

规则：

| 项 | 约定 |
|---|---|
| 页界 | 单独一行 `[Page N]`，`N` 从 1。对应原文档逻辑页 / PPT 幻灯片 / Excel 的一个 sheet |
| 标题 | ATX `#`～`######`，来自 heading / title / outline |
| 列表 | `-` 或有序 `1.`；能区分则区分，不能则无序 |
| 表格 | GitHub 风格 pipe table |
| 引用 | `>` |
| 强调 | `**bold**` / `*italic*`（有 run 才转；没有则纯文本） |
| 图 | 标准 `![alt](media/...)`，见 §4.3 |
| 干净 | 已有 `sanitize_text`：去 C0、空段不出、空 textbox 不出 |
| 禁止 | 不输出 `block_index` / `shape_index` / `shape_id` 当正文 |

PPT：一页幻灯片 = `[Page N]`。  
扫描 PDF：有稳定 `pageStart` 则写 `[Page N]`；扫描件判定失败（无可靠页界）再省略。见 §4.5。

### 4.2 内容与包装（业界 MIME 名）

不用 `return_mode=document` / `format=text` 这种易混名。阅读线拆成两维，名称跟常见 `Accept` / export 对齐：

**内容 `format`（这份是什么字）：**

| `format` | 内容 | 对应 MIME |
|---|---|---|
| `markdown`（默认） | 完整 MD（标题/列表/表/图引用） | `text/markdown` |
| `plain` | 无标记纯文本 | `text/plain` |
| `outline` | 仅标题的 MD | `text/markdown`（只要 heading） |

`structured`、`text` **不是**合法值。传入则 `err`（`format must be markdown, plain, or outline`）。不设别名、不静默映射。

**包装 `options.accept`（怎么把字交出去）：**

| `accept` | 出站 | 对应 MIME |
|---|---|---|
| `application/json`（默认） | `{ markdown\|text, media, page_count, title, ... }` | JSON 里嵌正文 |
| `text/markdown` | 顶层 MD 字符串（`format` 须是 `markdown` 或 `outline`） | 只要文章 |
| `text/plain` | 顶层纯文本（`format=plain`；其它 format 会剥标记） | 只要字 |
| `application/zip` | `content_base64`：`document.md` + `media/` | 落盘 |

默认：`format=markdown` + `accept=application/json`。  
`office_read_{category}` **不改**，仍是 `structured` / `text` / `outline`。

`_note` / description **固定**：

> For model reading only. Do not pass any index, page marker, or media URL to office_edit_*.

### 4.3 富媒体：分离存储 + 引用映射

Word sidecar 今天跳过 drawing/image/ole。目标：

1. 从包内 `media/`（及等价关系）抽出 PNG / JPEG / GIF / SVG。
2. 统一命名：`doc_<stable_id>_<content_hash8>_<seq>.<ext>`。`stable_id` 优先源文件指纹，其次本次 read id。
3. 媒体投递两种，由调用方显式选（不靠猜「是否同一网」）：
   - **`options.media_delivery=fetch_token`（默认，无 bucket 时）**：复用现有 staging / `MCP_PUBLIC_URL` fetch token，给同网内部调用。TTL 短。
   - **`options.media_delivery=caller_bucket`**：外部调用方必填 `media_output_path`（`s3://` / `gs://` 前缀目录），图上传到调用方桶；`media[].url` 为该对象地址。
4. 正文占位换成 `![alt](media/<filename>)`；json 模式另给 `media[]`：

```json
{
  "name": "doc_ab12_9f3c_01.png",
  "content_type": "image/png",
  "bytes": 12345,
  "url": "https://…/fetch/…",
  "page": 2
}
```

图表 / 图标：能导出位图或 SVG 则当图；导出不了则一行 alt 文本，不假装有图。  
`accept=application/zip`：`document.md` + `media/`。zip 内图片与 `media_delivery` 无关（已打进包）。  
失败策略：单张失败不整篇失败，该处留 `![alt]()` 并在 `_warnings` 记一条。

### 4.4 Excel → 多 CSV、一 sheet 一页

阅读线 **不** 输出 `sheets[].rows` JSON。

- 每个 sheet 转一份 CSV 文本。
- 包装为：

```markdown
[Page 1]
<!-- sheet: Sheet1 -->
colA,colB
1,2

[Page 2]
<!-- sheet: Sheet2 -->
...
```

`page_count` = sheet 数。json 模式可另给 `pages[].{ page, name, csv }` 便于调用方拆文件。  
公式：阅读线出**显示值**；公式留给编辑线 `include_formulas`。

### 4.5 PDF

| 文档形态 | 引擎 | MD 页标 |
|---|---|---|
| 数字 PDF（有字） | 优先 DS 抽字 → MD；结构不足再 DAI | 有可靠页界则 `[Page N]` |
| 纯图 / 扫描件 | **必须 DAI** OCR 后再做成 MD | **有稳定 `pageStart` 就写 `[Page N]`**；扫描件判定失败、无可靠页界才省略。页标不能当 `office_edit_pdf` 的 `page_index` |

判定「扫描件」：无可见字或 `document_has_structure` 失败且文本密度过低。  
DAI 出站 **只进线 A**。`office_read_pdf` 默认 DS 不变。

### 4.6 大文档（仍走阅读线）

同步硬上限（页数、字节，实施时写入配置）。超限：

- 仍调用 `office_read_document`，**不**改走 `office_parse_document`
- 未带 `options.page_range` → `err`，文案只提缩小 `page_range` 续读
- 带 range → 只投影该区间 MD

`office_parse_document` 继续只服务 scholar-kg 异步落库。

### 4.7 与 `office_parse_document` 的边界

| | `office_read_document` | `office_parse_document` |
|---|---|---|
| 同步性 | 同步 tools/call | 异步 job + 对象存储 |
| 受众 | 模型当场阅读 | scholar-kg / 派生 canonical.md |
| 本 PRD | 同步 MD，大文档也走这条（有页数/字节上限 + `page_range` 续读） | **不退役**；内部投影复用同一套 MD 规则 |

---

## 5. 线 B：编辑准备读

### 5.1 出站原则

`office_read_{word,presentation,spreadsheet,pdf}` 的 `format=structured` + `read_mode=fine`：

- 继续走 `build_read_response`（`units` + `blocks`/`slides`/`sheets`/`pages`）。
- **每个可改节点同一对象上带齐**：locator、text、type、已识别 style/runs。
- 不把阅读线的 `[Page N]` MD 当作 edit 输入。
- 省略空节点时 **不重编号**（已有卫生规则）。

今天缺口：canonical fine **几乎没有样式**（Word ToJSON 无 runs；PPT 无几何/runs；PDF 无字体；Excel 无单元格格式）。目标是补上，而不是再开一个「格式包」。

### 5.2 Word（编辑读 + 编）

按对象对齐。每一行的读、op、目标使用同一套类型名和字段名。阅读线里的页眉、页脚、脚注、目录、题注、文本框、图片只是 Markdown 投影，不能当成编辑地址。

**读（今天）：** `block_index`、`type`（`paragraph` / `heading1`–`heading3` / `table`）、`text`、有样式时的 `style_name`、标题的 `heading_path`，以及表的 `rows` / `row_count` / `col_count`。没有 run、对齐、列表、节、页眉页脚、脚注、图片或文本框。

精细读写指 `office_read_word`（`read_mode=fine`）和 `office_edit_word`。阅读线 sidecar 已经能抽出字体、字号、对齐，但那条线不能当编辑地址，fine read 也没有接这些字段。

**已有 op：** `search_replace`、`set_block_text`、`set_heading`、`insert_paragraph`、`insert_bullets`、`insert_table`、`delete_block`（表不可删，ADR-010）、`apply_style`、`add_page_break`、`insert_section_break`、`insert_toc`。回读约定见下文；未进该阶段的对象不写进 `office_edit_word` 的 description。

#### 每个目标要补的三边

对象总表。本轮范围见下文两节「本轮要补」：字体、字号、对齐、单元格文字，以及加粗/斜体/下划线、真列表、表格行列、页眉页脚页码、图片、超链接、移动块。图表、文本框、分栏、批注、脚注，以及合并格、底纹、边框，不在本轮。

| 编辑目标 | 编辑读要补的地址和字段 | 编辑 op 要补的写入 | 现在缺的对应关系 |
|---|---|---|---|
| 页眉 / 页脚 | 节上的 `header` / `footer` 文本，地址用 `section_index`。本轮只出 default；`first` / `even` 不在本轮 | `set_header`、`set_footer` | 正式文档几乎都会改。读今天没有这两段文本。P3 要改 first/even 时，读必须同一阶段给出这两种 variant，否则没有地址 |
| 页码 | 页眉或页脚中的 PAGE 域，不把排版后的页码数字当地址 | `set_header` / `set_footer` 的一个字段（位置、格式、起始号）。不单开「插页码」 | 和页眉、页脚是同一处，读侧今天没写 |
| 脚注 | `type=footnote`，`footnote_id`，正文里的引用点（`block_index` + `run_index`），注本体的 text / runs | `insert_footnote`、`set_footnote_text`、`delete_footnote`，参数用同一个 `footnote_id` | 读写「脚注」，目标写「注释」。注释要拆成脚注、尾注、批注三条，不能合成一个 op |
| 批注 | `comment_id`、锚点（`block_index` + 可选 `run_index`）、正文 | `insert_comment` / `set_comment` / `delete_comment` | 目标里的「注释」若指批注，读和 op 都还没有这个对象 |
| 尾注 | 与脚注同一形状，`type=endnote` | 与脚注同一组 op，用 `type` 区分 | 三边都没写。要做就和脚注一起定义；不做就在目标里明确排除 |
| Run 字符格式 | 块内 `runs[]`，每条有 `run_index` 和可见 `text`。字段闭集：`bold`、`italic`、`underline`、`strike`、`highlight`、`font_name`、`font_size_pt`、`font_color`。`hyperlink` 不在这 8 个字段里 | `set_run_format`：定位 = `block_index` + `run_index`（或一段 `match_text`），参数名与读的字段逐个相同。本轮写入 `bold`、`italic`、`underline`、`font_name`、`font_size_pt` | 创建只能给新段落加粗，编辑改不了已有字。`apply_style` 只接收 `style_name`，不能代替 run。`填充` 要定成 run 的 `highlight`，或改指段/单元格底纹，三处用同一个词 |
| 段落格式 | 段上的 `align`（闭集 `left` / `center` / `right` / `justify`；写在段上，不写在 run 上）、`style_name`。列表是段上的 `list_type=bullet\|number`、`list_level`，不写进 `align` | `set_paragraph_format` 只写 `align` 和 `style_name`。对齐不单开 `SetJc`。列表走 `set_list` | 精细读没有 `align`，编辑侧也没有 `SetJc`。`insert_bullets` 只在文字前加「• 」，不是 Word 列表 |
| 列表 | 段上的 `list_type=bullet\|number`、`list_level` | `set_list` 写这两个字段。改已有列表不用删了再插 | `insert_bullets` 不是 Word 列表，续号和缩进都会乱 |
| 超链接 | run 上的 `hyperlink`，地址用 `run_index` | `set_hyperlink`、`remove_hyperlink` | 正文里加链接、改链接没有对应 op |
| 移动块 | 现有 `block_index` | `move_block`，目标位置用另一个 `block_index` 或 `heading_path` | 现在只能删了再插，格式会丢，后面的 `block_index` 也会变 |
| 标题级别 | `heading_level`（建议 1–6，与阅读线 `outline_level+1` 上限一致）和 `heading_path` | `set_heading` 增加 `heading_level`，并写明与 `style_name`（`Heading N`）是同一事实的两种写法 | 读要 level，op 只有 `style_name`。解析器只认 Heading 1–3，4–6 和 `outline_level` 没有编辑约定 |
| 表格单元格 | 表块保留 `block_index`、`rows`（字符串网格）、`row_count`、`col_count`。单元格补 `row`、`col`、`text`。格内字体、字号、对齐、加粗/斜体/下划线用与正文相同的 run / 段字段。增删行列用已有 `block_index` 加上 `row`、`col` | 改字用 `set_cell_text`。字体和字号、加粗/斜体/下划线走 `set_run_format`，对齐走 `set_paragraph_format` 的 `align`。增删行列：`insert_table_row`、`delete_table_row`、`insert_table_column`、`delete_table_column`。删整表用 `delete_table`（`delete_block` 不能删表，ADR-010） | 整表文本已有，缺单元格，也缺在已有表上增删行列。合并格、底纹、边框本轮不补；sidecar 表格只抽了单元格文字。`insert_table` 只插整表字符串网格 |
| 分节 / 分栏 | `type=section`，`section_index`，`break_type`（next / continuous / even / odd），`columns`（栏数、栏宽）。`different_first_page`、`odd_even_headers` 决定页眉 variant 是否存在 | 现有 `insert_section_break` 补上 `break_type`。另给 `set_section` 写栏数和上述两个旗标 | 目标写「双栏 / 分栏」，op 没有栏参数，读没有节节点。「插页」要定义成某种 `break_type`，或定义成已有的 `add_page_break`，不能再单列一个没有字段的目标 |
| 分页符 | `type=page_break` 也占一个 `block_index`，空段继续省略且不重编号 | 已有 `add_page_break`。删除走 `delete_block` | 读不出分页符，插完无法再定位。和「插页」、分节符要写成三个不同的 type |
| 目录 | `type=toc`，自带 `block_index` | 已有 `insert_toc`。补 `delete_block` 是否允许删目录，以及有没有 `update_toc` | 读不把目录当块。创建侧的 `add_toc` 与这个 op 的插入位置（文首还是 operations 当前位置）要写成同一条规则 |
| 题注 | `type=caption`，`block_index`，所附对象的地址（表或图） | `insert_caption` / `set_block_text` | 阅读线会出题注文字，编辑三边都没有这个对象 |
| 图片 | `type=image`，`block_index` 或锚点，`alt`，尺寸（pt）。地址是文档内序号，不是阅读线的 `media/` URL | `insert_image`、`replace_image`、`delete_block`。来源用 `source_url` / 字节，不用阅读线 URL | 目标有「插入图片」，读和 op 都没有字段。阅读线禁止把 media URL 传给 `office_edit_*`，这条要写进 Word 编辑节 |
| 图表 | `type=chart`，锚点，图表类型，数据范围或内嵌表。它是可编辑图表，不是阅读线导出的 PNG | `insert_chart`、`set_chart_data`、`delete_block` | 目标有「图表」，没有数据字段。阅读线的图表导出图不能当作这个对象 |
| 文本框 | `type=textbox`，`block_index`，`text`，`runs[]`，几何（pt）。空文本框省略且不重编号 | `insert_textbox`、`set_block_text`、几何用 `set_textbox_geometry` | 目标有「文本框」。阅读线只把有字的文本框投影成普通段落，编辑读必须单独成块，否则无法改框本身 |

#### 已有 op 上要补的回读约定

这些 op 已经存在，缺的是写完之后读回什么，以及和上表字段的关系。

- **`search_replace`**：写明搜索范围是仅正文，还是包含页眉、页脚、脚注、文本框。新故事类型落地后，这条不写就会和 `block_index` 定位不一致。
- **`set_block_text`**：整段 `SetText`，会清掉原有 `runs[]`。字体和字号落地之后，改字和改格式必须分成两个 op，否则读回的 `font_name`、`font_size_pt` 对不上。
- **`apply_style`**：保留为「套用样式名」。读继续出当前 `style_name`。它不写入 bold、字号、颜色；那些只走 `set_run_format`。
- **`insert_paragraph` / `insert_bullets` / `insert_table`**：插入位置继续用 `block_index` / `heading_path` / `match_text` / `after`。`insert_bullets` 只是在文字前加「• 」，不是 Word 列表；编号和层级走 `set_list`，不靠改 `items` 来假装列表。创建侧已有的 `level`、`header_row`、段落 `bold` 要么升进对应 op 和读字段，要么标明只属于 `office_create_word`。段落 `bold` 的编辑写入是 `set_run_format`。
- **`delete_block`**：表仍不可删。目录、图片、图表、文本框、分页符各自标明允许或不允许。
- **`set_heading`**：`heading_level` 与 `style_name` 二选一，读回只保留一个规范字段。
- **`add_page_break`、`insert_section_break`、`insert_toc`**：对应的 `page_break`、`section`、`toc` 块必须出现在 fine read 里，否则下次编辑没有地址。

#### 公共规则

1. 定位只使用编辑读发出的字段：`block_index`、`heading_path`、`match_text`，以及上表的 `section_index`、`run_index`、`row`/`col`、`footnote_id`。`[Page N]`、阅读线 media URL、`shape_id` 不进入任何 Word op。
2. 同一属性在读和 op 上同名。run 的 8 个格式字段、段的 `align`、列表的 `list_type` / `list_level`、节的 `break_type` / `columns` 各出现一次。列表只走 `set_list`，不写进 `set_paragraph_format`。`hyperlink` 不计入那 8 个字段，走 `set_hyperlink` / `remove_hyperlink`。
3. P2 与 P3 成对。P2 的读只承诺 `default` 页眉页脚和正文 run/段/单元格字段；对应的写入 op 若放在 P3，P3 的读必须先或同时给出 first/even、分栏旗标和图表数据。未进该阶段的对象不写进 `office_edit_word` 的 description。
4. 空节点继续省略且不重编号。新增的页眉、脚注、文本框、分页符也遵守这条，避免 `block_index` 和 `GetElement` 错位。

#### 本轮要补：字体、字号、对齐、单元格

字体、字号、对齐在精细读写两边都还没有。表格的整表文本已经有，缺的是单元格这一层，以及单元格里的这三项格式。阅读线 sidecar 已能抽出字体、字号、对齐，但不能当编辑地址。

| 项 | 现在的精细读 | 现在的编辑 op | 要补的对应 |
|---|---|---|---|
| 字体 | 只有整段 `text`，无 `font_name` | 没有。`apply_style` 只写样式名 | 段内 `runs[]` 带 `run_index` + `font_name`；op `set_run_format` 用同一字段写回 |
| 字号 | 无 `font_size_pt` | 没有 | 与字体同一条 run、同一个 op |
| 对齐 | 无 `align` | 没有 `SetJc` | 写在段上，不写在 run 上。闭集先定 `left` / `center` / `right` / `justify`。op 用 `set_paragraph_format` 的 `align` |
| 表格 | 已有 `block_index`、`rows`（字符串网格）、`row_count`、`col_count` | 已有 `insert_table`（整表插入）。不能改已有单元格；`delete_block` 不能删表 | 单元格补 `row`、`col`、`text`。改字用 `set_cell_text`。单元格内的字体、字号、对齐用上面同一套 run / 段字段 |

`set_block_text` 是整段 `SetText`，会清掉原有 run。字体和字号落地之后，改字和改格式必须分成两个 op，否则读回的 `font_name`、`font_size_pt` 对不上。

合并格、底纹、边框这次不用加。目标里没把它们和字体、字号、对齐放在一起，sidecar 的表格也只抽了单元格文字。

#### 本轮还要补：7 类高频操作

除了字体、字号、对齐和单元格文字，精细编辑还缺下面 7 类。图表、文本框、分栏、批注、脚注出现得少，这轮不用补。

| 操作 | 为什么高频 | 读要有 | 写要有 |
|---|---|---|---|
| 加粗 / 斜体 / 下划线 | 比改字体族更常见。创建只能给新段落加粗，编辑改不了已有字 | run 上的 `bold`、`italic`、`underline` | 跟字体、字号同一个 `set_run_format` |
| 真正的编号列表和层级 | 现在的 `insert_bullets` 只是在文字前加「• 」，不是 Word 列表，续号和缩进都会乱 | 段上的 `list_type=bullet\|number`、`list_level` | `set_list` 写这两个字段。改已有列表不用删了再插 |
| 表格增删行列、删除整表 | 已有表上加一行，比整表重插常见。`delete_block` 不能删表 | 已有 `block_index` 加上 `row`、`col` 就够 | `insert_table_row`、`delete_table_row`、`insert_table_column`、`delete_table_column`、`delete_table` |
| 页眉、页脚、页码 | 正式文档几乎都会改 | 节上的 `header` / `footer` 文本；页码是其中的 PAGE 域 | `set_header`、`set_footer`，页码是它们的一个字段 |
| 插入和替换图片 | 标志、截图、插图 | `type=image` 的 `block_index` 和 `alt`。不用阅读线的图片 URL | `insert_image`、`replace_image` |
| 超链接 | 正文里加链接、改链接没有对应 op | run 上的 `hyperlink` | `set_hyperlink`、`remove_hyperlink`，地址用 `run_index` |
| 移动段落或标题 | 「把这段挪到某标题下」现在只能删了再插，格式会丢，后面的 `block_index` 也会变 | 现有 `block_index` | `move_block`，目标位置用另一个 `block_index` 或 `heading_path` |

### 5.3 PPT（编辑读 + 编）

`layouts[]` 与 `add_slide` / `office_create_presentation`（ADR-016）已经对齐，0-based `slide_index` 也已经对齐。编辑地址继续用 `slide_index` + `shape_index`，字段名跟 Word 已拍板的那套对齐。P2 仍然只出 `layouts[]`，不把 sidecar 的 runs / 几何接到 `shape_index`。

**已有 op：** `set_text`、`set_title`、`set_bullets`、`add_slide`、`delete_slide`、`duplicate_slide`、`move_slide`、`set_notes`、`replace_image`、`remove_shape`。

禁止用 `office_read_document` 的 1-based `slide_index` 或 `shape_id`（`s1-1`）。阅读线 media URL 不进入 `office_edit_*`。`replace_image` 用自己的 `url` 加上精细读的 `shape_index`。

本轮只落地两件：保留图片和空文本框的原始 `shape_index`（废弃 `kind`），以及精细读默认带上非空 `notes`。其余行字段名已写死，不进本轮，落地前不得写进 `TOOL_DEF`。

#### 每个目标要补的三边

| 编辑目标 | 编辑读 | 编辑 op | 对应关系 |
|---|---|---|---|
| Shape runs | 精细读只有 `text`。没有 `runs[]`、`run_index`。sidecar 的 runs 在阅读线上，不能当编辑地址 | `set_text`、`set_title`、`set_bullets` 只写纯文本 | **已写死，不在本轮。** 每条 run 用 Word 同一闭集：`bold`、`italic`、`underline`、`strike`、`highlight`、`font_name`、`font_size_pt`、`font_color`。`hyperlink` 不进这 8 个字段。写入 op 是 `set_run_format`，本轮只写 `bold`、`italic`、`underline`、`font_name`、`font_size_pt`。地址是 `slide_index` + `shape_index` + `run_index` |
| Type（废弃 `kind`） | 字段名用现有的 `type`。闭集三个：`text`（有可见文字的形状，含占位符）、`image`、`shape`（空文本框）。占位符不是第四种 type，继续用 `placeholder_type` 和 `role` | `replace_image`、`remove_shape` 需要原始 `shape_index` | **本轮落地。** `shape_index` 是该页 `GetAllShapes()` 的原始序号，过滤后不重编号。`type=image` 和空文本框必须出现。无文字、又不是图片或文本框的装饰形状继续省略。图片和文本框同时成立时，图片优先 |
| 几何与文本框 | 编辑侧不用创建侧的 `position` / `size`。shape 上的字段是 `x_pt`、`y_pt`、`width_pt`、`height_pt` | `set_shape_geometry`，定位 `slide_index` + `shape_index`。`insert_textbox` 追加到该页形状树末尾 | **已写死，不在本轮。** 同一次 `operations` 里不为新形状承诺 `shape_index`，插完再读。空文本框保留并占序号，不套用 Word「空段省略」 |
| 填充与线条 | 以后若做，字段在 shape 上：`fill_color`、`line_color`、`line_width_pt` | 同名字段，例如 `set_shape_fill`、`set_shape_line` | **排除。** 不进 runs / 几何那一轮。`highlight` 只表示 run 高亮，不表示形状填充 |
| 框内文字对齐 | `align` 写在 shape 的文本上，不写在 run 上。闭集 `left` / `center` / `right` / `justify` | `set_paragraph_format` 的 `align`，定位 `slide_index` + `shape_index`。一个 shape 先只有一个对齐，不加 `paragraph_index` | **已写死，不在本轮。** 形状相对幻灯片的对齐、以及组合，不叫 `align`，也不设 `group_id`。这两项排除 |
| 母版 | P2 的读只有 `layouts[]` 名字列表 | 没有 op | **已写死，P3 才读母版形状。** 地址是 `layout_name` + `shape_index`。`layout_name` 必须属于该次读到的 `layouts[]`。不引入 `master_index`。多母版不在第一刀。`slide_index` 只表示幻灯片 |
| 占位符 vs 标题 / 项目 | `role` 闭集 `title` / `body` / `subtitle`。`placeholder_type` 只作为读出的原始值 | `set_title` / `add_slide.title` → `role=title`；`set_bullets` 的 `items` / `add_slide.items` → `role=body`；`add_slide.subtitle` → `role=subtitle`。op 收 `role` 或 `shape_index`，不收 `placeholder_type` | **已写死，不在本轮。** 同一页有多个 body 时，省略 `shape_index` 的 `set_bullets` 和 `role=body` 只打中 `shape_index` 最小的那一个；第二个必须带 `shape_index`。规范名是 `items`。`office_create_presentation` 的 `bullets` 保留为创建侧别名；编辑侧不接受 `bullets` |
| 备注 | 页级字段 `notes`，地址只有 `slide_index`。不是 shape，没有 `shape_index` 或 runs。空备注省略 | 已有 `set_notes`（`slide_index` + `text`） | **本轮落地。** 精细读默认返回非空备注（`include_notes` 默认 `true`）。显式 `false` 仍可去掉 |

P2 的 PPT 只出 `layouts[]`，runs 和几何不在本轮。P3 的母版必须和写入 op 同一阶段出现。每一行要先有同名的读字段和 op，才能写进工具 description。

#### 本轮要补：原始序号和备注

| 项 | 现在的精细读 | 要补的对应 |
|---|---|---|
| 图片 / 空文本框 | 没有可见文字的 shape 被丢掉，`replace_image` / `remove_shape` 没有地址 | `type=image` 和空文本框保留原 `shape_index`。装饰形状继续省略 |
| `type` | 出的是 `type=shape`，目标曾写 `kind` | 废弃 `kind`。闭集 `text` / `image` / `shape` |
| 备注 | `include_notes` 默认 `false`，编辑闭环里等于没有这个字段 | 默认返回非空 `notes`。空的省略 |

#### 已写死，本轮不实现

- **Run 字段**跟 Word 同一闭集。真正写入时只写 `bold`、`italic`、`underline`、`font_name`、`font_size_pt`。`set_text` 继续整段替换并清掉 runs，改字和改格式分成两个 op。
- **几何**用 `x_pt` / `y_pt` / `width_pt` / `height_pt` 和 `set_shape_geometry`。`insert_textbox` 追加后必须再读。
- **填充和线条**本轮排除，字段先定死：`fill_color`、`line_color`、`line_width_pt`。
- **`align` 只表示框内文字对齐**，走 `set_paragraph_format`。形状对齐和组合排除。
- **母版**地址用版式名，不新开 master 下标。
- **标题 / 项目 / 副标题**就是三个 `role`。多 body 必须带 `shape_index`。

#### 字体与字号

字体和字号与 Word 使用同一套名字：`runs[]` 上的 `font_name`、`font_size_pt`，写回用 `set_run_format`。P2 的 PPT 只出 `layouts[]`，这两项不在本轮。

| 侧 | 字体和字号 |
|---|---|
| 阅读线 sidecar | 已经抽出。每条 run 可以带 `font_name`（`GetFontFamily`）和 `font_size_pt`（`GetFontSize`）。同一抽取器还会把**只有第一条 run** 抄到 `style.font_name` / `style.font_size_pt`。地址是 1-based `slide_index` 加上 `shape_id`（`s1-1`），编辑不能用。没有 `run_index` |
| 精细读（`office_read_presentation`） | 两个字段都没有。shape 只有 `text`、`type`，有时有 `placeholder_type` / `role` |
| 编辑 op | `set_text`、`set_title`、`set_bullets` 只写纯文本。没有字体族或字号参数 |
| 目标 | 字段名定为 `font_name` / `font_size_pt`，写入 op 定为 `set_run_format`。P2 的 PPT 只出 `layouts[]`，所以不在本轮 |

Word 已经关上、PPT 还没有的两处：

- 一个 shape 里可以有两种字体。sidecar 的 `style` 只留第一条 run，第二种字体没有地址。编辑读必须把 `font_name` 和 `font_size_pt` 放在每条 run 上，地址是 `slide_index` + `shape_index` + `run_index`，写入 op 用同样的字段名。
- `set_text` 替换整个 shape 的文字，并丢掉原有 runs。字号落地之后，改字和改 `font_name` / `font_size_pt` 必须分成两个 op，否则再读对不上刚写的值。Word 已对 `set_block_text` 写了这条；PPT 对 `set_text` 同样适用。

### 5.4 Excel（编辑读 + 编）

`sheet_index`（0-based）、`name`、`rows`、`used_range` 已经有。单元格写入已经用 A1：`set_cell`、`set_range`、`clear_range`、`set_formula`（ADR-015）。阅读线 CSV 不能回写。公式读回、`rows[r][c]` 到 A1、按 op 的工作表地址，以及样式字段名已写死，见下文。合并、图表、数据验证、条件格式没拍板，不发明字段名。

**已有 op：** `set_cell`、`set_range`、`clear_range`、`insert_rows`、`delete_rows`、`add_sheet`、`delete_sheet`、`rename_sheet`、`set_formula`、`copy_sheet`。

#### 每个目标要补的三边

| 编辑目标 | 编辑读 | 编辑 op | 对应关系 |
|---|---|---|---|
| 公式 | `include_formulas=true` 把公式字符串写进同一个 `rows` 单元格，替换显示值（ADR-031）。没有 `formula` 字段。默认读只出显示值 | `set_formula` 收 `cell` + `formula`，与 `set_cell` 的 `value` 分开 | **已写死。** 不另设 `formula` 字段。默认再读就是计算值；要看公式必须 `include_formulas=true` |
| `rows` 网格 vs A1 | `rows[r][c]` 是 used range，或 `options.range` 裁出来的那一块，不是表上的 A1。`headers` 永远是这块网格的第一行（ADR-033），裁切切掉真表头时也一样 | op 拒绝 `row` / `col`。单元格写入要 `cell` / `range`。`insert_rows` 用 1-based 的表行 `at_row`；`delete_rows` 用 1-based 的 `from_row`。两者都不是 `rows` 里的下标 | **已写死。** 原点是该次返回的 `used_range` 左上角。`headers` 不是编辑地址 |
| 工作表地址 | 每张表同时有 `sheet_index` 和 `name`。`sheet_index` 是工作簿里的 0-based 序号，不是过滤后 `sheets[]` 的下标 | 见下文按 op 分列 | **已写死。** 两个都给时 `sheet_name` 优先。新表不承诺 `sheet_index` |
| 单元格样式 | 不放进 `rows`。`include_styles=true` 时，sheet 上另给 `cell_styles[]`，每项以 A1 `cell` 带上下列 16 个字段。默认不返回 | `set_cell_style`：`cell` 或 `range`，字段名与读相同。缺省保持原样，显式 `null` 清该项。`clear_format` 一次清掉这 16 个字段 | **已写死。** 不再有一个叫「单元格样式」的字段。名字按 Word 已定的拆开 |
| 合并单元格 | 没有合并区字段 | 没有合并或取消合并的 op | **没拍板。** 没有把两边拴在一起的 A1 range 字段，也没有 op 名 |
| 列宽与行高 | `column` + `width_pt`，`sheet_row` + `height_pt`。不复活 `default_col_width`（ADR-032） | `set_column_width`、`set_row_height` | **已写死。** 不是单元格字段 |
| 图表 | 没有图表地址 | 没有 op | **没拍板。** 「工作表 + 图表序号」和锚点 range 都没选定 |
| 数据验证 | 没有 range 或规则字段 | 没有 op | **没拍板。** 不发明字段名 |
| 条件格式 | 没有 range 或规则字段 | 没有 op | **没拍板。** 不发明字段名 |

#### 已写死

这三条约定写入 `office_read_spreadsheet` / `office_edit_spreadsheet` 的 description。不新增字段，不新增 op。

**公式读回**

- `set_cell` 只写 `cell` + `value`。`set_formula` 只写 `cell` + `formula`。两边不混用。
- 不另设 `formula` 字段，也不另给 `formulas[][]`（ADR-031）。
- `include_formulas` 默认 `false`：`rows` 里是显示值。`set_formula` 之后默认再读看到计算值。这是约定，不是漏读。
- `include_formulas=true`：该格有公式时，`rows` 里改成公式字符串，保留前导 `=`，显示值被换掉；没有公式的格仍是显示值。这是读回公式的唯一方式。

**`rows[r][c]` → A1**

`r`、`c` 从 0，只是本次返回网格的下标。原点是该 sheet 这次读到的 `used_range` 左上角，不是表上的 A1。

- 解析 `used_range` 左上角为 0-based `(row0, col0)`。单格 `B3` 和区域 `B3:D10` 都取左上角。
- `rows[r][c]` 的 A1：列字母由 0-based 列号 `col0 + c` 得到（0 = A），行号是 `(row0 + r) + 1`。编辑只写这个 `cell` 或 `range`。
- 禁止把 `r` / `c` 当作 op 的 `row` / `col`（ADR-015）。
- `options.range`（ADR-034）先按工作表坐标裁剪，再把 `used_range` 改成这块范围。裁剪后 `rows[0][0]` 是 `options.range` 的左上角，换算仍用上一条。裁剪不得把 `rows[0]` 当成 A1。
- `max_rows` 只从网格顶部截断行数，不移动原点。换 A1 只用 `used_range` 的左上角，不用它的右下角去对 `rows` 的长度。
- `headers` 永远是这次返回的 `rows[0]`（ADR-033）。`options.range` 切掉真表头时也一样。它不是编辑地址。改表头用这块第一行换出来的 A1，走 `set_cell` / `set_range`。创建侧 `header_row` 不写出这份 `headers`。
- `at_row`、`from_row` 是工作表的 1-based 行号（第 1 行 = 1），不是 `rows` 的下标。`insert_rows` 在该表行之前插入。不能由 `r + 1` 得到，除非这次 `used_range` 恰好从第 1 行开始。

**按 op 的工作表地址**

`sheet_index` 是工作簿序号（`GetSheet` 的 0-based），`options.sheet_names` 滤掉其它表之后也不重编号。同一 op 上 `sheet_name` 和 `sheet_index` 都给时，用 `sheet_name`。

| op | 地址 |
|---|---|
| `set_cell`、`set_range`、`clear_range`、`clear_format`、`set_cell_style`、`set_column_width`、`set_row_height`、`insert_rows`、`delete_rows`、`set_formula` | `sheet_index` 或 `sheet_name`。两个都省略就打到活动表 |
| `delete_sheet` | 必须 `sheet_index` 或 `sheet_name`，不能省略 |
| `rename_sheet` | 必须 `sheet_name` + `new_name`。只给 `sheet_index` 则拒绝 |
| `add_sheet` | 只收新表的 `name`。不收 `sheet_index`，也不收初始 `rows`（ADR-036） |
| `copy_sheet` | 源表用 `sheet_index` 或 `sheet_name`，必填。可选 `new_name`（ADR-035）。不定义新表的 `sheet_index` |

`add_sheet` 和 `copy_sheet` 都不把新表的 `sheet_index` 交回调用方。同一次 `operations` 里，后面的 op 不得猜这个下标。下一轮再读；复制或新增时若写了名字，之后用 `sheet_name` 定位。

**样式字段**

按 Word 已定的名字拆开。「单元格样式」不再作为一个字段。这些字段不放进 `rows`：`rows` 已经写死为显示值或公式字符串。`options.include_styles` 默认 `false`，不返回样式。为 `true` 时，每个 sheet 另给 `cell_styles[]`，每项有 A1 `cell` 和下列字段。写入用 `set_cell_style`，定位仍是 `cell` 或 `range`，外加与 `set_cell` 相同的工作表地址。缺省的字段保持原样，显式 `null` 才清掉那一项。

| 字段 | 含义 |
|---|---|
| `number_format` | 数字格式代码本身，例如 `0.00`、`yyyy-mm-dd`、`0%`。不做成「货币 / 百分比」枚举。空表示常规 |
| `fill_color` | 单元格底色，`#RRGGBB`。这是填色，不是 Word 的 `highlight` |
| `border_left` | `none` / `thin` / `medium` / `thick` |
| `border_right` | 同上 |
| `border_top` | 同上 |
| `border_bottom` | 同上 |
| `border_color` | 四条边共用的 `#RRGGBB`。四边都是 `none` 时为空 |
| `bold` | 布尔 |
| `italic` | 布尔 |
| `underline` | 布尔。先不区分单下划线和双下划线 |
| `strike` | 布尔 |
| `font_name` | 字体名 |
| `font_size_pt` | 字号，单位 pt |
| `font_color` | 字色 `#RRGGBB`。不用 `color` |
| `align` | 水平对齐，闭集 `left` / `center` / `right` / `justify`，与 Word 相同 |
| `vertical_align` | 垂直对齐，闭集 `top` / `center` / `bottom`。Word 没有这一项 |

列宽和行高不是单元格字段，也不复活 ADR-032 已删除的 `default_col_width`。同样只在 `include_styles=true` 时返回：`column_widths[]` 的 `column` + `width_pt`，`row_heights[]` 的 `sheet_row` + `height_pt`。

| 字段 | 地址 | 含义 |
|---|---|---|
| `width_pt` | `column`，列字母，如 `"B"` | 该列宽度，单位 pt。op 为 `set_column_width` |
| `height_pt` | `sheet_row`，1-based 表行 | 该行高度，单位 pt。op 为 `set_row_height`。不用 `at_row`（那是插入位置），也不用已废弃的 `row` / `col` |

`clear_range` 只清值和公式。数字格式、字体、对齐、填色、边框都留下。列宽、行高、合并区继续不动。`set_cell_style` 写过的字段，再被 `clear_range` 清掉数值之后，读回来仍然在。现在的实现是对区域调用 `Clear()`，格式也会掉。样式字段落地时改为只清内容。

要清样式时另开 `clear_format`，地址同样是 `range`。它清掉前面 16 个单元格字段，不清值、不清公式、不改列宽行高、不取消合并。不在 `clear_range` 上加「清到哪一层」的开关。

字段名已写死。P2 不实现这组读字段和 op。

#### 没拍板

下面这些不是样式字段，仍然没有读字段，也没有 op 名。不发明字段名，不写进 `office_read_spreadsheet` / `office_edit_spreadsheet` 的 description。

- **合并单元格。** 没有 A1 range 把「合并区」和「合并」拴在一起，也没有合并或取消合并的 op 名。
- **图表。** 地址没选定：工作表加图表序号，或一个锚点 range。没有 op。
- **数据验证。** 没有 range，没有规则字段，没有 op。
- **条件格式。** 没有 range，没有规则字段，没有 op。

### 5.5 PDF（编辑读 + 编）

DocumentServer 精细读的 0-based `page_index` 已经和现有页操作对齐。Document AI layout、`read_mode=coarse`、阅读线的 `[Page N]` 都不能当 `office_edit_pdf` 的地址（`LAYOUT_LOCATOR_NOTE` 保留）。阅读线 media URL 不进入 `office_edit_pdf`。下面每一行仍是名字不一致，或三边只写了一边。

**已有 op：** `add_paragraph`、`set_page_text`、`add_page`、`delete_page`、`rotate_page`、`add_annotation`；表单 `office_fill_pdf_form`。

#### 每个目标要补的三边

| 编辑目标 | 编辑读 | 编辑 op | 现在缺的对应关系 |
|---|---|---|---|
| 块改写 | 精细读给出 `page_index` + `block_index`，`type` 为 `paragraph` 或 `table`，以及 `text` 或 `rows` 字符串网格 | 没有 op 收 `block_index`。`add_paragraph` 追加到页末。`set_page_text` 删掉该页全部元素，再推入没有 `block_index` 的新 `blocks` | 「更细的块改写」没有 op 名，也没有字段。`set_page_text` 之后旧的 `block_index` 不再存在 |
| 表格单元格 | 表块只有 `rows`。没有 `row` / `col` | `set_page_text` 可以推入一整张新表。不能改已有表的一个单元格 | 没有单独点名。它被折进「块改写」，没有单元格地址 |
| 对齐、加粗、字体 | 段落读只有 `text`。没有 `align`、`bold`、`font_name`、`font_size_pt` | `add_paragraph` 和 `set_page_text` 写 `align`（`left` / `center` / `right`）。`bold` 在创建侧和 `set_page_text` 的块上，不在 `add_paragraph` 上。没有字体族或字号参数 | §5.1 写 PDF 无字体，P2 的 PDF 样式不在本轮。清单没有点名 `align`、`bold`、`font_name`、`font_size_pt` |
| 图替换 | 非表元素存成 `type=paragraph`。没有 `type=image`。Document AI 用 `type=figure` 和它自己的 `block_index` | 没有 op | 「图替换」只在目标清单上。Document AI 的 figure 序号不是编辑地址。阅读线 media URL 不进入 `office_edit_pdf` |
| 书签 | 没有 bookmark id | 没有 op | 「书签」只在目标清单上 |
| 批注 | 仅 `include_annotations=true` 时返回（默认关）。每条有 `kind`（`GetClassType`）和 `text`（`GetContents`）。没有序号，也没有 `rect` | `add_annotation` 写 `page_index`、`kind`（`freetext` 或 `highlight`）、`text`、`rect`（`x`、`y`、`width`、`height`） | 不在清单里。已有批注没有地址。读的 `kind` 不是写的 `kind` |
| 页面旋转 | 页对象没有 `degrees` | `rotate_page` 写 `degrees`（`90` / `180` / `270`） | 没有点名。再读看不到刚写的值 |
| 表单字段 | 页上的 `form_fields[]`：`name`、`type`（`GetClassType`）、`value` | `office_fill_pdf_form` 按 `name` 把 `data` 写成 `value`。不收 `page_index` 或 `type` | `name` 与 data 的键一致。`type` 不是闭集。不同页上同名的两个字段没有页地址 |

`add_page` 收 `after_index`，然后脚本读最后一页的元素。新页的 `page_index` 没有定义成 `after_index + 1`。`delete_page` 会让后面每个 `page_index` 前移，改完必须再读。

P3 只收已经有读字段、并且 op 用同一名字的项。上表没有一行满足，所以在写成那样之前，不得写进工具 description。

---

## 6. 线 C：Builder

保持现状，本 PRD 不改契约：

| 工具 | 作用 | 回包 |
|---|---|---|
| `office_execute_builder` | `script` 或 `.docbuilder` `url` + 可选 `argument` | 生成文件 |
| `office_edit_word_script` | 对已有 Word 跑中间 JS（MCP 注 Open/Save/Close） | 改后的 Word 文件 |
| `office_call_api` | Conversion / Command，不是 Builder | API 原样 |

开发者可用 Builder 自己抽 JSON，**官方 read 不会认**。自定义解析 = 调用方自己解 `content_base64`。

---

## 7. 现状对照（实施前基线）

| 能力 | 现在 | 本 PRD 目标 |
|---|---|---|
| `office_read_document` | `elements[]`（Word/PPT 含 runs；PDF=DAI；xlsx=csv 元素） | `format=markdown` + JSON/MD/plain/zip；**无 `elements[]`**；声明只读 |
| `office_read_document` 全类型 | 富结构仅 doc/docx/odt/rtf、ppt/pptx/odp、pdf；其余 Conversion | 仍接这些输入，但一律投影 MD/CSV |
| canonical fine | 有 locator，无/少样式 | locator + 样式同对象 |
| 图片 | Word 跳过 | 抽 media + MD 引用（阅读线） |
| Excel 阅读 | csv/`rows` JSON | 多 sheet 多 CSV + `[Page N]` |
| 扫描 PDF | DAI 当 structured 元素 | DAI → MD；有 `pageStart` 则 `[Page N]` |
| 编辑 op | §5 已有列 | 已有保留；待补充另开规格 |
| Builder | 已开放 | 保持 |

---

## 8. 分阶段

### P0 — 收束语义（对外可感知、内部可落地）

1. `office_read_document` description + `_note`：只读，禁止 edit。
2. 主出站改为 MD（默认 `format=markdown` + `accept=application/json`）。**不保留 `elements[]`。** 发 changelog，本仓库不改 middleware。
3. Word/PPT/数字 PDF：`[Page N]` + 标题/列表/表。
4. Excel：一 sheet 一页 CSV。
5. 扫描 PDF：DAI → MD；有 `pageStart` 写页标，无可靠页界才省略。
6. 大文档：同步硬上限（页数/字节）；超限仍用本工具 + `page_range` 续读，**不**改走 `office_parse_document`。
7. canonical / Builder 行为不动。
8. 单测：MD 页标、空段、Excel 多 sheet、DAI 无页标；E2E 抽一份 docx/pptx/xlsx/pdf。

### P1 — 阅读线媒体

抽出 media、命名、`![ ](media/…)`；`media_delivery=fetch_token|caller_bucket`；`accept=application/zip`。

### P2 — 编辑线补格式

把 Word sidecar 已有的 runs **接到 canonical fine**（同一 `block_index`）。Word 本轮见 §5.2：字体、字号、对齐、单元格文字，以及加粗/斜体/下划线、真列表、表格行列、页眉页脚页码（只出 default）、图片、超链接、移动块。图表、文本框、分栏、批注、脚注，以及合并格、底纹、边框，不在本轮。PPT 本轮只出 `layouts[]`（§5.3），不把 sidecar runs / 几何接到 `shape_index`；另做两件：精细读保留图片和空文本框的原始 `shape_index`（`type` 闭集 `text` / `image` / `shape`），以及默认返回非空 `notes`。Excel 样式字段名已写死（§5.4），实现不在本轮。PDF 样式不在本轮（§5.5）。

### P3 — 编辑 op 补全

Word first/even 页眉页脚，以及 §5 里已经写明读字段和同名 op 的项。PPT 母版地址已写死为 `layout_name` + `shape_index`，P3 才读母版形状，且必须和写入 op 同一阶段出现。§5.3 已写死但未实现的项（runs / `set_run_format`、几何、框内 `align`、填充线条）在落地前不得写进 TOOL_DEF。形状相对幻灯片的对齐和组合已排除。§5.4 已写死的公式读回、`rows[r][c]` → A1、按 op 的工作表地址写入工具 description。样式字段名已写死，但 P2 不实现，未实现前不写进工具 description。合并、图表、数据验证、条件格式仍没拍板，不得写进工具 description。§5.5 没有一行同时有读字段和同名 op，不得写进工具 description。

---

## 9. 验收

### 阅读线

- 模型只靠 `office_read_document` 能读完一篇带标题/列表/表的文档。
- 出站 MD 无 `block_index` / `shape_id`。
- `_note` 含「must not edit」。
- 多图文档：MD 引用与 `media[].url` 能拉下同一文件。
- 三 sheet xlsx：三个 `[Page N]` 三段 CSV。
- 扫描 PDF：有正文 MD；有 `pageStart` 则有 `[Page N]`，无页界时没有假页标。
- 超同步上限：`err` 提示用 `page_range` 续读，响应里没有 parse 工具名。
- `office_edit_word(block_index=0)` 若误用阅读线结果，文档与指南均说明这是误用。

### 编辑线

- fine structured 的 locator 仍能打中现有 edit op（回归）。
- P2 后：改 run 样式不必先靠 `office_read_document`。
- `office_read_pdf` + DAI 的 `_locator_note` 仍禁止 edit。

### Builder

- `office_execute_builder` 仍只回文件。
- 自定义 JSON 不会被 read 工具当 `units`。

---

## 10. 已决问题

| # | 议题 | 决定 |
|---|---|---|
| 1 | 存量 `elements[]` | **P0 直接切 MD**，不并行双字段。本机 **不改 middleware**。只出 [CHANGELOG](./CHANGELOG_OFFICE_READ_DOCUMENT_MD.md)，由其它团队按文档改。 |
| 2 | DAI 页标 | **有稳定 `pageStart` 就写 `[Page N]`**；扫描件判定失败、无可靠页界再省略。页标不作 edit 地址。 |
| 3 | media 投递 | **两种都支持**。同网：`media_delivery=fetch_token`（默认）。外部：`caller_bucket` + `media_output_path`。 |
| 4 | 大文档 | **同步上限，线不拆**。超限仍 `office_read_document` + `page_range` 续读，不引导 parse。 |
| 5 | 母版 / first·even 页眉 | **是。** P2 读只出 default 页眉页脚 + `layouts[]`；first/even 与母版编辑放 P3。PPT 母版地址是 `layout_name` + `shape_index`，不引入 `master_index`。 |
| 6 | 命名 | 阅读线只认 `format=markdown\|plain\|outline` 与 `accept=application/json\|text/markdown\|text/plain\|application/zip`。旧 `structured`/`text` **不留别名**，调用方自行改。canonical 工具仍用 `structured`/`text`/`outline`。 |
| 7 | Excel 编辑读三条约定 | **写死。** 不另设 `formula` 字段；公式只经 `include_formulas=true` 读回，默认再读是计算值。`rows[r][c]` 的原点是该次 `used_range` 左上角。工作表地址按 op 分列，两个都给时 `sheet_name` 优先；`add_sheet` / `copy_sheet` 不承诺新表 `sheet_index`。合并、图表、数据验证、条件格式**没拍板**，不发明字段名。 |
| 8 | Excel 样式字段 | **写死。** 不再使用「单元格样式」这一个名字。16 个单元格字段放在 `cell_styles[]`（`include_styles` 默认关），不放进 `rows`。写入用 `set_cell_style`；`clear_range` 只清值和公式；清样式另开 `clear_format`。列宽 `width_pt`、行高 `height_pt` 单独寻址。P2 不实现。 |
| 9 | PPT 编辑字段 | **写死。** 编辑地址继续用 `slide_index` + `shape_index`。废弃 `kind`，`type` 闭集 `text` / `image` / `shape`。run 闭集与 Word 相同；几何用 `x_pt` / `y_pt` / `width_pt` / `height_pt`；`align` 只表示框内文字对齐。填充线条字段先定死但本轮排除。P2 只出 `layouts[]`，另保留图片/空文本框序号，并默认返回非空 `notes`。 |

---

## 11. 文档关系

| 文档 | 关系 |
|---|---|
| 本文 | **读/编/Builder 三条线的产品真源（目标态）** |
| [CHANGELOG_READ_EDIT_THREAD.md](./CHANGELOG_READ_EDIT_THREAD.md) | **给开发者的实际变更**（阅读线影响 + 各编辑线对象/地址/op） |
| [CHANGELOG_OFFICE_READ_DOCUMENT_MD.md](./CHANGELOG_OFFICE_READ_DOCUMENT_MD.md) | **给 middleware 的阅读线出站说明**（本仓库不改 middleware） |
| [implementation_design.md](./implementation_design.md) | M0–M7 as-built How；本 PRD 落地后回写差异 |
| [ADR.md](./ADR.md) | 已采纳决策仍有效；阅读线出站变更需新 ADR |
| [SCHOLAR_PARSE_CONTRACT.md](./SCHOLAR_PARSE_CONTRACT.md) | 异步 parse 不改、不退役；MD 规则应对齐 |
| 各 `OFFICE_MCP_*_LLM_GUIDE.md` | P0 后改：document=阅读，category read=编辑 |
