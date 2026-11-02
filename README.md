# LIA · Circuit Studio

本地运行的 Virtuoso 电路学习与分析工具。通过 SSH 桥接读取真实原理图，在独立网页窗口中查看电路、理解功能，并与 AI 讨论设计。

Based on [virtuoso-bridge-lite](https://github.com/Arcadia-1/virtuoso-bridge-lite), LIA reads Cadence Virtuoso schematics and helps users explore circuit structures. Current preview: **0.4**.

## 功能

- 同步当前 Virtuoso 会话及已发现的 `cds.lib`，浏览库与 schematic 单元。
- 读取真实器件、CDF、已存储参数、端子网络和原生符号几何，保留布局、旋转、镜像、导线及连接点。
- 根据实际连接生成中文功能判断、分区讲解和器件高亮；讨论中的修正可同步到讲解，保留版本并支持恢复。
- 框选、多选器件；按 **Only current / All selected / All** 修改兼容参数，显示操作范围与混合数值，支持撤销和重做。
- 为教学二级运放提供真实 Spectre AC、DC、闭环阶跃实验，展示曲线、基准和实验历史。
- 本地服务仅监听 `127.0.0.1:8765`；Windows 支持双击启动与创建桌面图标。

## 环境

- Windows 10/11、Python 3.10+、Git；前端无构建依赖，无需 Node 即可运行应用。
- 可通过 SSH 访问的 Linux 主机、合法可用的 Cadence Virtuoso / Spectre 环境与许可证。已在 CentOS 7、Virtuoso IC6.1.8 环境验证。
- 本机已安装并登录的 Codex CLI，用于生成讲解和对话；也可用 `CIRCUIT_CODEX_EXE` 指定可执行文件。AI 调用会发送当前电路上下文，并使用当前账号用量。

## 首次安装

```powershell
git clone https://github.com/amerysain-IC/LIA.git
cd LIA
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1
```

安装脚本创建项目自己的 `.venv`，安装 [requirements.txt](requirements.txt) 中固定版本的桥接依赖。需要访问 GitHub，不会复制本机现有的虚拟环境。

### 配置桥接

先确保 SSH 密钥登录可用。按照[上游连接说明](https://github.com/Arcadia-1/virtuoso-bridge-lite/blob/17883ca35d14df108f46ebeb5c2ea9d70ee08acf/skills/virtuoso/references/connection.md)初始化桥接，将生成的环境配置保存在本项目的 `bridge.env`，或通过环境变量指定现有配置：

```powershell
# 在项目目录执行；替换为实际远端账号和主机。
.\.venv\Scripts\virtuoso-bridge.exe init your-user@your-vm-host
# 将初始化生成的完整 .env 复制为 bridge.env，或设置：
$env:CIRCUIT_BRIDGE_ENV = 'C:\your-private-config\bridge.env'
.\.venv\Scripts\virtuoso-bridge.exe start --env $env:CIRCUIT_BRIDGE_ENV
```

`bridge.env.example` 提供字段说明，但完整初始化配置优先。按上游工具输出的准确指令，在指定的 Virtuoso CIW 加载桥接，再验证：

```powershell
.\.venv\Scripts\virtuoso-bridge.exe eval '1+2' --env $env:CIRCUIT_BRIDGE_ENV
```

仓库中的 `Start-Bridge.ps1` 使用标准桥接启动流程，不会自动寻找或启动 Virtuoso 图形会话。如果实验室已有专用启动脚本，可设置 `CIRCUIT_BRIDGE_LAUNCHER` 指向它；脚本应建立或复用指定桥接，完成后退出。账号、私钥、认证缓存和站点启动脚本应在本地管理。

### 打开界面

双击 `Launch.cmd`，或运行 `Start.ps1`。也可在浏览器访问 <http://127.0.0.1:8765>。

```powershell
# 创建桌面快捷方式（可选）
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Shortcut.ps1
```

Windows 启动器优先使用本项目 `.venv`；`CIRCUIT_PYTHON_EXE` 可指定其他 Python 环境。保留旧工作区相邻 `virtuoso-bridge-lite/.venv` 的兼容回退。

服务校验 Host、Origin 和页面会话令牌。关闭窗口不会停止服务或关闭 Virtuoso。停止后台前，核对 `runtime/server.pid` 对应进程的命令行确实是本项目 `server.py`，再停止该进程。

## 示例与边界

- `setup_teaching.py` 创建独立的 `CircuitTutorLab/two_stage_opamp`：8 个 MOS、参考电流源、补偿与负载电容。使用显式的通用 MOS Level-1 模型，不代表任何商业工艺。脚本会检查既有目标，拒绝覆盖拓扑不同的同名单元。
- [image_001](cases/image_001/README.md) 是 52 器件、35 网络的图片转录回归用例，包含连续布线和连接检查。半导体模型与面积比未知，不能直接仿真或据此声明性能。
- 自动仿真仅对已校验的教学运放开放；其他原理图需要单独配置模型与测试平台。
- 参数修改保存在草稿和独立仿真实验中，不回写原始 Virtuoso 原理图；不提供拓扑编辑。
- 旧 CDB 单元会提示转换要求，不自动修改原库；不自动展开复杂子电路。库同步不是对全部磁盘的无限扫描。
- 原生读取忠实保留源图：若原图通过同名网络标签连接，界面也会显示标签，不凭空补画跨区导线。
- AI 结论属于辅助解释，需结合实际连接、模型与仿真核实。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
# 可选：安装 Node 后验证前端纯函数和语法
node --check web/app.js
node tests/native_geometry.cjs
node tests/device_edit.cjs
node tests/image_wires.cjs
```

发布包不附带私有运行目录、PDK、原生库符号绘图、第三方来源图片和本机截图。因此依赖实机回读文件的检查会明确跳过；连接合法的 Cadence 环境并重新生成测试用例后可执行完整检查。离线通过不代表对任意 PDK 的实机验证。见 [VALIDATION.md](VALIDATION.md)。

## 依赖与许可

本项目沿用仓库已有的 [MIT License](LICENSE)。桥接依赖固定为上游提交 `17883ca35d14df108f46ebeb5c2ea9d70ee08acf`，来源和 MIT 声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。Cadence 软件、PDK、第三方图片及外部模型不属于本项目发行内容，也不因本项目许可获得授权。
