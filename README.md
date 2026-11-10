# Vantage

Windows x64 本机三维镜头预演工具，支持场景/模型导入、人物路径和分段镜头、焦点选择及 MP4 导出。运行时不连接云端，不需要账号。

## 安装与运行

普通用户使用 [Release](https://github.com/Diablosda/Camera-Control/releases/tag/v2.1.2) 中的 `Vantage-2.1.2-Setup.exe` 离线安装包。包内包含 Blender 5.2.2（及其 Python）、FFmpeg 7.1 和前端运行文件，不需分别安装 Python、Node.js、Blender 或 FFmpeg。默认按当前 Windows 用户安装，无需管理员权限；安装后通过快捷方式启动 Vantage，界面在本机浏览器打开。系统和显卡需满足 Blender 及 WebGL 要求。

源码仓库不包含大体积运行组件及个人素材。源码方式可将 Blender 放在同级 `blender/blender-5.2.2-windows-x64/`，或设置 `PREVIS_BLENDER`；FFmpeg 用 `PREVIS_FFMPEG` 指定。源码和安装版均可优先使用程序内 `runtime/blender`、`runtime/ffmpeg` 组件。

## 数据与升级

- 程序文件：安装目录，运行期间不写入模型、工程或缓存。
- 用户资源和默认工程：`%LOCALAPPDATA%/Vantage/Data`，其中 `model`、`场景`、`动作` 存放导入资源，`Projects` 存放默认工程。
- 工作缓存：`%LOCALAPPDATA%/Vantage/Cache` 及系统临时目录。
- 可用 `VANTAGE_DATA_DIR`、`VANTAGE_CACHE_DIR` 指定其他位置，适用于测试与自定义部署。
- 在旧源码目录直接更新时，旧资源提供只读兼容查找；安装到其他位置时，请用旧版保存的完整 `.previs.zip` 工程包加载迁移。旧文件不会被自动移动或删除。
- 升级/卸载会先停止同一安装目录的空闲后台，有任务正在运行时要求先结束任务。卸载只删除安装清单中的程序文件，保留用户数据、导出文件及额外放入安装目录的自有文件。

## 开发与构建

`launcher/build.cmd` 重建启动器和 Windows 原生保存窗口；`python build.py` 构建源码包。测试：`node --test tests/*.test.mjs` 与 `python -B -m unittest discover -s tests -p "test*.py"`。浏览器集成测试额外需要开发者提供 Playwright 和浏览器，用户运行软件不需要这些依赖。测试默认隔离用户数据。

离线安装包构建：按 `packaging/components.json` 下载和校验组件，干净解压到发布工作目录后执行 `python packaging/build_installer.py --work <工作目录>`；NSIS 编译器来自该工作目录。组件不得从带个人配置的现有 Blender 目录复制。大组件和发布工作目录不纳入 Git。

具体操作和功能边界见 [产品说明](产品说明.md)，组件许可及对应源码信息见 [THIRD_PARTY](THIRD_PARTY.md)。仓库保持私有，本次部署更新不改变 Vantage 自身授权方式。

## 开发进度与验证范围

2.1.1 完整功能已单独同步；2.1.2 增加安装内置引擎定位、程序/用户数据/缓存分离、旧资源兼容和安全卸载。顶部导出全部已设镜头，右侧导出当前视频；视频只输出 MP4，工程另行保存。

安装与导出验收结果随 Release 记录。相同 Windows 主机的隔离安装测试不能替代全新电脑/虚拟机验收；原生保存窗口的真实桌面点击此前受 Computer Use 审批超时限制，不将接口替身测试当作已完成的系统窗口验收。
