# PySciCompTool / 星算工坊

(本程序由暨南大学谢金言，杨华长，陈浩翔，闫天一四人共同完成，用于提交课程作业。）

星算工坊是一个基于 Python + Tkinter 的科学计算工具，面向 Python 实验课程设计场景。程序提供符号计算、数值计算、数据分析和数据可视化等功能，支持通过图形界面输入公式、导入 CSV/Excel 数据并生成图表。

## 主要功能

- 符号计算：表达式计算、求导、积分、方程求解、傅里叶变换等。
- 数值计算：数值求导、数值积分、数值方程求根等。
- 数据分析：导入 CSV / Excel 文件，预览数据，统计均值、中位数、方差、标准差、最大值、最小值等。
- 数据可视化：绘制折线图、散点图、多项式拟合图，支持基础交互查看。
- 图形界面：提供启动界面、主题切换、状态栏图标和常用功能入口。

## 目录结构

```text
PySciCompTool/
├─ PySciCompTool.py        # 程序入口
├─ requirements.txt        # 运行依赖
├─ assets/                 # 图标等静态资源
├─ 前端/                   # Tkinter 图形界面
├─ 后端/                   # 符号计算、数值计算、数据分析、绘图逻辑
└─ tests/                  # 项目测试代码
```

## 运行环境

建议使用 Python 3.10 及以上版本。

安装依赖：

```bash
pip install -r requirements.txt
```

启动程序：

```bash
python PySciCompTool.py
```

## Windows 可执行文件

如果不想配置 Python 环境，可以在 GitHub Releases 页面下载打包好的 Windows 可执行文件：

```text
星算工坊.exe
```

下载后双击运行即可。

## 依赖说明

项目主要依赖：

- `sympy`：符号计算
- `numpy`：数值处理
- `pandas`：CSV / Excel 数据处理
- `matplotlib`：图表绘制
- `scipy`：数值积分、方程求根等科学计算功能
- `openpyxl`：Excel 文件读取支持

## 注意事项

- 源码仓库不包含打包产物，`build/`、`dist/` 和 `.exe` 文件不会提交到 Git。
- Windows 可执行文件放在 Release 中，方便直接下载。
- 如果导入 Excel 文件失败，请确认已安装 `openpyxl`。
- 如果图表显示异常，可以尝试切换图表类型后重新生成。
