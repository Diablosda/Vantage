# Vantage

Windows 本机三维预演工作台，支持导入场景与模型、安排人物路径、绑定动作、编辑镜头并导出视频。

请阅读 [产品说明](产品说明.md)，了解安装、启动、操作和功能边界。双击 `Vantage.exe` 启动；运行需要另行安装 Blender 5.2.2 与 FFmpeg。

本仓库不包含个人工程、场景、角色、动作或第三方 Blender / FFmpeg 二进制文件。网页 Three.js 运行文件及其许可证位于 `web/vendor/three`。

## 开发进度

当前版本 2.0.6：产品统一命名 Vantage，启动程序、网页标签及品牌栏正式采用深色青绿相机眼睛图标。保留现有工程格式与草稿兼容性。

Windows 下可运行 `launcher/build.cmd` 重建带图标的启动器；用 `python build.py` 生成产品包。运行时只需 Blender 自带 Python，无需 Node.js。

已验证启动器编译、启动环境检查及图标资源结构，58 项前端测试和 35 项 Python 测试通过。浏览器内视觉效果仍需实际使用验收。
