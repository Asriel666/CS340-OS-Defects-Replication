# 方法核查附录：修复规模与 Overall 相似度

核查日期：2026-11-06。本文记录论文原图、公开数据与本项目计算之间的可核验差异；Figures 2/3 和 Figure 4(d) 尚未完成精确复现，不计入已完成的核心数值对比。核查由自动化工具辅助完成，不代表两名学生已独立阅读补丁或完成人工重新标注。

## Figures 2/3：先确定统计口径

已直接查看 [Figure 2 原图](https://arxiv.org/html/2608.20643v1/photo/group_changes.png) 与 [Figure 3 原图](https://arxiv.org/html/2608.20643v1/photo/group_funcs.png)。图中标签分别为：

| 图 | 指标 | 分箱标签 |
|---|---|---|
| Figure 2 | 修改行数 | `0–10`、`10–30`、`30–50`、`50–100`、`100–500` |
| Figure 3 | 涉及函数数、修改文件数 | `0–3`、`3–5`、`5–10`、`10–50` |

标签没有明确说明边界值属于哪一箱。例如 `10` 可能归第一箱或第二箱；不能只凭图中文字决定开闭区间。正文把 Figure 3 的集中区间描述为 1–3，但图的第一箱从 0 开始，零值处理因此需要额外确认。[论文 IV-A.5](https://arxiv.org/html/2608.20643v1#S4.SS1.SSS5)

本地固定版本数据核查结果如下，原始值均保留：

| 核查项 | 本次观察 | 对复现的影响 |
|---|---|---|
| `involved_functions = 0` | 共 177 条：Android 18、Linux 145、HarmonyOS 14 | 未确认其表示真实零函数修改还是未记录；不得擅自删除或改为 1。 |
| 带 `+` 的函数数 | HarmonyOS 共 7 条：`10+` 3 条、`20+` 2 条、`30+` 2 条 | 只知下界，不能把 10+ 当成精确的 10；跨箱归属和是否超过图示上限均未确认。 |
| 行数加和不一致 | Linux `2044216`：删除 331、增加 28、原始总修改 349；前两项相加为 359 | 尚未逐项审阅补丁；不自动替换 349。此例的两个候选值虽同处 100–500，仍影响数据真实性。 |
| 数值范围 | 原始修改行数 1–498；精确函数数 0–40；修改文件数 1–32 | 精确值没有超出图示范围；带 `+` 的记录仍无已知上界。 |

上述记录来自项目固定的[作者数据提交](https://github.com/zuohongyao/zuohongyao.github.io/blob/832d536f5d381d428a887e59ceeacc90a40e3b7e/index.html)，可由运行生成的 `data/processed/raw_records.json` 和 `data/processed/validation.json` 核查。保留原值、警告与删失标记使数据处理可追溯；分类统计不依赖这些修复规模字段。

后续验证应先取得作者分箱脚本或明确的边界、零值及下界处理规则；再针对零函数记录与 7 条下界记录查阅公开补丁并保存证据。若暂时拿不到规则，可以分别报告不同边界约定的敏感性分析，但必须标注为本项目新增分析，不能选择最接近论文的口径冒充原方法。

## Figure 4(c)：保留发现的系数差异

[Figure 4(c) 原图](https://arxiv.org/html/2608.20643v1/heatmap-c.png)中 Android–HarmonyOS 的触发场景相关系数为 **0.38**。本次直接从原始标签计数，按以下统一类别顺序对齐：

`Boundary Condition, Concurrency/Multi-thread, Environment Dependency, Multi-Language/Localization, Permission/Identity Dependency, Regular Operation, State Dependency`

| 系统 | 各类别缺陷数量 |
|---|---|
| Android | `[185, 36, 5, 0, 156, 44, 74]` |
| HarmonyOS | `[263, 120, 14, 0, 14, 33, 56]` |
| Linux | `[95, 15, 310, 1, 8, 45, 26]` |

对各向量取升序平均秩，再计算秩的 Pearson 相关，即标准 Spearman：Android–HarmonyOS 为 **0.6126374746329801**，Android–Linux 为 **0.21428571428571427**，HarmonyOS–Linux 为 **0.41443123283995714**。换用数量除以 500 得到的比例不改变秩。HarmonyOS 的两个 14 必须使用并列平均秩，不能任意打破并列。

因此 Android–HarmonyOS 的差异不是两位小数舍入造成的。原因尚未确定：需作者提供 Figure 4(c) 的实际输入及计算代码，才能区分图表誊录、输入版本或算法口径问题。本项目保留原图值与重算值，不修改标签或算法以追求吻合。

## Figure 4(d)：输入未定义，图文存在矛盾

已核查 [Figure 4(d) 原图](https://arxiv.org/html/2608.20643v1/heatmap-d.png)的行列标签：

| 系统对 | 原图值 |
|---|---:|
| Android–HarmonyOS | -0.11 |
| Android–Linux | 0.05 |
| HarmonyOS–Linux | -0.04 |

[论文 IV-C 的 Overall 段落](https://arxiv.org/html/2608.20643v1#S4.SS3)把 -0.11 归于 Linux–Android，与图中位置不同。此外，当前论文描述没有明确 Overall 的输入向量、类别拼接方式及权重，无法据此唯一还原计算。

本项目将 Overall 标为**未确认**，不把三个维度自行拼接后得到的值当作论文复现。后续需作者确认输入定义和系统对标注；确认后再增加独立基准、计算与测试。现有 RQ3 核心比较限定为 Figure 4(a–c) 的 9 个独立系数。
