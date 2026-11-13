# 12 条抽查材料的实质证据审计（2026-11-14）

本轮提交记录：**1230037310 钟峻瀚**。本页是 Codex 辅助完成的下载、正文检查及证据整理，**不是两位成员独立完成的人工重标注**。A/B 标签表未填写，作者数据及主实验输入未改动。

## 核心发现

对固定种子 340 选出的 12 条记录重新 GET 正文后，**8 条取得可读 unified diff，4 条未取得补丁正文**。4 条未确认记录均来自 Gitee：请求最后跳转到登录页，最终 HTTP 状态仍为 200。因而此前清单的 HTTP 200 只能证明服务器有响应，不能证明证据可以阅读。当前判断应以本次正文审计结果为准。

这次还发现两个需要人工核查的计数问题：Linux 2044546 的数据写作 0 个涉及函数，但补丁内确有函数体代码修改；Android A-323850943 写作 1 个涉及函数，而两个文件都显示函数体代码变更。两者均作为**待澄清的函数计数口径**保留，不据此修改作者标签或主统计结果。

此外，CVE 官方记录把抽中样本 **CVE-2023-52756 标为 REJECTED**，撤回时间为 **2024-06-08T11:37:10.679Z**。公开理由仅说明编号已被 CNA 拒绝或撤回，没有说明具体原因。这个发现提示数据来源状态也需要审核；它不等于补丁不存在、代码没有缺陷，或该条数据应自动删除。[CVE 官方记录 JSON](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2023/52xxx/CVE-2023-52756.json)

## 方法和可复跑产物

运行：

```powershell
py -3.11 scripts/audit_review_evidence.py
py -3.11 -m unittest discover -s tests -p test_review_evidence.py -v
```

脚本使用标准库，读取 [原始清单](../review_materials/evidence_checklist.csv)。Android 的 Gitiles 链接增加 `format=TEXT` 获取同一提交范围的 base64 diff；Launchpad 和 Gitee 使用清单原 URL，记录最后的重定向地址。不登录、不执行补丁、不修改远端内容。

公开输出：

- [audit.csv](../results/review_evidence/audit.csv) 与 [audit.json](../results/review_evidence/audit.json)：每条记录的 UTC 时间、原始/请求/最终 URL、HTTP 状态、Content-Type、响应及解码后正文的字节数和 SHA-256、内容类型、外层文件和 hunk、嵌套补丁文件和 hunk。
- [interpretations.json](../results/review_evidence/interpretations.json)：对实际取得的 8 份补丁阅读后的简短解释，每项绑定所读正文 SHA-256。只有下载正文哈希仍相同，脚本才把解释合入新审计输出；文件变化不会沿用旧结论。
- [cve_sources.json](../results/review_evidence/cve_sources.json)：4 条 CVE 的官方 CNA 元数据、记录状态、简短标题、参考链接和取回哈希。只用于背景核查，**不能替代无法读取的 OpenHarmony 补丁**。

原始响应、解码补丁和 CVE JSON 仅缓存在被 `.gitignore` 忽略的 `work/review_evidence/`，不上传第三方补丁正文。这里的审计是对访问时点的记录；登录页的动态内容和上游访问状态可能变化，重复运行不要求 HTTP 正文哈希稳定。论文数据的固定输入、三次计算稳定性与本审计是两件事。

自动检测保守地要求文件头和 unified hunk 同时出现；它不是通用 patch 验证器。重命名专用补丁、二进制补丁或其他未支持格式会落入未确认，不能直接解释为无效补丁。**hunk 数不是函数数**，包装层文件数也不是源码文件数。

## 逐条检查

表中“外层文件/hunk”和“内层文件/hunk”表示下载正文的结构计数；未确认记录的“—”表示没有可读补丁，而不是确认为 0。

| 系统 / ID | 状态 | 外层文件 / hunk | 内层文件 / hunk | 可见证据及界限 |
|---|---|---:|---:|---|
| Android A-297517712 | 可读 diff | 1 / 2 | 0 / 0 | `PackageManagerService.java` 的 MIME group 更新路径收集用户 UID 并发送 package changed 广播；两个方法上下文可读，具体分类仍待独立判断。 |
| Android A-333681693 | 可读 diff | 1 / 2 | 0 / 0 | `UninstallerActivity.java` 调整用户与父用户身份校验，另有 import 整理；两个 hunk 不能直接计作两个函数。 |
| Android A-260230151 | 可读 diff | 1 / 1 | 0 / 0 | `bta_av_aact.cc` 改变蓝牙地址取值来源；局部片段不足以独立确认完整触发场景。 |
| Android A-323850943 | 可读 diff | 2 / 2 | 0 / 0 | `eatt.h` 方法增加 MTU 下界，`gatt_sr.cc` 函数体增加零 MTU 保护。源数据函数数为 1，需核对计数定义。 |
| Linux 2063344 | 可读 diff | 4 / 4 | 1 / 1 | Debian 包装中含 `smi_drv.h` 的条件宏补丁；见下节。 |
| Linux 2076398 | 可读 diff | 3 / 3 | 1 / 3 | 包装中含 `pcap-linux.c` 的 VLAN offset helper 和调用路径调整。 |
| Linux 2044546 | 可读 diff | 3 / 3 | 2 / 2 | 包装中含 `Modules/options.c` 函数体修改及 `setup.py` Python 版本声明；见下节。 |
| Linux 2072772 | 可读 diff | 2 / 2 | 1 / 9 | 内层 `cc-applications-panel.c` 关闭 Malcontent 条件块，包含 include、结构成员与多个函数上下文。 |
| HarmonyOS CVE-2024-39475 | 未确认 | — | — | 原 patch 跳转登录页；CNA 标题涉及 savage framebuffer 错误返回处理，不能证明该 OpenHarmony 提交的内容。 |
| HarmonyOS CVE-2024-46740 | 未确认 | — | — | 原 patch 跳转登录页；CNA 标题涉及 Binder 越界覆盖导致的对象生命周期问题，不能确认该 fork 补丁的函数数。 |
| HarmonyOS CVE-2023-52756 | 未确认 | — | — | 原 patch 跳转登录页，CNA 记录已撤回；源数据函数数 0 仍未确认。 |
| HarmonyOS CVE-2024-43882 | 未确认 | — | — | 原 patch 跳转登录页；CNA 标题涉及执行权限检查与 set-id 使用之间的竞态，不代替 patch 核验。 |

上述逐条 patch URL、最终下载地址与哈希均可在 `audit.csv` 按 ID 定位；不把本表的简短解释当作 A/B 标签答案。

## 对三个“涉及函数数 = 0”样本的深入检查

**Linux 2063344：0 有局部证据支持。** [原始 debdiff](https://bugs.launchpad.net/ubuntu/+source/smifb2/+bug/2063344/+attachment/5770062/+files/smifb2_2.2.6.3.gbbd2e82-1ubuntu1.debdiff) 外层改变 changelog、control、patch 和 series，共 4 个包装文件。真正内嵌的源码补丁仅在 `smifb2/smi_drv.h` 增加 Linux 6.8 的版本条件与 `I2C_CLASS_DDC` 宏，共 4 行，没有可见函数体修改。因此本例可以解释作者的 0，但不能把这项观察推广到全部 177 个零值。外层 4 文件与源数据 1 文件的差异同时说明了包装层与源码层口径的重要性。

**Linux 2044546：0 不能解释为没有函数代码改变。** [原始 diff](https://bugs.launchpad.net/ubuntu/+source/python-ldap/+bug/2044546/+attachment/5723066/+files/python-ldap_python3.12-compat.diff) 外层是 3 个 Debian 文件，内嵌补丁同时修改 `Modules/options.c` 和 `setup.py`。前者在有返回值及分支上下文的代码块中改变错误格式化的格式符和参数。补丁自己指向的[固定上游提交源码](https://raw.githubusercontent.com/python-ldap/python-ldap/2229d83646895ce041a5582400fa77e82d40c2c7/Modules/options.c)可把该代码块定位于 `LDAP_set_option`。这说明至少存在函数体修改；作者的“涉及函数”是否排除某类改动、是否处理嵌套补丁，需要进一步确认。本项目保留原始 0，并记录为有证据的待澄清项。

**HarmonyOS CVE-2023-52756：函数数无法确认，CVE 状态另有异常。** [原始 OpenHarmony patch](https://gitee.com/openharmony/kernel_linux_5.10/commit/57898356796547b947e4d3fe59e13ed11e232773.patch)本轮只返回登录页面，没有据此判断函数数的条件。[官方 CNA JSON](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2023/52xxx/CVE-2023-52756.json)确认编号已撤回，但没有保留正文描述或足够的撤回原因。不能以其他 Linux 补丁替代原 fork 补丁，也不能根据 REJECTED 自动推断其代码修改量。

## 后续人工核验如何进行

两位成员应各自读取证据并填写自己的原始判断；可读 diff 的 8 条优先执行。4 条 Gitee 材料需要取得有权访问的原始提交内容，或找到能核验提交身份的公开等价材料；未取得前保持未确认。对 0/1 函数计数的问题，应明确“函数定义/函数体变更/函数调用”的计数口径，以及是否先解开 Debian 的内嵌补丁，再讨论是否需要扩展检查范围。

本轮新增 9 项离线测试，覆盖 HTTP 200 登录页、Gitiles base64 正确/损坏内容、内嵌补丁、删除文件、只有文件头的假阳性、CVE 撤回记录和错误 CVE ID。测试不访问公网；真实下载结果另见审计产物。
