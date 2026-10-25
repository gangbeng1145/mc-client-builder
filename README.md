# MC 客户端构建器

## 访问地址

| 线路 | 地址 |
|---|---|
| 主力 | <https://dlmc.gber.dpdns.org/> |
| 备用 1 | <https://mc-client-builder.pages.dev/> |
| 备用 2 | <https://gangbeng1145.github.io/mc-client-builder/> |

> 一个不依赖启动器的 Minecraft 客户端下载 / 配置 / 打包工具。
> 选好版本和加载器，自动下载原版、依赖库、资源文件，调用官方安装器装好 Forge / OptiFine / Fabric / Quilt，最后打包成一个可以直接被 HMCL 启动的 zip。

![界面截图](docs/screenshot.png)

## 功能

- **全量版本**：正式版、快照、远古 Alpha / Beta（约 900+ 个版本）
- **原版安装**：version JSON、client jar、libraries、assets、logging 全套
- **加载器**
  - Forge：调用官方 installer 的 `--installClient`，1.12.2 和新版本都支持
  - OptiFine：调用官方 `optifine.Patcher` 生成补丁库
  - Fabric / Quilt：读取官方 meta 直接生成版本 JSON
- **安装 Java**：Mojang 官方运行时（8 / 16 / 17 / 21 / 25），装好自动加入列表
- **下载源**：自动（国内优先 BMCLAPI）/ 仅 BMCLAPI / 仅 Mojang 官方，失败自动换源
- **下载线程**：4 / 8 / 16 / 24 / 32 可选，默认 32
- **完整性**：SHA-1 校验、按哈希缓存、原子写入、可取消
- **离线兜底**：内置版本清单，清单接口不可用时仍能显示版本列表
- **网络诊断**：DNS / TCP / HTTPS / 代理 / 系统时间一键检查

## 系统要求

- Windows 10 / 11 **64 位**
- 源码运行需要 Python 3.10+（推荐 3.12）
- 本机已安装 Java（工具可以帮你装）
- 磁盘空间：建议预留 5 GB 以上

## 快速开始

### 方式一：下载 exe

到 [Releases](../../releases) 下载 `MC-Client-Builder_vX.Y_Win64.zip`，解压后双击 `MC客户端构建器.exe`。

> 单文件 exe 首次启动需要解压，约 5–10 秒；个别杀毒软件可能误报，加信任即可。

### 方式二：源码运行

```bat
git clone https://github.com/gangbeng1145/mc-client-builder.git
cd mc-client-builder
run.bat
```

首次运行会自动创建 `.venv` 并安装依赖。

## 使用步骤

### 1. 启动

双击 `MC客户端构建器.exe`，或源码运行 `run.bat`。
窗口加载后会从 BMCLAPI / Mojang 拉取版本清单；如果清单接口不可用，会自动读取内置的离线清单（920 个版本）。

### 2. 选 Minecraft 版本

左侧列表支持：

- 搜索：输入 `1.20`、`1.12.2`、`26.3` 等关键词
- 筛选：全部 / 正式版 / 快照 / 远古（Alpha、Beta）

### 3. 选加载器

右侧「加载器」下拉：

| 选项 | 说明 |
|---|---|
| 原版 | 不装加载器，纯净客户端 |
| Forge | 选具体 Forge 版本，工具调用官方 installer 安装 |
| OptiFine | 选具体 OptiFine 版本（`HD_U_xxx`） |
| Fabric / Quilt | 选 loader 版本，读取官方 meta 生成 |

> Forge 1.13+ 不能叠加 OptiFine，工具会明确报错。

### 4. 选 Java

工具会自动扫描本机 Java。没有合适的版本就点「安装 Java」：

- 支持 Java 8 / 16 / 17 / 21 / 25（Mojang 官方运行时）
- 安装到 `构建目录\java\<组件>-<版本>`
- 装完自动加入下拉框并选中

### 5. 选目录

- **构建目录**：存放 `versions / libraries / assets` 等中间文件
- **输出目录**：最终 `<实例名>.zip` 放这里

默认都在用户目录下（`%USERPROFILE%\MC_Downloader_Work` / `MC_Downloader_Out`）。

### 6. 开始构建

点「开始构建」，底部会显示：

- 当前阶段（版本 JSON → client jar → 资源 → 依赖库 → 加载器 → 打包）
- 文件进度条
- 实时日志（失败会写明是哪个 URL、什么问题）

构建过程中可以「取消」。

### 7. 使用成品

到输出目录取 `<实例名>.zip`，解压后是一个完整游戏目录：

```
<实例名>/
├─ versions/          版本 JSON + client jar
├─ libraries/         全部依赖库
├─ assets/            游戏资源
├─ launcher_profiles.json
└─ 使用说明.txt
```

在 HMCL 里两种用法：

- **推荐**：把解压出的文件夹整个作为 HMCL 的游戏目录（设置 → 游戏目录）
- 或者把 `versions`、`libraries`、`assets` 三个目录一起合并进现有 `.minecraft`

> `libraries` 和 `assets` 必须一起带，只复制 `versions` 会缺文件。

## 工作原理

```
版本清单 (manifest)
      │
      ▼
版本 JSON (version.json)
      │
      ├─ downloads.client ──────────► versions/<id>/<id>.jar
      ├─ libraries[] ───────────────► libraries/<maven 路径>
      ├─ assetIndex ────────────────► assets/indexes/<id>.json
      │                               └─ objects ─► assets/objects/<xx>/<hash>
      └─ logging ───────────────────► assets/log_configs/<id>
      │
      ▼
加载器安装
      ├─ Forge: 下载 installer → --installClient → 官方 processor 生成子版本
      ├─ OptiFine: 下载 installer → optifine.Patcher → 补丁库 + launchwrapper
      ├─ Fabric / Quilt: 读 meta → 生成 profile JSON + 依赖
      │
      ▼
写入版本 JSON（官方 launcher 规范，inheritsFrom 继承链）
      │
      ▼
打包 zip（jar/ogg 等已压缩文件直接 store，JSON 等 deflate）
```

几个关键点：

1. **版本清单**：优先 BMCLAPI，失败换 piston-meta / launchermeta，再失败用内置 `assets/fallback/version_manifest.json`。
2. **依赖解析**：把 `group:artifact:version[:classifier]` 转成 Maven 目录，处理 `rules`（操作系统 / 架构）、`natives`、`classifier`。
3. **完整性**：每个文件带 SHA-1，下载到临时文件 → 校验 → 原子替换；缓存按 hash 存，命中直接硬链接。
4. **加载器隔离**：子版本用 `inheritsFrom` 指向原版，只写增量字段（`mainClass`、`arguments`、`libraries`），符合 Mojang 启动规范，HMCL / 官方启动器都能识别。
5. **并发**：`ThreadPoolExecutor` 默认 32 线程；大文件（如 Java 的 `lib/modules`、Forge installer）单独串行，避免和几百个小文件抢线程池。
6. **多源回退**：同一个文件有多个候选 URL（镜像 + 官方），失败自动换下一个，每个 URL 重试 3 次。

## 命令行

```bat
python cli.py --mc 1.20.1 --loader forge --loader-version 47.2.5 --threads 32
python cli.py --install-java java-runtime-beta
python verify.py <游戏目录> <版本id>
```

- `--mc` 版本号，`--loader` 取 `none/forge/optifine/fabric/quilt`
- `--work` / `--out` 构建目录与输出目录
- `--no-assets` 跳过资源下载（调试用）
- `--install-java` 只安装 Java 运行时
- `verify.py` 检查继承链、依赖库、资源是否齐全

## 项目结构

```
├─ app.py               GUI 入口
├─ cli.py               命令行
├─ verify.py            结构校验器
├─ make_icon.py         生成图标
├─ core/
│  ├─ net.py            下载器（多源、并发、SHA-1、缓存）
│  ├─ manifest.py       版本清单（在线 + 离线兜底）
│  ├─ vanilla.py        原版安装
│  ├─ loaders/          Forge / OptiFine / Fabric / Quilt
│  ├─ java_install.py   安装 Java 运行时
│  ├─ netdiag.py        网络诊断
│  ├─ installer.py      安装编排
│  └─ pack.py           打包 zip
├─ ui/                  PySide6 界面
└─ assets/              图标 + 离线版本清单
```

## 从源码构建 exe

```bat
build_exe.bat
```

等价于：

```bat
python -m PyInstaller --onefile --windowed --name "MC客户端构建器" ^
  --icon assets\icon.ico --add-data "assets;assets" app.py
```

## 数据来源

| 内容 | 地址 |
|---|---|
| 版本清单 | BMCLAPI / `piston-meta.mojang.com` / `launchermeta.mojang.com` |
| 游戏资源 | `resources.download.minecraft.net`（镜像 `/assets`） |
| 依赖库 | `libraries.minecraft.net`、Forge / Fabric / Quilt Maven |
| Forge 列表 | `bmclapi2.bangbang93.com/forge/minecraft/<mc>` |
| OptiFine 列表 | `bmclapi2.bangbang93.com/optifine/versionlist` |
| Fabric / Quilt | `meta.fabricmc.net` / `meta.quiltmc.org` |
| Java 运行时 | `piston-meta.mojang.com/v1/products/java-runtime/...` |

所有文件下载后都会做 SHA-1 校验。

## 学习目标

这个项目最初是练手，适合用来学习：

1. **HTTP 客户端工程化**
   - 连接池、并发、超时、重试、指数退避
   - 多源镜像与自动回退
   - 流式下载 + 边下边算 SHA-1 + 原子写入
2. **Maven 坐标与依赖解析**
   - `group:artifact:version:classifier@ext` 转路径
   - `rules`（os / arch / features）过滤、natives 分类器
3. **Minecraft 启动规范**
   - version JSON 字段、`inheritsFrom` 继承链、`arguments` 合并
   - assets 索引与 objects 寻址、旧版本 virtual 映射
4. **加载器安装机制**
   - Forge installer 的 `install_profile.json` 与 processors
   - OptiFine 的 `Patcher`、launchwrapper、tweakClass
   - Fabric / Quilt meta 与 profile JSON
5. **Java 运行时管理**
   - Mojang java-runtime 清单、按相对路径落盘、大文件下载策略
6. **桌面 GUI**
   - PySide6 线程 / 信号槽、进度上报、无边框窗口、QSS 主题
7. **发布工程**
   - PyInstaller 单文件打包、GitHub Release、GitHub Pages

## 已知限制

- 仅支持 Windows 10 / 11 64 位
- Forge 1.13+ 不能叠加 OptiFine（启动器机制冲突），工具会明确报错
- 未内置 NeoForge（下载源在部分网络环境不可达）
- 首次全量构建约 3–5 分钟，资源包 zip 可能 600 MB+

## 许可证与 HMCL 的关系

本项目采用 **[MIT](LICENSE)**。

项目在开发时研究过 [HMCL](https://github.com/HMCL-dev/HMCL) 的公开下载流程和 Minecraft 启动规范，但：

- **没有复制或包含 HMCL 的任何源代码或二进制文件**；
- 只参考了公开可观察的行为（下载哪些文件、如何组织版本 JSON）以及 Mojang 官方启动规范；
- 因此本项目是独立实现，不是 HMCL 的衍生作品，可以继续使用 MIT。

HMCL 本身采用 **GNU GPL v3.0**（[许可证全文](https://github.com/HMCL-dev/HMCL?tab=GPL-3.0-1-ov-file#)）。这里把与分发有关的义务说清楚：

1. **分发 HMCL 或其修改版时**，必须遵守 GPL-3.0：
   - 随附完整的对应源代码（GPLv3 §5 / §6）；
   - 保留版权声明和许可证文本；
   - 不得附加额外限制（GPLv3 §10）。
2. **以二进制形式分发**（例如把 HMCL 打包进整合包）时，GPLv3 §6 要求同时提供对应源码，或提供书面报价按成本价提供源码。
3. **把本项目与 HMCL 一起分发**时，两者分别适用 MIT 与 GPL-3.0：
   - 本项目（独立进程、独立文件）通常不构成 HMCL 的衍生作品；
   - 但 HMCL 部分仍必须满足 GPL-3.0 的全部分发义务；
   - 如果修改了 HMCL 的代码再分发，修改后的 HMCL 也必须以 GPL-3.0 开源。
4. 本项目与 HMCL 官方**没有任何隶属或背书关系**。

> 以上是开发者的理解，不构成法律意见；涉及商业分发请咨询律师。

## 免责声明

- 本项目是非官方的第三方工具，与 Mojang / Microsoft 无关。
- 工具只下载**公开的客户端文件**，不包含、不分发游戏本体。
- Minecraft 及相关素材版权归 Mojang Studios 所有，使用时请遵守 Minecraft 最终用户许可协议（EULA）。
- 请勿将本工具用于商业用途或违反当地法律法规的用途。

## License

[MIT](LICENSE) © 2026 gangbeng1145
