# 2024 国赛 A 题“板凳龙”独立成果

本目录是可复现的独立解题包。建模和编程阶段只使用了题面 `D:\2024\2024年_A题_板凳龙.pdf` 以及 `D:\2024\附件_A题\附件` 中的三个官方结果模板。未浏览、读取、引用或改写任何优秀论文或他人解答。

## 目录

- `report_A.md`：详细中文报告。
- `src/bench_dragon.py`：螺线、铰链、碰撞、双圆弧和速度上限模型。
- `run_all.py`：从零重算五问并产生 CSV/JSON。
- `tests/test_models.py`：几何、运动学、碰撞根和调头路径测试。
- `tooling/verify_refinements.py`：问题 2、3、5 的加密复核。
- `tooling/fill_templates.mjs`：将 CSV 原位填入官方 XLSX 模板。
- `computed/`：全量 CSV、摘要 JSON 和加密复核 JSON。
- `outputs/`：填好的 `result1.xlsx`、`result2.xlsx`、`result4.xlsx`。
- `logs/`：全量运行、加密复核和测试日志。
- `tmp/filled_previews/`：导出后工作表的质量检查图。

## 环境

已验证 Python 环境：NumPy 2.3.4、SciPy 1.16.3、pytest 8.3.4。

```powershell
python -m pip install -r D:\2024\work_independent\A\requirements.txt
```

Excel 填充使用 Codex 工作区附带的 `@oai/artifact-tool`；`tooling/node_modules` 是指向本机附带依赖的目录联接。

## 复现

在 `D:\2024` 下执行：

```powershell
python -u D:\2024\work_independent\A\run_all.py --output-dir D:\2024\work_independent\A\computed
python -u D:\2024\work_independent\A\tooling\verify_refinements.py
python -m pytest D:\2024\work_independent\A\tests\test_models.py -q
```

待 CSV 生成后填充官方模板：

```powershell
& 'C:\Users\28717\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' `
  'D:\2024\work_independent\A\tooling\fill_templates.mjs'
```

Excel 脚本会重新打开导出文件，扫描公式错误，检查关键范围，并渲染每张工作表。

## 关键结果

- 首次碰撞：412.473837682 s，龙头板与第 8 节龙身板。
- 最小螺距：0.450337393 m；限制半径 4.572603230 m。
- 双圆弧半径：3.005417668 m 和 1.502708834 m；总长 13.621244907 m。
- 最大速度放大系数：1.604793379；龙头速度上限 1.246266358 m/s；把手索引 3--7 在峰值构型中并列。

## 已执行的检查

- 模型单元测试 5 项全部通过。
- 问题 1 的全量最大孔距残差为 `1.2581047315e-12 m`。
- 问题 2 用 0.5 s 和 1.0 s 扫描均得到 412.473837682 s。
- 问题 3 用 0.02 m 径向网格复核得限制半径 4.572603226 m。
- 问题 5 用 0.25 m 和 0.125 m 峰值区网格复核，放大系数一致到 13 位有效数字。
- 三个 XLSX 的错误扫描均为 0 命中；5 张工作表预览无截断、重叠或乱码。

详细加密数据见 `computed/refinement_checks.json`，日志见 `logs/`。

