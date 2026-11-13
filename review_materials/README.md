# 12 条抽查的 A/B 独立审核材料

**2026-11-14 更新：优先使用 [blind/](blind/README.md) 中的无答案审核表。** 原版 `ab_review_sheet_A.csv` / `B.csv` 在同一文件末尾含作者标签，提前打开即可看到答案，不利于独立判断；保留它们作为历史材料，新的作者对照标签放到 [coordinator/](coordinator/README.md)，由协调人延后提供。新流程增加准备与记录校验命令，人工判断仍未填写。

生成日期：2026-11-13。对应 [docs/weekly/2026-11-12.md](../docs/weekly/2026-11-12.md) 排定的优先级 1 工作。

## 文件清单

| 文件 | 用途 |
|---|---|
| `evidence_checklist.csv` | 12 条抽查缺陷的证据清单：作者发布的分类标签、修复规模参考值、补丁链接与域名、HTTP 可访问性。供审核者打开链接前了解背景。 |
| `ab_review_sheet_A.csv` | 审核者 A 的空白独立判断表 |
| `ab_review_sheet_B.csv` | 审核者 B 的空白独立判断表 |

## 抽取规则与可访问性

- 抽样来自 `data/review/rq123_label_review.csv`：每个系统按缺陷 ID 排序、以种子 340 抽取 4 条，共 12 条（Android / Linux / HarmonyOS 各 4）。
- 2026-11-13 对全部 12 条补丁链接执行过一次只读 HTTP 检查：**12/12 返回 200**，域名分布为 `android.googlesource.com`（4）、`bugs.launchpad.net`（4）、`gitee.com`（4）。该结果只说明链接当时可达，不保证补丁内容与标签一致；`patch_http_status` 列即为本次检查记录。

## 填写规则

1. **先独立判断，后对照**：每份审核表中 `your_*` 三列（系统层次、受影响功能、触发场景）请只依据补丁内容独立填写；`paper_*_fill_after` 三列是作者发布的标签，**填完 `your_*` 之后**再对照并填写 `agrees_with_paper`（yes / no / partial）。提前看答案会让抽查失去独立性。
2. **只依据补丁内容**：判断只能来自补丁 diff 与缺陷描述本身。打不开或看不懂的材料，对应格填 `unconfirmed`，不补造理由。
3. **留证据**：`your_evidence_link` 填写支撑判断的具体文件/行/讨论链接；`your_notes` 记录不确定处。
4. **不许互看**：A 与 B 的表各自独立填写，完成前不交流分类结论；分歧留待两人同时在场时讨论，讨论结论写回 `data/review/rq123_label_review.csv` 的 `adjudication` 列。

## 分类定义（仅供独立判断时参考，不含答案）

三个维度的合法类别如下；一条缺陷在单标签维度恰好属于一类。

**OS Layer（系统层次，6 类）**：Kernel（内核）；System Library（系统库）；Runtime / Virtual Machine（运行时或虚拟机）；Framework（框架层）；System Service（系统服务）；Application（应用层）。

**Affected Function（受影响功能，8 类）**：Memory and Resource Management（内存与资源管理）；Process and Task Scheduling（进程与任务调度）；Storage Management（存储管理）；Device Management and Drivers（设备管理与驱动）；Network and Communication（网络与通信）；Compatibility and Adaptation（兼容与适配）；Security and Permission Control（安全与权限控制）；Graphics and Rendering（图形与渲染）。

**Trigger Scenario（触发场景，7 类）**：Permission / Identity Dependency（权限或身份依赖）；Regular Operation（常规操作）；Boundary Condition（边界条件）；Concurrency / Multi-thread（并发或多线程）；State Dependency（状态依赖）；Environment Dependency（环境依赖）；Multi-Language / Localization（多语言或本地化）。

## 边界声明

本目录由自动化工具整理生成：它搬运的是**作者已发布的标签**（作为对照材料）、公开的补丁链接与本次 HTTP 可访问性检查结果，**不包含任何 AI 预填的独立判断**——`your_*` 各列全部留空，分类结论必须由两位人类审核者独立产生。自动整理不等于人工复核已完成；A、B 两表填写完毕并经讨论仲裁后，结果回写 `data/review/rq123_label_review.csv`（该文件在本地生成、默认不提交 Git），才算完成 12 条抽查。
