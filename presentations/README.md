# 答辩材料

## 交付版本（2026-11-27 最终版）

- **`OS_Defects_G15_Final_2026-11-27.pptx`**：14 页、16:9，Group 15 最终答辩稿。第 1 页分工：Guo Haoxuan 负责 PPT Slides 与 P7–P10（批判性分析、局限、结论与影响）；Zhong Yiheng 负责 PPT Slides 与 P5–P6（RQ2/RQ3）；Zhong Junhan 负责 P3–P4（方法与 RQ1）；Gu Xuanze 负责 P1–P2（引言）。
- [final_validation_2026-11-28.md](final_validation_2026-11-28.md) / [.json](final_validation_2026-11-28.json)：由 1230036051 GUO HAOXUAN 对最终版 17 项数值断言逐项核对仓库证据，17/17 通过；含讲解时需主动说明的三点边界。这是数值一致性检查，不是人工审核或演练。
- 最终版纳入 11-22 进度：成对排除共同零类别后 A–H 触发场景 0.3769（≈0.38）、12/12 补丁证据可读、抽样波动结果。旧版保留作历史记录。

## 历史版本（2026-11-14）

报告人：**1230037310 钟峻瀚**。内容基于团队仓库的结果，Codex 协助计算、证据整理与材料编写。共同署名和实际贡献仍由成员确认。

**2026-11-22 进度补充：**下列 PPT、内部备注和原讲稿保持 11 月 14 日的历史版本。其“8 条可读、4 条登录页”和“109 项测试”反映当时状态；现在累计 12/12 样本有可读证据，134 项测试通过，人工审核仍各 0/12。讲解时补充[最新周报](../docs/weekly/2026-11-22.md)和[个人报告](../docs/contributions/1230037310_钟峻瀚_2026-11-22.md)，不能把新进度误称为原 PPT 已包含的内容。

- `defense_2026-11-14_v2.pptx`：10 页、16:9 中文可编辑答辩稿，原生表格和文字均可在 PowerPoint 中修改。
- [speaker_notes.md](speaker_notes.md)：逐页讲解稿与来源链接，也写入 PPT 的演讲者备注。
- [validation_summary.json](validation_summary.json)：最终文件摘要、页数、原生表格数、包与布局检查结果及其适用边界。

保留核心固定类别结果 **552/552 表格值、8/9 相关系数吻合**。按系统对删除共同零类别后，Android–HarmonyOS 触发场景得到约 0.38，是**与论文相容的候选解释**，作者方法仍待确认。人工审核未完成，答辩时不要将自动化证据检查称为两位同学已独立重新标注。

## 重新生成

统计分析和 PPT 构建是独立流程。PPT 源码读取已有 `results/full/`，使用 `@oai/artifact-tool` JavaScript ES module，未使用 `python-pptx`。在当前 Codex Windows 环境：

```powershell
& 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' scripts/build_defense_slides.mjs
```

可用 `CODEX_PRESENTATION_RUNTIME` 指向包含 `node/node_modules` 和 `python/python.exe` 的 Codex 依赖目录，`CODEX_PRESENTATION_SKILL` 指向当前 Presentations 技能目录。绘制中文使用已安装的 **Microsoft YaHei** 字体。此构建环境独立于统计分析所需的全局 Python 3.11，不需要为统计代码安装演示文稿运行时。

草稿、逐页渲染与验证记录位于忽略目录 `work/slides/`。构建脚本先通过包完整性、原生表格、页面尺寸和字体检查，再导出最终文件。已有文件不会覆盖，重复构建会生成新文件名。交付版本经过逐页渲染检查，未在桌面 PowerPoint 中实际打开测试。

第 6、9 页引用本次新增的类别集合分析和证据整理结果。以后修改这些结果时，应同步改动构建脚本中的解释与讲解稿，重新生成并检查全部页面。
