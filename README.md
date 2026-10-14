# 城市内容台

抖音城市选题的本地 MVP。一条热帖走完四步：导入、拆解、复刻稿、人审后的发布包。

打开页面不会发布任何内容。上传命令默认只写进发布包，不执行。

## 运行

需要 Python 3.11。

```bat
启动.bat
```

或：

```bat
python app.py
```

浏览器打开 http://127.0.0.1:8765 。第一次会放进 3 条标了「演示」的假数据，用来把流程点通。演示数据不是抖音上的真实帖子。

## 怎么用

1. 工作台选一条热帖。口播可以直接改，然后点「拆解」。
2. 「生成复刻稿」会按同一结构写一条新口播，不照搬原片原句。
3. 改完点「通过」。稿里如果还有「无痛」「保证」「最好」这类词，通过会被拦住。
4. 「生成发布包」在 `data/publish/` 下写出标题、口播、分镜和 `command.txt`。
5. 成片是自己的素材，并且本机已经装好 `sau` 时，才用「确认并上传」。

真实热帖从「导入」贴进去。三种格式都可以：

- 带表头的 CSV：`标题,点赞,评论,分享,链接,关键词,口播,作者`
- MediaCrawler 导出的 JSON，字段如 `aweme_id`、`liked_count`、`aweme_url`、`source_keyword`
- 一行一个抖音链接

示例文件在 `examples/import.sample.json`。

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
- 机构卖点里一旦有风险词，整段卖点不会写进口播。
- API key 和 cookie 只写在本机 `data/settings.json`，页面回显会打码。
- 医疗广告需要人工核对。这个工具不代替审查。

## 测试

```bat
python -m unittest discover -s tests -v
```
