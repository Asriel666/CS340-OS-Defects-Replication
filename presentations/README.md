# 答辩材料

报告人：**1230037310 钟峻瀚**。内容基于团队仓库的结果，Codex 协助计算、证据整理与材料编写。共同署名和实际贡献仍由成员确认。

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
