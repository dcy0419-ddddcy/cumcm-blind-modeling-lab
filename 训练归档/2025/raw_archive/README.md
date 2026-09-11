# 2025 A/B 原始归档说明

本目录只在独立模型 V1 已冻结、且需要核查 2025 实现细节时上传给 AI。

## 包含

- 2025 A/B 原题 PDF；
- A 题官方提交模板与独立计算结果表；
- B 题四个原始数据附件；
- A/B 独立论文 PDF；
- A 题运动学、单弹/多弹优化和汇总代码；
- B 题峰序回归与多谐波分析代码；
- A_final.json、B/results.json 和支撑图。

## 唯一权威结果

- A 题：outputs/independent/A_final.json；
- B 题：outputs/independent/B/results.json；
- 其他 A_*.json 为历史搜索候选或汇总所需中间文件，不得与最终结果并列引用；
- outputs/final/result1.xlsx、result2.xlsx、result3.xlsx 为独立方案填写后的提交表。

## 明确排除

- C 题题面、附件、论文、数据和代码；
- tmp、缓存依赖、日志、渲染页和预览图；
- 官方优秀论文 JPG/HTML 本地副本，仅在 06_官方资料索引.md 保留官方 URL；
- 未脱敏 DOCX：原 DOCX 的 Office 元数据含本机账户邮箱，因此材料包只收录 PDF 和无元数据的 Markdown 转换版；
- build_papers.py、inspect_inputs.py：二者混有 C 题逻辑或本机输出路径；
- Codex 专用 Excel 检查脚本。

## 可移植性

代码是 2025 独立解答的工作记录，不是下一届题目的即插即用程序。

- Python 参考环境：3.12.14；
- 依赖版本见材料包根目录 requirements.txt；
- a_optimize.py、a_multi_optimize.py、a_finalize.py、b_analysis.py 会尝试加载 ROOT/tmp/python_packages；该目录不存在时应使用已安装的标准依赖；
- B 题代码要求从 2025_workspace 根目录保持“附件_B题/附件”相对结构；
- A 题汇总代码要求 outputs/independent 下的中间 JSON 完整；
- 新题必须重新检查路径、字段、单位、约束和模型，禁止只修改文件名后运行。

## 使用规则

- 历史数值只能用于复现 2025 案例；
- 新题结果不得继承任何历史参数；
- 所有代码先静态阅读，再运行测试；
- 若程序与论文不一致，以题面、严格评价器和实际运行证据为准；
- 发现绝对路径、个人信息或异常依赖时停止外发并记录。
