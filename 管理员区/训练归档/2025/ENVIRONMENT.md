# 参考运行环境

本次 2025 A/B 独立计算使用或核验过的参考环境：

| 组件 | 版本 |
|---|---|
| Python | 3.12.14 |
| NumPy | 2.5.2 |
| SciPy | 1.18.1 |
| pandas | 2.3.3 |
| Matplotlib | 3.11.1 |
| openpyxl | 3.1.5 |
| python-docx | 1.2.0 |
| 操作系统 | Windows |

注意：

- 版本来自本次工作区的 Python 3.12 运行时；
- 当前机器默认的另一套 Python 3.13 与历史二进制缓存不兼容，因此不得把缓存 site-packages 一并复制；
- 材料包只保存 requirements.txt，不保存 Python 二进制和依赖缓存；
- 下一届比赛应新建隔离环境、安装依赖并运行冒烟测试；
- 计算代码应尽量跨平台，Word 排版和公式构建可能仍依赖 Microsoft Word；
- 最终 PDF 是版式基准，跨平台生成后必须逐页检查。
