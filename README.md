# 3D 积木式大脑模型

一个基于真实大脑解剖数据的交互式 3D 积木大脑模型。将大脑体素化为约 **18.5 万个小方块**，按 **116 个脑区**着色，支持点击选中、拆解/组装、旋转缩放与白色屏幕空间描边。

## 功能特性

- **真实解剖数据**：使用 AAL（Automated Anatomical Labelling）脑图谱，MNI 标准空间健康人模型。
- **体素积木化**：185,405 个体素方块，紧密贴合无缝隙，按 116 个脑区着色。
- **分区配色**：相近功能脑区归入同一色系，相邻脑区自动分配不同明度以保证对比度。
- **点击选中**：单击模型脑区显示该脑区的功能列表与复杂任务协作链路；点击右侧脑区列表选中/取消选中。
- **白色屏幕空间描边**：选中脑区用白色动态轮廓标记，实时计算屏幕朝向边界，可透出外层脑区看到内层脑区。
- **拆解 / 组装**：左键长按拖拽脑区将其拆解，松开时距正确位置小于阈值（`max(|dx|,|dy|,|dz|) < 5`）自动吸附回原位。
- **撤销 / 重做 / 重置**：支持完整历史栈与一键复位。

## 操作说明

| 操作 | 效果 |
| --- | --- |
| 左键单击模型脑区 | 显示该脑区详情 + 白色描边 |
| 左键长按拖拽脑区 | 拆解 / 组装脑区 |
| 右键拖拽 | 3D 旋转模型 |
| 滚轮 | 缩放 |
| 点击右侧脑区列表 | 选中 / 取消选中对应脑区 |
| 重置 / 撤销 / 重做 | 回归初始 / 回退 / 前进 |

## 技术栈

- **Three.js**：3D 渲染、体素实例化（InstancedMesh）、后处理描边（EffectComposer + OutlinePass）
- **Vite**：开发与构建
- **Python**（`numpy` + `requests`）：下载并解析 NIfTI 脑图谱，生成体素 JSON 数据

## 数据来源

- AAL 脑图谱（Automated Anatomical Labelling，116 脑区），MNI 单被试标准空间。
- 原始数据来自 [FieldTrip template/atlas/aal](https://github.com/fieldtrip/fieldtrip/tree/master/template/atlas/aal)：`ROI_MNI_V4.nii`（2mm 各向同性，91×109×91）。

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

浏览器打开输出的本地地址（默认 http://localhost:5173/）即可。

### 重新生成脑区数据

`public/brain.json` 已预生成，如需重新下载并处理原始脑图谱：

```bash
python scripts/build_data.py
```

## 项目结构

```
.
├── index.html                 # 页面入口与布局
├── package.json               # 依赖与脚本
├── src/
│   ├── main.js                # Three.js 渲染、交互、描边
│   └── style.css              # 界面样式
├── public/
│   └── brain.json             # 预处理后的体素积木数据（116 脑区）
├── scripts/
│   ├── build_data.py          # 下载/解析 NIfTI → JSON
│   └── inspect_atlas.py       # 数据头部信息检查
├── data/
│   ├── ROI_MNI_V4.nii         # AAL 脑图谱（大端 NIfTI）
│   └── ROI_MNI_V4.txt         # 116 个脑区标签
└── task.txt                   # 需求说明
```

## 界面结构

```
功能按键（重置/撤销/重做） | 脑区列表
——————————————————————————————
       3D 大脑积木模型       |
                            |
——————————————————————————————
        选中脑区详细信息
```
