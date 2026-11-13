/** Build the editable 10-slide Chinese defense deck using the Codex artifact runtime.
 * Data are read from committed results. No statistical result is recomputed here.
 * Run with the bundled Node.js. See presentations/README.md for dependencies.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const tmp = path.join(root, 'work', 'slides');
const output = path.join(root, 'presentations');
const runtime = process.env.CODEX_PRESENTATION_RUNTIME ?? 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const skill = process.env.CODEX_PRESENTATION_SKILL ?? 'C:/Users/Administrator/.codex/plugins/cache/openai-primary-runtime/presentations/26.1112.11217/skills/presentations';
process.env.RUNTIME_NODE_MODULES = path.join(runtime, 'node', 'node_modules');
process.env.RUNTIME_NODE = path.join(runtime, 'node', 'bin', 'node.exe');
process.env.RUNTIME_PYTHON = path.join(runtime, 'python', 'python.exe');
process.env.RUNTIME_BIN_DIR = path.join(runtime, 'bin', 'override');
await fs.mkdir(tmp, { recursive: true });
await fs.mkdir(output, { recursive: true });
try { await fs.symlink(path.join(runtime, 'node', 'node_modules'), path.join(tmp, 'node_modules'), 'junction'); }
catch (error) { if (error.code !== 'EEXIST') throw error; }
const requireFromBuild = createRequire(path.join(tmp, 'builder.cjs'));
const { Presentation, PresentationFile, FileBlob } = await import(pathToFileURL(requireFromBuild.resolve('@oai/artifact-tool')).href);
const { finalizePresentation, resolvePresentationFont } = await import(pathToFileURL(path.join(skill, 'container_tools', 'artifact_tool_utils.mjs')).href);
const font = resolvePresentationFont({ fontFamily: 'Microsoft YaHei' });
const fontPolicy = { basis: 'design', families: [font] };
const [univariate, core, categoryPolicy, evidenceAudit] = await Promise.all([
  fs.readFile(path.join(root, 'results/full/tables/univariate_summary.json'), 'utf8').then(JSON.parse),
  fs.readFile(path.join(root, 'results/full/stage_summary.json'), 'utf8').then(JSON.parse),
  fs.readFile(path.join(root, 'results/category_policy/run_summary.json'), 'utf8').then(JSON.parse),
  fs.readFile(path.join(root, 'results/review_evidence/audit.json'), 'utf8').then(JSON.parse),
]);
if (univariate.cell_count !== 114 || univariate.matched_cells !== 114) throw new Error('Recheck RQ1 slide against current results.');
if (core.comparisons.joint.cell_count !== 438 || core.comparisons.joint.matched_cells !== 438 || core.comparisons.similarity.cell_count !== 9 || core.comparisons.similarity.matched_cells !== 8) throw new Error('Core RQ2/RQ3 results changed: revise slides.');
if (categoryPolicy.policy_summary.pairwise_nonzero.matched_pairs !== 9 || categoryPolicy.policy_summary.pairwise_nonzero.pairs_with_exclusions !== 1) throw new Error('Category-set sensitivity changed: revise slide 6.');
if (evidenceAudit.sample_count !== 12 || evidenceAudit.confirmed_diff_count !== 8 || evidenceAudit.unconfirmed_count !== 4 || evidenceAudit.human_reannotation_completed !== false) throw new Error('Evidence review status changed: revise slide 9.');
const android = univariate.dimensions.trigger_scenario.Android.counts;
const harmony = univariate.dimensions.trigger_scenario.HarmonyOS.counts;
if (JSON.stringify(android) !== '[156,44,185,36,74,5,0]' || JSON.stringify(harmony) !== '[14,33,263,120,56,14,0]') throw new Error('Trigger vectors changed: revise interpretation.');

const C = { bg: '#F8F9FB', ink: '#182A3D', muted: '#526274', blue: '#245A8D', teal: '#276A67', rule: '#CAD4DF', pale: '#EAF0F6', white: '#FFFFFF', amber: '#9D4D20', amberPale: '#FFF0E3' };
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const sources = {
  paper: 'https://arxiv.org/html/2608.20643v1',
  repo: 'https://github.com/Asriel666/CS340-OS-Defects-Replication',
  data: 'https://github.com/zuohongyao/zuohongyao.github.io/blob/832d536f5d381d428a887e59ceeacc90a40e3b7e/index.html',
};
const notes = [];

function txt(slide, name, value, x, y, w, h, size = 28, color = C.ink, bold = false, align = 'left') {
  const s = slide.shapes.add({ geometry: 'textbox', name, position: { left: x, top: y, width: w, height: h }, fill: 'none', line: { fill: 'none', width: 0 } });
  s.text = value;
  s.text.style = { typeface: font, fontSize: size, color, bold, alignment: align, verticalAlignment: 'top', autoFit: 'none', wrap: 'square', insets: 0 };
  return s;
}
function page(title, foot, note) {
  const s = p.slides.add();
  s.background.fill = C.bg;
  const n = p.slides.items.length;
  txt(s, 'title', title, 64, 44, 1152, 70, 44, C.ink, true);
  txt(s, 'source-footer', foot, 64, 658, 1080, 32, 16, C.muted);
  txt(s, 'page-number', String(n).padStart(2, '0'), 1160, 658, 56, 32, 16, C.muted, false, 'right');
  s.speakerNotes.text = note;
  notes.push({ number: n, title, note });
  return s;
}
function table(slide, values, x, y, widths, rowHeight = 60, fontSize = 24, options = {}) {
  const t = slide.tables.add({ rows: values.length, columns: values[0].length, left: x, top: y, width: widths.reduce((a, b) => a + b, 0), height: values.length * rowHeight, columnWidths: widths, values });
  t.borders.assign({ style: 'solid', fill: C.rule, width: 0.65 });
  t.styleOptions = { headerRow: false, bandedRows: false };
  for (let r = 0; r < values.length; r++) {
    t.rows[r].height = rowHeight;
    for (let c = 0; c < values[0].length; c++) {
      const cell = t.getCell(r, c);
      cell.fill = r === 0 ? C.ink : C.white;
      cell.text.style = { typeface: font, fontSize, color: r === 0 ? C.white : C.ink, bold: r === 0, alignment: c === 0 ? 'left' : 'center', verticalAlignment: 'middle', autoFit: 'none', insets: 10 };
    }
  }
  for (const [r, c] of options.highlight ?? []) {
    t.getCell(r, c).fill = C.amberPale;
    t.getCell(r, c).text.style = { typeface: font, fontSize, color: C.amber, bold: true, alignment: c === 0 ? 'left' : 'center', verticalAlignment: 'middle', autoFit: 'none', insets: 10 };
  }
  return t;
}

// 1. The title page is deliberately simple and makes attribution explicit.
{
  const s = page('', 'CS340 论文复现进度答辩  ·  2026-11-14', `本报告介绍团队仓库的当前复现结果。报告人是 1230037310 钟峻瀚。原作者发布了 1,500 条标签，团队仓库重新计算统计结果，Codex 协助实现、验证、材料整理和本演示文稿。不能将团队结果表述为报告人独立完成全部代码或重新标注。共同署名与实际分工仍需成员确认。\n\n来源：${sources.paper}\n${sources.repo}\n仓库：docs/reproduction_report.md、docs/weekly/2026-11-14.md。`);
  txt(s, 'course', 'CS340 操作系统', 64, 100, 900, 44, 26, C.blue, true);
  txt(s, 'cover-title', '操作系统缺陷研究\n论文复现与方法核查', 64, 185, 1120, 180, 60, C.ink, true);
  txt(s, 'paper-title', 'Toward Understanding Operating System Defects', 68, 402, 1120, 44, 28, C.muted);
  txt(s, 'presenter', '报告人  1230037310 钟峻瀚', 68, 505, 1120, 42, 30, C.ink, true);
  txt(s, 'attribution', '基于团队仓库结果，Codex 协助计算与材料整理', 68, 563, 1120, 38, 24, C.muted);
}
// 2. Data and methods.
{
  const s = page('数据来源与复现范围', '来源：作者固定提交 832d536f ；论文 Table II、Tables III–V、Figure 4(a–c)', `本次复现使用作者已发布的标签，Android、Linux、HarmonyOS 各 500 条。通过固定 Git 提交和 SHA-256 摘要锁定输入，程序仅解析 JSON 数组，不执行网页 JavaScript。RQ1 是五个单维分布，RQ2 是三个联合分布，RQ3 是三个维度上的系统对相似度。表格百分比以每个系统 500 条为分母。Linux 样本包括 Ubuntu 生态，三个系统的采样渠道不同，结果只描述该样本，不能直接评价操作系统质量。\n\n来源：${sources.data}\n${sources.paper}#S4\n仓库：results/full/source_provenance.json、results/full/data_validation.json。`);
  txt(s, 'sample-count', '1,500', 64, 145, 340, 98, 76, C.blue, true);
  txt(s, 'sample-label', '作者已标注的缺陷记录', 70, 254, 390, 40, 28, C.ink);
  txt(s, 'sample-split', 'Android 500\nLinux 500\nHarmonyOS 500', 70, 324, 370, 150, 30, C.muted);
  txt(s, 'scope-heading', '本项目重算三个研究问题', 540, 155, 670, 50, 32, C.ink, true);
  txt(s, 'scope-body', 'RQ1  缺陷在五个维度如何分布\n\nRQ2  不同分类维度如何共现\n\nRQ3  不同系统的分布有多相似', 540, 230, 650, 260, 28, C.ink);
  txt(s, 'scope-caveat', '标签来自原作者。固定样本的统计吻合，不代表重新标注完成或系统质量排名。', 64, 550, 1152, 66, 26, C.amber);
}
// 3. Editable table summarizes Table II coverage.
{
  const s = page('RQ1：五维分类分布全部吻合', '来源：results/full/tables/table_ii.csv、univariate_summary.json；论文 Table II', `单维比例等于具有该标签的缺陷数量除以 500。五个维度分别有 6、8、7、5、12 类，对三个系统共比较 114 个百分比，全部吻合。前四维为单标签，因此各自合计 100%。代码元素是多标签，分母仍为 500，类别比例之和可以超过 100%。右侧只展示系统层次的最大类别，不等于全部缺陷都在这些层。\n\n来源：${sources.paper}#S4.T2\n仓库：results/full/tables/table_ii.csv、results/full/tables/univariate_summary.json。`);
  table(s, [['分类维度', '类别数', '比较项'], ['系统层次', '6', '18'], ['受影响功能', '8', '24'], ['触发场景', '7', '21'], ['严重性', '5', '15'], ['代码元素', '12', '36']], 64, 150, [270, 150, 150], 63, 25);
  txt(s, 'coverage', '114 / 114', 700, 150, 500, 90, 62, C.teal, true);
  txt(s, 'coverage-label', 'Table II 百分比吻合', 704, 243, 500, 40, 28, C.ink);
  txt(s, 'dominant-title', '系统层次的最大类别', 704, 324, 510, 40, 27, C.ink, true);
  txt(s, 'dominant-values', 'Android  系统服务 38.8%\nLinux  应用层 54.2%\nHarmonyOS  内核层 71.8%', 704, 381, 510, 145, 26, C.muted);
  txt(s, 'denominator', '统一分母为每系统 500 条。代码元素允许多标签，不要求各类比例合计 100%。', 64, 576, 1152, 64, 25, C.amber);
}
// 4. Joint distributions and concrete interpretive examples.
{
  const s = page('RQ2：三组联合分布全部吻合', '来源：results/full/tables/joint_comparison.csv、joint_summary.json；论文 Tables III–V', `联合分布单元格用该格缺陷数除以该系统全部 500 条，而不是进行行归一化。三个系统下的每张矩阵总计 500，行列边际与 RQ1 一致。Table III 是 6×8，三个系统共 144 项。Table IV 是 6×7，共 126 项。Table V 是 8×7，共 168 项。右侧三个例子对应 143、198、179 条，分母均是 500。共现结果不能作为因果结论。\n\n来源：${sources.paper}#S4.T3\n${sources.paper}#S4.T4\n${sources.paper}#S4.T5\n仓库：results/full/tables/joint_comparison.csv、results/full/tables/joint_summary.json。`);
  txt(s, 'rq2-coverage', '438 / 438', 64, 142, 600, 86, 60, C.teal, true);
  table(s, [['联合表', '维度', '吻合'], ['III', '层次 × 功能', '144/144'], ['IV', '层次 × 触发', '126/126'], ['V', '功能 × 触发', '168/168']], 64, 260, [100, 260, 170], 66, 24);
  txt(s, 'rq2-examples-title', '占该系统全部缺陷的比例', 684, 155, 530, 44, 28, C.ink, true);
  txt(s, 'example-a', '28.6%  Android\n系统服务层 × 安全与权限', 684, 228, 530, 90, 27, C.blue);
  txt(s, 'example-h', '39.6%  HarmonyOS\n内核层 × 边界条件触发', 684, 340, 530, 90, 27, C.blue);
  txt(s, 'example-l', '35.8%  Linux\n兼容与适配 × 环境依赖', 684, 452, 530, 90, 27, C.blue);
  txt(s, 'marginal-check', '9 张矩阵均满足：总数为 500，行列边际与 RQ1 一致。', 64, 582, 1152, 44, 26, C.muted);
}
// 5. Preserve the prespecified fixed-category comparison.
{
  const s = page('RQ3：固定类别下 8 / 9 个系数吻合', '单元格为“论文 / 本项目”；比较精度为两位小数，完整精度保存在 CSV', `标准 Spearman 等于两个计数向量各自取升序平均秩后，再算秩的 Pearson 相关。三个维度按固定类别顺序对齐，并列值取平均秩。该页列出全部 9 个独立系统对，镜像单元格与对角线不重复计数。唯一差异是触发场景 Android 与 HarmonyOS，论文 0.38，固定七类重算 0.6126374746329801。下一页检查这一差异的可能方法原因，但不追溯性地修改预先声明的核心口径。\n\n来源：${sources.paper}/heatmap-a.png\n${sources.paper}/heatmap-b.png\n${sources.paper}/heatmap-c.png\n仓库：results/full/tables/similarity_comparison.csv、reference/similarity_baselines.json。`);
  table(s, [['维度', 'Android–HarmonyOS', 'Android–Linux', 'HarmonyOS–Linux'], ['系统层次', '-0.66 / -0.66', '0.26 / 0.26', '0.09 / 0.09'], ['受影响功能', '0.43 / 0.43', '-0.19 / -0.19', '-0.52 / -0.52'], ['触发场景', '0.38 / 0.61', '0.21 / 0.21', '0.41 / 0.41']], 64, 165, [220, 342, 290, 300], 82, 24, { highlight: [[3, 1]] });
  txt(s, 'spearman-method', '相同类别顺序，标准 Spearman，并列值采用平均秩。', 64, 538, 1152, 44, 28, C.ink);
  txt(s, 'rq3-scope', '维度分别保留 6 / 8 / 7 类。计数变成百分比不会改变秩。', 64, 593, 1152, 42, 25, C.muted);
}
// 6. A category-universe sensitivity test explains the rounded value.
{
  const s = page('共同零类别给出可检验的候选解释', '来源：results/category_policy/；docs/category_policy_analysis.md；原图 Figure 4(c)', `新增检验只改变两个系统比较时使用的类别集合，不改原始标签，也不改平均秩 Spearman。下表最后一类 Mul/Loc Dep 在 Android 和 HarmonyOS 中都为零，但 Linux 该类有一条。因此移除“三系统全零类别”不会删除它。采用两系统非零类别的并集，即仅删除这两个系统共同为零的类别，向量从七维变六维，Spearman 从 0.6126374746329801 变为 0.3768511731740915，两位小数正好为 0.38。相同规则用于全部九对时得到 9/9 的数值相容，只有该对的结果变化。它是对差异的候选解释，不能证明原作者实际这样实现。核心固定类别的 8/9 记录仍保留。\n\n来源：${sources.paper}/heatmap-c.png\n仓库：results/full/tables/univariate_summary.json、results/category_policy/、docs/category_policy_analysis.md。`);
  table(s, [['系统', '权限/身份', '常规操作', '边界条件', '并发', '状态依赖', '环境依赖', '多语言'], ['Android', ...android.map(String)], ['HarmonyOS', ...harmony.map(String)]], 64, 147, [180, 142, 142, 142, 120, 142, 142, 142], 71, 23, { highlight: [[1, 7], [2, 7]] });
  txt(s, 'fixed-title', '固定 7 类', 64, 411, 500, 44, 30, C.ink, true);
  txt(s, 'fixed-rho', 'ρ = 0.612637', 64, 470, 500, 60, 43, C.blue, true);
  txt(s, 'pairwise-title', '删除两系统共同为零的类别', 664, 411, 550, 44, 30, C.ink, true);
  txt(s, 'pairwise-rho', 'ρ = 0.376851 ≈ 0.38', 664, 470, 550, 60, 43, C.teal, true);
  txt(s, 'candidate-only', '该规则与原图数值相容，作者方法仍待确认。核心固定类别结果保持 8/9。', 64, 578, 1152, 60, 26, C.amber);
}
// 7. Distinguish a matching convention from confirmed author methods.
{
  const s = page('Figures 2/3：39 个柱值有相容的候选口径', '来源：results/repair_size/tables/config_match_summary.csv；docs/methods_appendix.md', `图 2 是修改行数，图 3 是涉及函数数和修改文件数。三组柱标签总共 39 个。已测试的候选中，左闭右开且最后一箱包含最终上界、零值计入第一箱、删失记录按下界归箱，可以 39/39 吻合。177 条函数数为零和 7 条带加号的下界记录使解释受到限制。HarmonyOS 最后函数数箱 14 条中 7 条为删失记录，保持未归属时该柱从 2.8% 变成 1.4%，其余 11 个函数数柱不变。不能因为一组假设完全吻合，就认定作者真的使用了同一脚本。Overall 的定义仍未确认，此页不纳入核心 561 项的完成率。\n\n来源：${sources.paper}/photo/group_changes.png\n${sources.paper}/photo/group_funcs.png\n仓库：reference/figure_baselines.json、results/repair_size/tables/config_match_summary.csv、docs/methods_appendix.md。`);
  table(s, [['指标', '候选口径', '吻合'], ['修改行数', '左闭右开', '15/15'], ['涉及函数数', '左闭右开，删失按下界', '12/12'], ['修改文件数', '左闭右开', '12/12']], 64, 157, [280, 620, 252], 76, 27);
  txt(s, 'boundary-notes', '末箱包含最终上界，零值归入首箱。', 64, 501, 1152, 44, 28, C.ink);
  txt(s, 'censoring-warning', '177 条函数数为零，7 条函数数仅有下界。\n39/39 表明统计相容，作者实际分箱脚本仍待确认。', 64, 560, 1152, 68, 25, C.amber);
}
// 8. Runtime evidence without a stale hardcoded test count.
{
  const s = page('运行与核验', '来源：README.md；results/full/verification.json；docs/weekly/2026-11-14.md', `助教可以从 README 安装全局 Python 3.11 的依赖，再用这一条命令运行三个研究问题、三次计算和图表。首次联网下载固定输入并检查摘要，已有合法缓存可离线复跑。单项 rq1、rq2、rq3 和旧 Stage 1 入口都保留。运行记录保留命令、环境、输入摘要、结果摘要以及逐项对比 CSV。测试覆盖数据摘要错误、重复 ID、未知标签、缺项基准、联合分布边际和 Spearman 并列秩。三次相同结果只说明固定输入下的执行稳定，不等于三次独立采样实验，也不能证明人工标签正确。最终测试数量和本轮复跑证据以当日周报为准。\n\n来源：${sources.repo}\n仓库：README.md、results/full/verification.json、results/full/tables/repeated_run_statistics.csv、docs/weekly/2026-11-14.md。`);
  txt(s, 'run-label', '核心复现命令', 64, 156, 1120, 44, 30, C.ink, true);
  txt(s, 'run-command', 'py -3.11 scripts/run_stage.py --analysis all --runs 3', 64, 225, 1152, 62, 30, C.blue, true);
  txt(s, 'validation-a', '输入可追溯\n固定版本、SHA-256 校验、离线缓存', 64, 341, 550, 116, 28, C.ink);
  txt(s, 'validation-b', '结果可审阅\n逐项 CSV、图表、环境与运行日志', 664, 341, 550, 116, 28, C.ink);
  txt(s, 'tests-label', '关键检查覆盖：重复 ID、未知标签、缺失基准、联合边际与并列秩。', 64, 510, 1152, 68, 26, C.muted);
  txt(s, 'execution-boundary', '连续三次一致验证执行稳定性，不验证原始标签的正确性。', 64, 589, 1152, 43, 26, C.amber);
}
// 9. Evidence preparation remains separate from the two human reviewers.
{
  const s = page('12 条抽查：证据已整理，人工判断待完成', '来源：results/review_evidence/；docs/review_evidence_audit.md；自动化检查不计为真人独立审核', `每个系统按缺陷 ID 排序，固定随机种子 340 抽 4 条，共 12 条。自动化核验已区分 HTTP 成功状态与真实补丁内容。Android 与 Linux 的 8 条获取到实质 diff，HarmonyOS 的 4 条原链接重定向至 Gitee 登录页，不能因为最终返回 200 就声称获得了补丁。盲审材料将作者标签放入 coordinator/author_labels.csv，与 reviewer_A.csv、reviewer_B.csv 分开。两位真实参与者分别阅读报告和补丁，填写系统层次、功能、触发场景及证据，随后保留分歧与仲裁依据。目前人工判断都未填写，因此不能报告标签一致率。缺少公开证据的条目允许标记未确认。另有 CVE-2023-52756 的官方记录为 REJECTED，撤回原因未说明，不等于代码没有缺陷，原数据保留。详见审计文档与 results/review_evidence/cve_sources.json。\n\n仓库：docs/review_evidence_audit.md、review_materials/blind/reviewer_A.csv、review_materials/blind/reviewer_B.csv、review_materials/coordinator/author_labels.csv。`);
  table(s, [['系统', '抽样条数', '获取实质补丁', '人工审核'], ['Android', '4', '4', '待完成'], ['Linux', '4', '4', '待完成'], ['HarmonyOS', '4', '0，原链接需登录', '待完成']], 64, 158, [280, 210, 390, 272], 76, 26, { highlight: [[3, 2]] });
  txt(s, 'review-design', 'A / B 独立填写，作者标签单独保存，之后比较分歧和证据。', 64, 511, 1152, 50, 27, C.ink);
  txt(s, 'review-boundary', '实质补丁 8/12，人工判断 0/12。无法获取的证据保持“未确认”。', 64, 584, 1152, 50, 27, C.amber);
}
// 10. Concrete finish line and remaining scope.
{
  const s = page('当前结论与下一步', '报告人：1230037310 钟峻瀚；团队成员署名与实际贡献由成员共同确认', `当前可明确报告的核心结果是 552 个表格百分比全部吻合，9 个相关系数在固定类别下 8 个吻合。新增类别集合检验对原图 0.38 给出一个相容且可检验的解释，但作者方法仍未确认。下一步由两位实际参与者完成盲审并记录真实分工，然后进行答辩演练。需要作者澄清的问题已经具体化：Figure 4(c) 是否按系统对删除共同零类别，Figures 2/3 的分箱和删失处理，Figure 4(d) Overall 输入定义与系统对标注。任何对作者的联络都需要实际授权，本报告仅列出待确认事项，不表示已经发送询问。\n\n来源：${sources.repo}\n仓库：docs/reproduction_report.md、docs/category_policy_analysis.md、docs/methods_appendix.md、docs/review_evidence_audit.md。`);
  txt(s, 'closing-stat', '552 / 552 表格值吻合', 64, 152, 1152, 80, 48, C.teal, true);
  txt(s, 'closing-rho', '8 / 9 固定类别系数吻合，共同零类别给出差异的候选解释。', 64, 255, 1152, 82, 30, C.ink);
  txt(s, 'next-heading', '接下来由实际参与者完成', 64, 371, 1152, 48, 30, C.ink, true);
  txt(s, 'next-steps', '01  完成两份独立盲审，记录证据与分歧\n02  确认共同署名、实际分工并完成答辩演练\n03  向作者核实类别集合、分箱脚本和 Overall 定义', 64, 438, 1152, 166, 29, C.muted);
}

if (p.slides.items.length !== 10) throw new Error('Expected exactly ten slides.');
await fs.writeFile(path.join(output, 'speaker_notes.md'), '# 操作系统缺陷论文复现答辩讲解稿\n\n报告人：1230037310 钟峻瀚。基于团队仓库成果，Codex 协助编写。\n\n' + notes.map(n => `## 第 ${n.number} 页：${n.title || '操作系统缺陷研究论文复现与方法核查'}\n\n${n.note}\n`).join('\n'), 'utf8');
await fs.writeFile(path.join(tmp, 'presentation.json'), JSON.stringify(p.toProto()), 'utf8');
const candidate = path.join(tmp, `candidate-${Date.now()}.pptx`);
await (await PresentationFile.exportPptx(p)).save(candidate);
let finalPath = path.join(output, process.argv[2] ?? 'defense_2026-11-14_v2.pptx');
try { await fs.access(finalPath); finalPath = finalPath.replace(/\.pptx$/, `_${Date.now()}.pptx`); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const result = await finalizePresentation({
  workspaceDir: root,
  candidatePath: candidate,
  finalPath,
  pythonExecutable: path.join(runtime, 'python', 'python.exe'),
  integrityValidatorPath: path.join(skill, 'container_tools', 'inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill, 'container_tools', 'inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', ...[3, 4, 5, 6, 7, 9].flatMap(n => ['--require-native-table-slide', String(n)])],
  explicitTotalSlideCount: 10,
  requiredNativeTableOwnerSlides: [3, 4, 5, 6, 7, 9],
  requiredNativeChartOwnerSlides: [],
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(tmp, `${path.basename(finalPath)}.validation-${Date.now()}.json`),
});
console.log(JSON.stringify({ finalPath, validation: result }, null, 2));
// Render the validated exported file, not just the pre-export in-memory model.
const finalDeck = await PresentationFile.importPptx(await FileBlob.load(finalPath));
for (const [index, slide] of finalDeck.slides.items.entries()) {
  const blob = await finalDeck.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(path.join(tmp, `slide-${String(index + 1).padStart(2, '0')}.png`), new Uint8Array(await blob.arrayBuffer()));
}
await fs.writeFile(path.join(tmp, 'final-path.txt'), finalPath, 'utf8');
console.log('Rendered all 10 final slides for visual inspection.');
