# IFcalc

> 此文档由 LLM 生成. 已通过人工复核.

一个用于计算期刊影响因子(IF)的小型 Python 工具包, 支持对引用数据做双侧裁剪(去掉高/低引用尾部样本), 导入导出和绘图.

## IF 定义

某年的影响因子定义为前两年论文(Article)和综述(Review Article)引用数总和, 除以前两年的论文与综述总数:

$$
IF(y)=\frac{\sum_{i=1}^{N^{y-1}}C^{y-1}_i+\sum_{i=1}^{N^{y-2}}C^{y-2}_i}{N^{y-1}+N^{y-2}}
$$

- $N^y$: 年份 $y$ 的 Article + Review Article 总数
- $C_i^y$: 年份 $y$ 第 $i$ 篇文章的引用数

在本程序中, `ifCalc(delta)` 先对某年引用数组排序, 再按比例去掉头尾样本, 最后对保留样本求均值作为该年 IF.

## 功能与实现

### 环境依赖

- Python: `3.13`
- 必需依赖包:
  - `numpy`
- 可选依赖包:
  - `matplotlib` (仅绘图需要)

### 核心数据模型

- `Journal.identifier`: 规范化标识(CamelCase)
- `Journal.name`: 原始期刊名称(保留空格)
- `Journal._citations`: `dict[Year, np.ndarray[np.int16]]`

`Journal` 对象支持字典索引 `journal[year]`, 求长度`len(journal)`, 迭代`for year in journal`.

### 主要 API

- `read(path, journal=None)`
  - 读取 WoS txt 并追加引用数据
  - 自动推导目标年(支持双年份和单年份首行)
- `Journal.ifCalc(delta)`
  - 按 `delta` 裁剪头尾后计算各年份 IF
- `Journal.export()` / `import_journal(path)`
  - Journal 与 JSON 导出/导入
  - 按 `identifier` 做内存重复检查
- `write(journal, *deltas)`
  - 批量输出 IF 到 `<name>.csv`
- `transpose(path)`
  - 将 CSV 行列转置为 `<原文件名>-t.csv`
- `plot_from_csv(csv_path, output_path=None)`
  - 从 `write(...)` 结果直接绘图(懒加载 matplotlib)

### 关键流程

1. `read(...)`: 解析首行 -> 推导目标年 -> 读取目标列 -> 追加到 `Journal`
2. `ifCalc(delta)`: 标准化 `delta` -> 排序 -> 裁剪头尾 -> 求均值
3. `write(...)` / `transpose(...)` / `plot_from_csv(...)`: 输出结果表及可视化

> [!NOTE]
> 构建 `identifier` 时会去除首行中的括号说明(如 `(Publication Titles)`), 避免同一期刊在不同文件中的标识不一致.

## 示例

### 示例 1: 读取并计算 IF

```python
import IFcalc

journal = IFcalc.read("2010.txt")
print(journal.identifier)  # ChinesePhysicsC
print(journal.name)        # chinese physics c

if_values = journal.ifCalc(10) # 裁减10%并计算IF
print(if_values)
```

### 示例 2: 导出/导入 Journal

```python
journal = IFcalc.read("2010.txt")
json_path = journal.export()

# 如果内存中已存在同 identifier 的 Journal, 会抛 ValueError
loaded = IFcalc.import_journal(json_path)
print(loaded.identifier)
```

### 示例 3: 按多种比例裁减, 并输出 CSV 表格

```python
journal = IFcalc.read("2010.txt")
csv_path = IFcalc.write(journal, 0, 5, 10, 15)
print(csv_path)
```

### 示例 4: 从 CSV 直接绘图

```python
png_path = IFcalc.plot_from_csv("chinese physics c.csv")
print(png_path)
```

### 示例 5: CSV 行列转置

```python
transposed_path = IFcalc.transpose("chinese physics c.csv")
print(transposed_path)
```

## 完整工作流示例

### 1) WoS 原始 txt 样例

以 Science 2025年为例, 下面是导出文件前几行(示意格式, 关键在首行查询条件 + CSV 表头 + 数据行):

```text
science and 2023 or 2024 (Publication Years) and Review Article or Article (Document Types)
Timespan: 1980-2026.

"Title","Authors","Source Title","Publication Year",...,"2023","2024","2025"
"Example Paper A","Author1; Author2","SCIENCE","2023",...,"12","35","8"
"Example Paper B","Author3","SCIENCE","2024",...,"4","19","3"
```

> [!NOTE]
> WoS 中一次最多导出1000条记录, 同一年的记录可能需要导出为多个文件.
> 该程序能够通过 CSV 表头识别期刊和年份, 支持自动拼接相应的数据.

### 2) 端到端示例代码

将该脚本和仓库文件(整个 IFcalc 文件夹)复制到工作目录:

```python
from __future__ import annotations

from pathlib import Path
import shutil

import IFcalc

INPUT_DIR: Path = Path("./raw/SCIENCE") # WoS 导出的 txt 文件存放目录
OUTPUT_DIR: Path = Path("./OUT") # 处理后的数据输出目录
INPUT_PATTERN: str = "*.txt" # 一般不用改
DELTAS: tuple[int, ...] = tuple(range(0,26,2)) # 首尾裁减的比例
ANALYSE: bool = True # 计算每次裁剪相较上次裁减IF降低的百分比
PLOT: bool = True # 自动绘图
TRANSPOSE: bool = False # 行列转置


def main() -> None:
    """Run end-to-end IF calculation example for CPC files."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files: list[Path] = sorted(INPUT_DIR.glob(INPUT_PATTERN))
    if len(input_files) == 0:
        raise FileNotFoundError(f"No txt files found in: {INPUT_DIR.resolve()}")

    journal: IFcalc.Journal | None = None
    for input_file in input_files:
        journal = IFcalc.read(input_file, journal)

    if journal is None:
        raise ValueError("Journal initialization failed.")

    csv_path: Path = IFcalc.write(journal, *DELTAS, analyse=ANALYSE)
    target_csv_path: Path = OUTPUT_DIR / csv_path.name
    shutil.move(str(csv_path), str(target_csv_path))

    output_lines: list[str] = [
        f"Loaded files: {len(input_files)}",
        f"Journal identifier: {journal.identifier}",
        f"Journal name: {journal.name}",
        f"CSV output: {target_csv_path.resolve()}",
    ]

    if ANALYSE:
        source_analysis_path: Path = csv_path.with_name(f"{csv_path.stem}_analysis.csv")
        analysis_csv_path: Path = OUTPUT_DIR / source_analysis_path.name
        if source_analysis_path.exists():
            shutil.move(str(source_analysis_path), str(analysis_csv_path))
        decrease_csv_path = IFcalc.analyse(target_csv_path)
        output_lines.append(f"Analysis CSV output: {analysis_csv_path.resolve()}")
        output_lines.append(f"Decrease CSV output: {decrease_csv_path.resolve()}")

    if TRANSPOSE:
        transposed_csv_path = IFcalc.transpose(target_csv_path)
        output_lines.append(f"Transposed CSV output: {transposed_csv_path.resolve()}")

    if PLOT:
        image_path = IFcalc.plot_from_csv(target_csv_path)
        output_lines.append(f"Plot output: {image_path.resolve()}")
        if ANALYSE:
            analysed_image_path = IFcalc.plot_analysis_from_csv(analysis_csv_path)
            output_lines.append(f"Analysis plot output: {analysed_image_path.resolve()}")

    print("\n".join(output_lines))


if __name__ == "__main__":
    main()
```

> [!NOTE]
> 如果当前环境未安装 matplotlib, 调用 `plot_from_csv(...)` 时会提示安装依赖, 但不影响其他功能使用.
