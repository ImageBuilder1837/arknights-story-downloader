# arknights-story-downloader

一个从 [PRTS](https://prts.wiki/w/首页) 下载明日方舟剧情（包括主线剧情、活动剧情、干员密录与干员资料）的 python 爬虫脚本。

## 特殊词汇

- 活动剧情：包括 SideStory（插曲与别传）、集成战略、生息演算与其他特殊活动剧情。
- 干员资料：包括干员档案、语音记录与模组文案。

## 部署

安装依赖库：

```bash
$ pip install -r requirements.txt
```

## 使用

运行脚本：

```bash
$ python arknights-story-downloader.py
加载中……

选择需要下载的剧情类型：
1：主线剧情
2：活动剧情
3：干员密录
4：干员资料
5：开始下载
6：退出程序
请输入选项对应的数字：1  # 输入 1 ~ 4 可进入对应剧情类型选择界面

选择需要下载的主线剧情：
（输入 ls 查看所有可选择的主线剧情，输入 all 选择或取消选择所有可选择的主线剧情，空输入回到主选择界面）
请输入需要选择或取消选择的主线剧情（用全角逗号'，'隔开）：ls  # 输入 ls 可查看当前剧情类型所有可选项

所有可选择的主线剧情：特殊，黑暗时代·上，黑暗时代·下，异卵同生，二次呼吸，急性衰竭，靶向药物，局部坏死，苦难摇篮，怒号光明，风暴瞭望，破碎日冕，淬火尘霾，惊霆无声，恶兆湍流，慈悲灯塔

选择需要下载的主线剧情：
（输入 ls 查看所有可选择的主线剧情，输入 all 选择或取消选择所有可选择的主线剧情，空输入回到主选择界面）
请输入需要选择或取消选择的主线剧情（用全角逗号'，'隔开）：黑暗时代·上，黑暗时代·下，异卵同生，二次呼吸，急性衰竭，靶向药物，局部坏死，苦难摇篮，怒号光明  # 输入用全角逗号分隔开的特定剧情可选择或取消选择，并返回主选择界面

已选择的主线剧情：黑暗时代·上，黑暗时代·下，异卵同生，二次呼吸，急性衰竭，靶向药物，局部坏死，苦难摇篮，怒号光明

选择需要下载的剧情类型：
1：主线剧情
2：活动剧情
3：干员密录
4：干员资料
5：开始下载
6：退出程序
请输入选项对应的数字：1

选择需要下载的主线剧情：
（输入 ls 查看所有可选择的主线剧情，输入 all 选择或取消选择所有可选择的主线剧情，空输入回到主选择界面）
请输入需要选择或取消选择的主线剧情（用全角逗号'，'隔开）：all  # 输入 all 可选择或取消选择该类型所有可选项，并返回主选择界面

已选择的主线剧情：特殊，风暴瞭望，破碎日冕，淬火尘霾，惊霆无声，恶兆湍流，慈悲灯塔

选择需要下载的剧情类型：
1：主线剧情
2：活动剧情
3：干员密录
4：干员资料
5：开始下载
6：退出程序
请输入选项对应的数字：2

选择需要下载的活动剧情：
（输入 ls 查看所有可选择的活动剧情，输入 all 选择或取消选择所有可选择的活动剧情，空输入回到主选择界面）
请输入需要选择或取消选择的活动剧情（用全角逗号'，'隔开）：  # 不输入直接回车可返回主选择界面

已选择的活动剧情：

选择需要下载的剧情类型：
1：主线剧情
2：活动剧情
3：干员密录
4：干员资料
5：开始下载
6：退出程序
请输入选项对应的数字：5  # 输入 5 可开始下载所有已选剧情，剧情将被下载到 downloads 文件夹并保存为 markdown 格式

已选择的主线剧情：特殊，风暴瞭望，破碎日冕，淬火尘霾，惊霆无声，恶兆湍流，慈悲灯塔
已选择的活动剧情：
已选择的干员密录：
已选择的干员资料：

下载任务已全部启动

下载完成：主线剧情 特殊
下载完成：主线剧情 风暴瞭望
下载完成：主线剧情 淬火尘霾
下载完成：主线剧情 恶兆湍流
下载完成：主线剧情 惊霆无声
下载完成：主线剧情 破碎日冕
下载完成：主线剧情 慈悲灯塔

下载任务已全部完成
```
