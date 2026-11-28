# 2026-11-22 HarmonyOS 补丁公开镜像补证

本轮由 AI 助手对固定 12 条抽查清单中此前无法读取的 4 条 HarmonyOS 补丁进行只读补证。原 Gitee 地址本次仍返回登录 HTML；公开的 `openharmony/kernel_linux_5.10` GitHub 仓库可提供 4 条实质补丁。3 条与原链接的完整 40 位 SHA 相同；另 1 条原链接仅含 12 位 SHA，已在同名仓库解析为完整提交，保留短前缀身份限制。

截至本次，证据材料累计可读 **12/12（旧审计 8 条 + 本轮镜像补证 4 条）**。这不是同一天重抓全部 12 条，也不表示学生完成标签审核。两名成员的独立人工核验仍为 **0/12**，原 A/B 表没有填写或改动；不修改作者数据、旧审计文件或核心结果。

## 身份与来源核验

脚本对每条样本依次核验原链接、GitHub commit API、完整 SHA 的 `.patch`，并下载该提交及其父提交的变更文件。所有下载仅是读取，未应用或执行补丁。

每条记录同时检查：API 返回的完整 SHA 与原链接完整 SHA 或短前缀相符；补丁 `From` SHA 与 API 相同；父提交为有效的完整 SHA；变更文件清单和增删行数与 API 相同；当前文件按 Git blob 对象格式计算 SHA-1，与 API 文件 SHA 和补丁新 blob 前缀一致；父版本文件的 Git blob SHA-1 与补丁旧 blob 前缀一致。四条均通过这些检查。GitHub 仓库 API 同时记录了仓库名与组织名 `openharmony`。未以相同 CVE 的 Linux 上游提交代替原 OpenHarmony fork 提交。

| 样本 | 原链接身份 | 完整镜像提交与父提交 | 可见文件 / hunk | 补丁增行 + 删行 |
|---|---|---|---|---:|
| CVE-2024-39475 | 完整 SHA 相符 | `352581ba396aca7d9ac584a5faf7a1e917195130`；父 `076cf87c1aaa46da90a2789c03de07270c6299e9` | `drivers/video/fbdev/savage/savagefb_driver.c` / 1 | 4 + 1 = 5 |
| CVE-2024-46740 | 原 12 位前缀解析 | `60351db082d82f1f673b5e2ab5e9366a3bb98c1b`；父 `e6c68869d6fe63f33d2762dce5b5b953a683cad1` | `drivers/android/binder.c` / 1 | 1 + 0 = 1 |
| CVE-2023-52756 | 完整 SHA 相符 | `57898356796547b947e4d3fe59e13ed11e232773`；父 `6dda35970af7f1bf09fa2a7398ac1f9a7ec9392e` | `include/linux/pwm.h` / 1 | 2 + 2 = 4 |
| CVE-2024-43882 | 完整 SHA 相符 | `20623a6b55297a37ba5b348450b7b369508ae0c3`；父 `78aa7320da02c0a6a9f7ffeb5bbf8c8de3a983fa` | `fs/exec.c` / 2 | 7 + 1 = 8 |

其中 `60351db082d8` 由 GitHub commit API 成功解析到上述单一提交，提交说明也包含对应 CVE。但 Gitee 当前未提供完整 SHA，不能把它写成“已从原站独立获得完整 SHA”或声称跨所有仓库证明前缀唯一。

## AI 辅助阅读结果

以下为助手阅读可见补丁后的解释，供成员实际核验时参考；不等于两人的独立标签结论。

- **CVE-2024-39475**：`savagefb_probe` 增加对 `savagefb_check_var` 返回错误的处理，失败时转向已有退出路径。可见差异在一个函数体中，修改一文件、4 加 1 删，与清单中的 1 函数、1 文件、5 行在常见计数口径下相容。[原 fork 镜像提交](https://github.com/openharmony/kernel_linux_5.10/commit/352581ba396aca7d9ac584a5faf7a1e917195130)
- **CVE-2024-46740**：`binder_transaction` 的已有条件中增加一个数据边界检查。API、独立补丁和父/当前文件对应同一变更：一文件、一个 hunk、**1 加 0 删**；作者清单 `line_changes=2` 与本补丁按“增行 + 删行”统计的 1 行不一致。原链接为短 SHA，且论文修复规模计数口径仍有缺口，因此登记为待核实差异，不直接改成 1，也不据此推断其它行计数正确或错误。[短前缀解析所得 fork 提交](https://github.com/openharmony/kernel_linux_5.10/commit/60351db082d82f1f673b5e2ab5e9366a3bb98c1b)
- **CVE-2023-52756**：只修改 `include/linux/pwm.h` 中两个枚举常量的值；这些是函数体外的枚举定义，没有可见函数体改动，也不是打包文件中包裹的嵌套补丁。因此本条可见证据支持 `involved_functions=0`，且一文件、2 加 2 删与作者计数相容。此前保存的官方 CVE 记录状态为 `REJECTED`；撤销 CVE 与补丁是否存在是两个独立事实，不能据此删除数据或推断没有缺陷。[原 fork 镜像提交](https://github.com/openharmony/kernel_linux_5.10/commit/57898356796547b947e4d3fe59e13ed11e232773)；[此前 CVE 来源记录](../results/review_evidence/cve_sources.json)
- **CVE-2024-43882**：`bprm_fill_uid` 在锁内读取相关元数据时重新检查执行权限，并在检查失败后返回。两个 hunk 均属于同一个可见函数；一文件、7 加 1 删，与作者 1 函数、1 文件、8 行在常见计数口径下相容。[原 fork 镜像提交](https://github.com/openharmony/kernel_linux_5.10/commit/20623a6b55297a37ba5b348450b7b369508ae0c3)

本轮没有重新裁定系统层次、受影响功能或触发场景，也没有运行操作系统、触发漏洞或检验修复有效性。补丁可读性、提交身份、计数相容性与标签正确性是不同层面的证据。

## 产物与复跑

- [来源 JSON](../results/review_evidence_followup/sources.json)：4 条样本的提交、父提交、树 SHA、文件与 blob 核验、统计、逐 URL 获取时间及结果；仓库来源 API 记录。
- [逐请求 CSV](../results/review_evidence_followup/sources.csv)：21 次请求的 URL、UTC、最终 URL、HTTP 状态、内容类型、原始响应 SHA-256 和字节数。
- [独立核验用补充来源表](../review_materials/blind/supplemental_sources_2026-11-22.csv)：仅系统、ID、原链接、镜像链接、完整提交 SHA、身份核验说明，不含作者标签或本轮分类判断。
- [只读复跑脚本](../scripts/check_review_mirrors.py) 与 [离线测试](../tests/test_review_mirrors.py)。原始第三方响应、文件和补丁仅缓存在忽略的 `work/review_mirrors/`，不随成果上传。

```powershell
py -3.11 scripts/check_review_mirrors.py
py -3.11 -m unittest discover -s tests -p test_review_mirrors.py -v
```

本轮实际执行了上述两个命令：脚本返回 4 条可核验的公开补丁（3 条完整原 SHA，1 条原前缀解析）；10 项离线测试全部通过。测试覆盖错误 SHA、错误补丁 SHA、登录 HTML、文件/行统计不符、缺失父提交或 blob、父版本内容不符和短 SHA 身份披露。它们检验来源完整性判断，不验证作者原始标签。核心完整测试由主任务另行统一执行。

网络复跑会重新获取来源，并更新本目录结果；若需要保留此次快照，请使用 `--output-dir` 和 `--cache-dir` 指定新目录。脚本不提供离线重建网络证据模式；离线测试仅使用合成固定输入。未来来源不可访问时输出未确认，不会用旧缓存冒充本次成功获取。
