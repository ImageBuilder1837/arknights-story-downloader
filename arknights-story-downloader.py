import asyncio
import json
import os
import re
import sys
import time
import urllib.parse

import aiofiles
import aiohttp
from lxml import etree


BASE_URL = "https://prts.wiki/"
BASE_URL_W = "https://prts.wiki/w/"
DIALOG_SEP = "---"
ELITES = ["Pith", "Sharp", "Stormeye", "Touch", "郁金香"]
LINE_SEP = '\n\n'
COOKIES = {
    "ak_akToken": "",
    "ak_akUserID": "",
    "ak_akUserName": "",
    "ak_ak_session": "",
}

LINE_FEED = re.compile(r'((\\r)?\\n)+')
CONVERSATION = re.compile(r'\[name="(.*)".*\](.*)', re.I)
DECISION = re.compile(r'\[decision\(.*options="(.*)".*values="(.*)".*\)\]', re.I)
DIALOG = re.compile(r'\[dialog\]', re.I)
MULTILINE = re.compile(r'\[multiline\(name="(.*)".*\)\](.*)', re.I)
PREDICATE = re.compile(r'\[predicate\(.*references="(.*)".*\)\]', re.I)
STICKER = re.compile(r'\[sticker\(.*text="(.*?)".*\)\]', re.I)
SUBTITLE = re.compile(r'\[subtitle\(.*text="(.*?)".*\)\]', re.I)
DEMAND = re.compile(r'(\[.*\])|(\{\{.*)|(\}\})')


def extract_archive_text(operator_html) -> str:
    lines = []
    archive_span = operator_html.xpath("//*[@id='干员档案']")[0]
    archive_table = archive_span.getparent().getnext().getnext()
    tr_tags = archive_table.find('tbody').findall('tr')
    for i in range(1, len(tr_tags), 3):
        title = tr_tags[i].find('th').find('div').findtext('p').strip()
        condition = tr_tags[i + 1].find('th').findtext('small').strip()
        paragraphs = tr_tags[i + 2].find('td').find('div').itertext()
        lines.append(f"### {title}")
        lines.append(f"*{condition}*")
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:  # 部分 paragraph 为空行
                lines.append(paragraph)
    return LINE_SEP.join(lines)


def extract_module_text(operator_html) -> str:
    modules = operator_html.xpath("//h3/span[@class='mw-headline']/text()")
    if not modules:
        return "该干员暂无模组"

    lines = []
    for i in range(1, len(modules)):
        paragraphs = operator_html.xpath(
            f"//div[@id='mw-customcollapsible-module-{i+1}']/div[@id='mw-customcollapsible-module-{i+1}']/text()")
        lines.append(f"### {modules[i]}")
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:  # 部分 paragraph 为空行
                lines.append(paragraph)
    return LINE_SEP.join(lines)


def extract_voice_text(operator_html) -> str:
    titles = operator_html.xpath("//div[@id='voice-data-root']/div/@data-title")
    voices = operator_html.xpath("//div[@id='voice-data-root']/div/div[@data-kind-name='中文']/text()")

    lines = []
    for title, voice in zip(titles, voices):
        lines.append(f"### {title}")
        lines.append(voice)
    return LINE_SEP.join(lines)


def get_story_choices(kind: str, stories: dict, story_choices: list):
    while True:
        print(f"\n选择需要下载的{kind}：")
        print(f"（输入 ls 查看所有可选择的{kind}，输入 all 选择或取消选择所有可选择的{kind}，空输入回到主选择界面）")
        user_input = input(f"请输入需要选择或取消选择的{kind}（用全角逗号'，'隔开）：").strip()
        match user_input:
            case 'ls':
                print(f"\n所有可选择的{kind}：{'，'.join(stories.keys())}")
                continue
            case 'all':
                user_choices = stories.keys()
            case _:
                user_choices = user_input.split('，')
        for choice in user_choices:
            if choice in stories:
                if choice in story_choices:
                    story_choices.remove(choice)
                else:
                    story_choices.append(choice)
            elif choice:
                print(f"\n无此选项：{choice}")

        print(f"\n已选择的{kind}：{'，'.join(story_choices)}")
        break


def parse_story_code(story_code: str) -> str:
    lines = []
    codes = story_code.split("\n")
    is_multi = False
    for code in codes:
        code = re.sub(LINE_FEED, ' ', remove_html_tag(code.strip()))
        if result := MULTILINE.match(code):
            name, sentence = map(str.strip, result.groups())  # 部分 sentence 有空格前后缀
            if name and sentence:  # 部分 multiline 为空行
                if is_multi:
                    if lines and lines[-1].startswith(f"**{name}**"):
                        lines.append(lines.pop() + sentence)
                    else:
                        lines.append(f"**{name}**：{sentence}")
                else:
                    is_multi = True
                    lines.append(f"**{name}**：{sentence}")
            continue
        elif is_multi:
            is_multi = False

        if result := CONVERSATION.match(code):
            name, sentence = map(str.strip, result.groups())  # 部分 sentence 有空格前后缀
            if name and sentence:  # 部分 conversation 为空行
                lines.append(f"**{name}**：{sentence}")
        elif result := DECISION.match(code):
            lines.append('\n'.join(f"选项 {value}：{option}" for option, value in 
                                   zip(*map(lambda string: string.split(';'), result.groups()))))
        elif result := DIALOG.match(code):
            if lines and lines[-1] != DIALOG_SEP:
                lines.append(DIALOG_SEP)
        elif result := PREDICATE.match(code):
            lines.append(f"选项 {result.group(1)} 对应剧情：")
        elif result := STICKER.match(code):
            sentence = result.group(1).strip()  # 部分 sentence 有空格前后缀
            if sentence:  # 部分 sticker 为空行
                lines.append(f"**居中淡入文本**：{sentence}")
        elif result := SUBTITLE.match(code):
            sentence = result.group(1).strip()  # 部分 sentence 有空格前后缀
            if sentence:  # 部分 subtitle 为空行
                lines.append(f"**居中显示文本**：{sentence}")
        elif DEMAND.match(code) or code.startswith('//'):
            continue
        elif code:
            lines.append(code)
    return LINE_SEP.join(lines)


def remove_html_tag(string: str) -> str:
    stack, string_out = [], ""
    for char in string:
        if char == '<':
            stack.append(char)
        elif char == '>':
            stack.pop()
        elif not stack:
            string_out += char
    assert not stack
    return string_out


async def download_story(story_type: str, story: str, story_urls: dict):
    story_type_dir = os.path.join("downloads", story_type)
    if not os.path.isdir(story_type_dir):
        os.makedirs(story_type_dir)

    story_file_name = f"明日方舟{story_type}（{story}）.md"
    async with aiofiles.open(os.path.join(story_type_dir, story_file_name), 'w') as f:
        await f.write(f"# {story}{LINE_SEP}")
        if story_type == "干员资料":
            operator_html = etree.HTML(await fetch(story_urls[story]))  # type: ignore
            await f.write(f"## 干员档案{LINE_SEP}{extract_archive_text(operator_html)}{LINE_SEP}")
            await f.write(f"## 语音记录{LINE_SEP}{extract_voice_text(operator_html)}{LINE_SEP}")
            await f.write(f"## 模组文案{LINE_SEP}{extract_module_text(operator_html)}{LINE_SEP}")
        else:
            for operation in story_urls:
                operation_html = etree.HTML(await fetch(story_urls[operation]))  # type: ignore
                operation_code = operation_html.xpath("//*[@id='datas_txt']")[0].text
                await f.write(f"## {operation}{LINE_SEP}{parse_story_code(operation_code)}{LINE_SEP}")

    print(f"下载完成：{story_type} {story}")


async def fetch(url: str) -> str:
    while True:
        try:
            async with aiohttp.ClientSession(cookies=COOKIES) as session:
                async with session.get(url) as response:
                    return await response.text()
        except aiohttp.ClientError:
            if hasattr(fetch, "last_warn") and time.time() - fetch.last_warn < 10:
                continue
            fetch.last_warn = time.time()
            print("网络连接出现问题，正在尝试重新连接……")


async def get_operators() -> dict:
    operator_urls = {}
    operator_view = etree.HTML(await fetch("https://prts.wiki/w/干员一览"))  # type: ignore
    for operator in operator_view.xpath("//*[@id='filter-data']/div/@data-zh") + ELITES:
        operator_urls[operator] = {operator: urllib.parse.urljoin(BASE_URL_W, operator)}
    return operator_urls


async def get_records() -> dict:
    operator_record_urls = {}
    operator_record_view = json.loads(await fetch(
        "https://prts.wiki/api.php?action=cargoquery&format=json&tables=char_memory&limit=500&fields=_pageName=page,storySetName,storyTxt"))
    for json_piece in operator_record_view["cargoquery"]:
        operator = json_piece["title"]["page"]
        record = json_piece["title"]["storySetName"]
        operator_record_urls.setdefault(operator, {})[record] = urllib.parse.urljoin(
            BASE_URL_W, json_piece["title"]["storyTxt"])
    return operator_record_urls


async def get_stories() -> tuple[dict, dict]:
    main_story_urls, event_story_urls = {}, {}
    story_view = etree.HTML(await fetch("https://prts.wiki/w/剧情一览"))  # type: ignore
    main_story_view, event_story_view = story_view.xpath("//*[@id='mw-content-text']/div/table")

    tr_tags = main_story_view.find('tbody').findall('tr')
    for tr_tag in tr_tags[1:]:  # 第一行是“主线剧情一览”
        chapter = tr_tag.findtext('th').strip()
        main_story_urls[chapter] = {}
        for a_tag in tr_tag.find('td').findall('a'):
            operation = a_tag.text
            main_story_urls[chapter][operation] = urllib.parse.urljoin(BASE_URL, a_tag.get("href"))

    tr_tags = event_story_view.find('tbody').findall('tr')
    special_story_amount = int(tr_tags[1].find('th').get("rowspan"))
    integrated_strategy_amount = int(tr_tags[1 + special_story_amount].find('th').get("rowspan"))
    for i in range(1, len(tr_tags)):  # 第一行是“活动剧情一览”
        tr_tag = tr_tags[i]
        if i in (1 + special_story_amount, 1 + special_story_amount + integrated_strategy_amount):
            chapter = tr_tag.find('th').getnext().text.strip()  # 集成战略与生息演算首行有两个 <th> 标签
        else:
            chapter = tr_tag.findtext('th').strip()
        if chapter == "长夜临光" and i < 1 + special_story_amount:
            chapter = "长夜临光·后记"  # 长夜临光后记剧情与 SideStory 重名
        event_story_urls[chapter] = {}
        for a_tag in tr_tag.find('td').findall('a'):
            operation = a_tag.text
            event_story_urls[chapter][operation] = urllib.parse.urljoin(BASE_URL, a_tag.get("href"))
    return main_story_urls, event_story_urls


async def main():
    print("加载中……")
    story_urls, operator_record_urls, operator_urls = await asyncio.gather(
        get_stories(), get_records(), get_operators())
    main_story_urls, event_story_urls = story_urls

    main_story_choices, event_story_choices, operator_record_choices, operator_choices = [], [], [], []
    while True:
        print("\n选择需要下载的剧情类型：")
        print("1：主线剧情")
        print("2：活动剧情")
        print("3：干员密录")
        print("4：干员资料")
        print("5：开始下载")
        print("6：退出程序")
        user_input = input("请输入选项对应的数字：").strip()
        match user_input:
            case '1':
                get_story_choices("主线剧情", main_story_urls, main_story_choices)
            case '2':
                get_story_choices("活动剧情", event_story_urls, event_story_choices)
            case '3':
                get_story_choices("干员密录", operator_record_urls, operator_record_choices)
            case '4':
                get_story_choices("干员资料", operator_urls, operator_choices)
            case '5':
                print(f"\n已选择的主线剧情：{'，'.join(main_story_choices)}")
                print(f"已选择的活动剧情：{'，'.join(event_story_choices)}")
                print(f"已选择的干员密录：{'，'.join(operator_record_choices)}")
                print(f"已选择的干员资料：{'，'.join(operator_choices)}\n")
                break
            case '6':
                sys.exit(0)
            case _:
                print(f"\n无此选项：{user_input}")

    async with asyncio.TaskGroup() as group:
        for choice in main_story_choices:
            group.create_task(download_story("主线剧情", choice, main_story_urls[choice]))
        for choice in event_story_choices:
            group.create_task(download_story("活动剧情", choice, event_story_urls[choice]))
        for choice in operator_record_choices:
            group.create_task(download_story("干员密录", choice, operator_record_urls[choice]))
        for choice in operator_choices:
            group.create_task(download_story("干员资料", choice, operator_urls[choice]))
        print("下载任务已全部启动\n")

    print("\n下载任务已全部完成")


if __name__ == "__main__":
    asyncio.run(main())
