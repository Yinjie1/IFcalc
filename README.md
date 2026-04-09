# IFcalc

此文档由 LLM 生成。

一个用于计算期刊影响因子(IF)的小型 Python 工具包，支持对引用数据做双侧裁剪(去掉高/低引用尾部样本)、导入导出和按 CSV 直接绘图。

## IF 定义

某年的影响因子定义为前两年论文(Article)和综述(Review Article)引用数总和，除以前两年的论文与综述总数：

$$
IF(y)=\frac{\sum_{i=1}^{N^{y-1}}C^{y-1}_i+\sum_{i=1}^{N^{y-2}}C^{y-2}_i}{N^{y-1}+N^{y-2}}
$$

- $N^y$: 年份 $y$ 的 Article + Review Article 总数
- $C_i^y$: 年份 $y$ 第 $i$ 篇文章的引用数

在本程序中，`ifCalc(delta)` 先对某年引用数组排序，再按比例去掉头尾样本，最后对保留样本求均值作为该年 IF。

## 程序功能

- `read(path, journal=None)`
  - 读取 Web of Science 导出的 txt
  - 解析期刊原始名称与目标年份列
  - 追加引用数据(不覆盖)
- `Journal.ifCalc(delta)`
  - 计算各年份 IF
  - `delta` 可传比例(0~0.5)或百分数(如 `10` 表示 10%)
- `Journal.export()` / `import_journal(path)`
  - Journal 与 JSON 的导出/导入
  - 导入时检查内存中是否已有同 `identifier` 的 Journal
- `write(journal, *deltas)`
  - 输出多组 delta 的 IF 结果到 CSV
  - 文件名使用期刊原始名称：`<name>.csv`
- `plot_from_csv(csv_path, output_path=None)`
  - 从 `write(...)` 生成的 CSV 直接画图
  - 绘图模块懒加载，不影响无 matplotlib 环境下的核心计算

## 代码实现

### 1) 数据模型

- `Journal.identifier`: 规范化标识(CamelCase)
- `Journal.name`: 期刊原始名称(保留空格)
- `Journal._citations`: `dict[Year, np.ndarray[np.int16]]`

`Journal` 支持索引、长度和迭代：

- `journal[year]` 获取该年引用数组
- `len(journal)` 获取已加载年份数
- `for year in journal` 遍历年份

### 2) 导入流程

`read(...)` 主要步骤：

1. 从首行提取原始期刊名和 publication years
2. 推导目标引用列年份(如 2008/2009 -> 2010)
3. 解析 CSV 表头和数据行
4. 提取目标年份列并追加到 Journal

### 3) 计算流程

`ifCalc(delta)` 主要步骤：

1. 校验并标准化 `delta`
2. 对每年数组排序
3. 裁剪头尾 `int(N * ratio)` 个值
4. 对剩余样本求均值并返回字典

### 4) 可选绘图设计

- 绘图代码在 `IFcalc/plotting.py`
- 包入口使用懒加载暴露 `plot_from_csv`
- 普通 `import IFcalc` 不会直接导入 matplotlib

## 示例

### 示例 1: 读取并计算 IF

```python
import IFcalc

journal = IFcalc.read("2010.txt")
print(journal.identifier)  # ChinesePhysicsC
print(journal.name)        # chinese physics c

if_values = journal.ifCalc(10)
print(if_values)
```

### 示例 2: 导出/导入 Journal

```python
import IFcalc

journal = IFcalc.read("2010.txt")
json_path = journal.export()

# 如果内存中已存在同 identifier 的 Journal，会抛 ValueError
loaded = IFcalc.import_journal(json_path)
print(loaded.identifier)
```

### 示例 3: 输出多组 delta 到 CSV

```python
import IFcalc

journal = IFcalc.read("2010.txt")
csv_path = IFcalc.write(journal, 0, 5, 10, 15)
print(csv_path)
```

### 示例 4: 从 CSV 直接绘图(可选)

```python
import IFcalc

png_path = IFcalc.plot_from_csv("chinese physics c.csv")
print(png_path)
```

> [!NOTE]
> 如果当前环境未安装 matplotlib，调用 `plot_from_csv(...)` 时会提示安装依赖，但不影响其他功能使用。
