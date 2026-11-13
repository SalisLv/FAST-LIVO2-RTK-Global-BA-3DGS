# FAST-LIVO2-RTK + Global-LVBA + 3D Gaussian Splatting

从 ROS 1 Bag 生成带地理参考的轨迹、LiDAR 点云地图和可渲染的 3DGS 场景。运行入口依次执行 FAST-LIVO2 里程计、离线 GNSS/RTK 优化、LiDAR BA、Visual BA，以及 3DGS 训练和渲染。

## 1. 环境

- Linux x86-64 或 WSL2，安装 Git、Bash、Python 3 和 Docker。
- 3DGS 使用支持 CUDA 12.8 的 NVIDIA GPU，Docker 需要能通过 `--gpus all` 使用 GPU。ROS Noetic、COLMAP 和训练依赖在容器内运行。
- HH 验收使用约 8 GB GPU 显存及约 8 GB WSL 内存。较长序列的内存和磁盘占用会随输入增长。可在设备配置中调整抽帧、体素和训练参数。

## 2. 构建

```bash
git clone https://github.com/SalisLv/FAST-LIVO2-RTK-Global-BA-3DGS.git
cd FAST-LIVO2-RTK-Global-BA-3DGS
./build.sh
```

构建按 [sources.lock](sources.lock) 获取固定提交、初始化 3DGS CUDA 子模块，并应用 [patches](patches/) 下的实验补丁。源码和依赖保存在本地 `src/` 和 `.deps/`。可用 `CUDA_ARCH_LIST=12.0 ./build.sh` 只为 RTX 50 系列编译 CUDA 扩展。构建步骤需要访问上游代码仓库和软件包源。

## 3. 准备 Bag 并运行

可从 [FAST-LIVO2-RTK 上游的数据集说明](https://github.com/xuankuzcr/FAST-LIVO2-RTK#2-run-our-examples) 获取 HH-LVGO-01。下例使用本地验证过的压缩图像版本。程序根据 Bag 中的连接类型选择原始或压缩图像话题。

```bash
./run.sh --bag /path/to/HH-LVGO-01_compressed.bag --profile profiles/hh-lvgo --run-dir runs/my-hh-run
```

`--run-dir` 指定一个尚未创建的目录。省略时会在 `runs/` 自动新建结果目录。中断后，用同一 Bag 和结果目录加 `--resume`，继续执行未完成的阶段。重试阶段会先将已有的部分产物移到 `attempts/`。

```bash
./run.sh --bag /path/to/HH-LVGO-01_compressed.bag --run-dir runs/my-hh-run --resume
```

同设备、同标定和同话题的新 Bag 可沿用设备配置。适配其他设备时复制 [profiles/hh-lvgo](profiles/hh-lvgo/) 并填写对应的传感器话题、相机内外参、时间偏移和采样参数。当前前端支持已适配的 Livox CustomMsg 和 PointCloud2 输入，IMU 使用 `sensor_msgs/Imu`，离线 RTK 使用 `gnss_comm/GnssPVTSolnMsg`。完整 RTK 优化需要有效、时间上有重叠的 GNSS 观测。HH 是目前用于端到端验收的设备配置。

## 4. 数据流和输出

| 步骤 | 输入 | 输出目录中的主要产物 |
| --- | --- | --- |
| FAST-LIVO2 | Bag 中的相机、LiDAR、IMU | `raw/all_image/` 和 `raw/all_pcd_body/` 中的逐帧数据和机体位姿 |
| 离线 RTK | LIVO 里程计、同步彩色点云及 GNSS 位置观测 | `frontend/TUM/enu_imu_after_rtk.txt`、`frontend/global_pcd/after_optimization.pcd`，以及供后端使用的 `datasets/input/` |
| Global-LVBA | RTK 修正后的位姿、图像、点云、标定和 COLMAP 特征匹配数据库 | `datasets/input/3DGS_V6/` 中的图像、相机位姿和彩色点云。LiDAR BA 前后点云由对应扫描位姿拼接到 `maps/` |
| 3DGS | 由 `3DGS_V6` 整理的 `datasets/input/3DGS_train/` | `3dgs/point_cloud/iteration_15000/point_cloud.ply` 和渲染图。迭代次数可在设备配置中调整 |

`results.json` 汇总模型、轨迹、地图、渲染指标和 Visual BA 结果。若候选位姿触发保护，后端采用 LiDAR BA 初始化的相机位姿，运行记录会标明该状态。测试照片留出于 3DGS 训练，前面的 BA 和点云着色可使用这些图像。

在 WSLg 环境可查看 LiDAR 地图预览。训练完成的高斯 PLY 可用 [SuperSplat](https://superspl.at/editor) 打开。

```bash
./view-map.sh runs/my-hh-run rtk
./view-map.sh runs/my-hh-run ba
```

Bag、数据集、训练结果及本机缓存保留在本地。上游代码在构建时下载。

## 5. HH-LVGO-01 验收

本次从 Bag 重新执行了全部阶段。离线 RTK 输出 2,736 个关键帧位姿，Global-LVBA 使用 1,368 帧 LiDAR 扫描和 342 张照片，本次 Visual BA 候选解已采纳。3DGS 训练 15,000 步后得到 438,544 个高斯，并生成 299 张训练视角渲染和 43 张留出视角渲染。留出视角平均 PSNR 为 18.63 dB。

三份地图预览已通过 ROS 点云发布和读回验证。此次 LiDAR BA 有局部轨迹跳变，最大扫描位置变化为 9.07 m。前后轨迹、点云对照和变化统计随本地运行结果保存，便于复核异常路段。

## 6. 上游项目与引用

| 组件 | 作者及项目 |
| --- | --- |
| FAST-LIVO2 与 RTK | Chunran Zheng 等人的 [FAST-LIVO2](https://github.com/hku-mars/FAST-LIVO2) 和 [FAST-LIVO2-RTK](https://github.com/xuankuzcr/FAST-LIVO2-RTK)，本项目集成带数据导出的 [WilsonGuo（Gunda）版 FAST-LIVO2-RTK](https://github.com/WilsonGuo/FAST-LIVO2-RTK) |
| Global-LVBA | Chunran Zheng 等人的 [Global-LVBA](https://github.com/xuankuzcr/Global-LVBA)，本项目集成带 3DGS 导出的 [WilsonGuo（Gunda）版 Global-LVBA](https://github.com/WilsonGuo/Global-LVBA) |
| 3D Gaussian Splatting | Bernhard Kerbl、Georgios Kopanas、Thomas Leimkühler 和 George Drettakis 的 [官方实现](https://github.com/graphdeco-inria/gaussian-splatting) 与 [论文主页](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) |

本项目的集成改动包括前端位姿导出、点云拼接参考点统一、3DGS PLY 写出内存优化，以及运行、数据转换和结果检查脚本。上游源码按各自许可证使用。随仓库分发的补丁许可证位于 [licenses/](licenses/)。官方 3DGS 的非商业使用及再分发条件见 [Gaussian-Splatting License](https://github.com/graphdeco-inria/gaussian-splatting/blob/54c035f7834b564019656c3e3fcc3646292f727d/LICENSE.md)。
