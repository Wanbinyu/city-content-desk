# 城市内容台：GitHub 参考项目

整理日期：2026-10-16  
用途：后续学习和评估，不代表现在要修改城市内容台。

> GitHub 星标数和项目状态会变化。下方星标数为整理时页面显示的大致数量。

## 项目清单

### 1. f2：多平台内容数据接口

- 仓库：[Johnserf-Seed/f2](https://github.com/Johnserf-Seed/f2)
- 主要用途：提供抖音、TikTok、微博等平台的作品下载和接口数据处理能力。
- 可参考：采集适配器、命令行设计、数据解析和平台差异处理。
- 许可证：Apache-2.0；约 2.7k stars。
- 注意：仓库默认展示开发分支，README 提醒开发分支可能尚未发布到 PyPI；使用前应核对当前分支、文档和版本。

### 2. social-auto-upload：多平台视频发布

- 仓库：[dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)
- 主要用途：把视频发布到抖音、Bilibili、小红书、快手、视频号、YouTube 等平台。
- 可参考：平台上传器的拆分方式、命令行流程、账号配置和发布状态处理。
- 许可证：MIT；约 15.5k stars。
- 注意：项目 README 提到正在进行重构，当前主线侧重 CLI；Web 端代码不保证与主线同步。

### 3. CapCap：短视频本地化和剪辑

- 仓库：[notepower2k1/CapCap](https://github.com/notepower2k1/CapCap)
- 主要用途：把语音识别、翻译、配音、字幕时间线和视频导出整合在一个工作流中，支持竖屏视频。
- 可参考：视频生成和预览流程、字幕编辑体验、音视频分层及 9:16 导出。
- 许可证：Apache-2.0；约 348 stars。整理时仓库近期仍有更新。
- 注意：这是 Windows 桌面应用，技术形态与城市内容台的网页服务不同，适合参考具体功能和交互。

### 4. n8n-automated-video-creator：自动化视频工作流示例

- 仓库：[sashakayukov23/n8n-automated-video-creator](https://github.com/sashakayukov23/n8n-automated-video-creator)
- 主要用途：从一个故事想法生成分镜、图片、短片、配音、字幕和音乐提示词。
- 可参考：如何把 AI 生成步骤拆成可组合的工作流节点。
- 项目规模：约 9 stars、4 次提交；定位是流程示例，README 将最终剪辑和平台发布列为后续可扩展步骤。
- 注意：适合学习编排思路，不宜仅凭示例仓库判断生产环境的可靠性。

## 与城市内容台的模块对应

| 城市内容台的环节 | 可先看的项目 |
| --- | --- |
| 抖音内容读取和数据解析 | [f2](https://github.com/Johnserf-Seed/f2) |
| 表格整理、城市替换和内容工作流 | 城市内容台自身的实现 |
| 竖屏视频、字幕和配音处理 | [CapCap](https://github.com/notepower2k1/CapCap) |
| 多平台上传和发布流程 | [social-auto-upload](https://github.com/dreammis/social-auto-upload) |
| AI 步骤的流程编排 | [n8n-automated-video-creator](https://github.com/sashakayukov23/n8n-automated-video-creator) |

## 建议的阅读顺序

1. 先看 CapCap 的视频工作流，了解字幕、配音和竖屏导出的实现方式。
2. 再看 f2 和 social-auto-upload，分别了解内容读取与平台发布。
3. 最后看 n8n 示例，参考如何组织多个生成步骤。

## 后续评估记录

| 日期 | 项目 | 想借鉴的功能 | 评估结果 / 备注 |
| --- | --- | --- | --- |
|  |  |  |  |
