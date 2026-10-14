# 城市内容台

把一条抖音表格视频换成另一个城市。导入链接和原标题，选择目标城市，用你的表格、本地排名文件或模型整理出同一版式，然后得到页面、竖屏视频和视频文案。

脚本和模型都不会编造机构排名。没有 `data/ranks/城市-选题.csv` 时，只有自带的示例表，页面会标明不是真实排名。

## 运行

需要 Python 3.11。

```bat
启动.bat
```

或：

```bat
python app.py
```

浏览器打开 http://127.0.0.1:8765 。

## 怎么用

1. 贴上抖音链接和原视频标题。链接只作记录，不会下载原片。
2. 目标城市可以选，也可以自己填，例如青岛。原城市不在常见名单里时，填上原城市，标题和单元格里的这个地名会换成目标城市。
3. 选数据来源。
   - 我提供表格：CSV、制表符、中文逗号，或「1、机构：说明」都可以。图片列可以填本机路径，或一张公网图片地址。
   - 脚本读取排名文件：把真实排名存成 `data/ranks/城市-选题.csv`。UTF-8 和 Excel 的 GBK 都能读。没有这份文件时，只有武汉双眼皮会用示例表。
   - 接入模型整理：已经是表格的内容直接用。只有认不出表格的文字才会交给模型，模型不补机构。
4. 补充说明里可以写「把示例机构甲改成某某」，一行一条。
5. 先点「只整理表格」改单元格，再点「生成页面和视频」。右边出现表格页面、竖屏视频和视频文案。文案可以改完再生成一次。

示例排名在 `examples/ranks/武汉-双眼皮.csv`，里面的机构是示例，不是真实排名。

## 用到的开源项目

| 环节 | 项目 | 许可证 | 在这里怎么用 |
| --- | --- | --- | --- |
| 单条作品文案 | [Johnserf-Seed/f2](https://github.com/Johnserf-Seed/f2) | Apache-2.0 | 工作台按钮调用 `f2 douyin -u 链接 -M one`，再读它写出的 `*_desc.txt` |
| 确认后上传 | [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) | MIT | 发布包里的命令是 `sau douyin upload-video` |

可选安装：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

`f2` 会装到当前 Python。`social-auto-upload` 克隆到 `third_party/`，还要按它自己的 README 装依赖、登录创作者中心，并保证命令行里能运行 `sau`。这两个目录不进 git。

没有把 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 放进这个仓库。它的许可证写明不得用于商业用途，而这套流程是给机构用的。已经用它导出的 JSON 仍然可以导入。

## 边界

- 复刻的是结构，不是别人的画面、人脸或声音。
- 规则改写不承诺效果。大模型地址留空时，只用规则稿。
- 无痛、保证、最好这类说法会标出来，不会拦下生成。
- API key 和 cookie 只写在本机 `data/settings.json`，页面回显会打码。
- 医疗广告需要人工核对。这个工具不代替审查。

## 测试

```bat
python -m unittest discover -s tests -v
```
