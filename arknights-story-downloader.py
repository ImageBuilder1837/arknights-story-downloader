import asyncio
import json
import os
import re
import time
import urllib.parse

import aiohttp
from lxml import etree


BASE_URL = "https://prts.wiki/"
BASE_URL_W = "https://prts.wiki/w/"
ELITES = ["Pith", "Sharp", "Stormeye", "Touch", "郁金香"]


def extract_operator_archive_text(operator_html) -> str:
    operator_archive_text = ""
    archive_span = operator_html.xpath("//*[@id='干员档案']")[0]
    archive_table = archive_span.getparent().getnext().getnext()
    tr_tags = archive_table.find('tbody').findall('tr')
    for i in range(1, len(tr_tags), 3):
        title = tr_tags[i].find('th').find('div').findtext('p').strip()
        condition = tr_tags[i + 1].find('th').findtext('small').strip()
        paragraphs = tr_tags[i + 2].find('td').find('div').itertext()
        archive_text = f"### {title}\n\n*{condition}*\n\n"
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:  # 部分 paragraph 为空行
                archive_text += paragraph + '\n\n'
        operator_archive_text += archive_text
    return operator_archive_text


def extract_operator_voice_text(operator_html) -> str:
    titles = operator_html.xpath("//div[@id='voice-data-root']/div/@data-title")
    voices = operator_html.xpath("//div[@id='voice-data-root']/div/div[@data-kind-name='中文']/text()")

    operator_voice_text = ""
    for title, voice in zip(titles, voices):
        voice_text = f"### {title}\n\n{voice}\n\n"
        operator_voice_text += voice_text
    return operator_voice_text


def extract_operator_module_text(operator_html) -> str:
    modules = operator_html.xpath("//h3/span[@class='mw-headline']/text()")
    if not modules:
        return "该干员暂无模组"

    operator_module_text = ""
    for i in range(1, len(modules)):
        paragraphs = operator_html.xpath(
            f"//div[@id='mw-customcollapsible-module-{i+1}']/div[@id='mw-customcollapsible-module-{i+1}']/text()")
        module_text = f"### {modules[i]}\n\n"
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:  # 部分 paragraph 为空行
                module_text += paragraph + '\n\n'
        operator_module_text += module_text
    return operator_module_text


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


def parse_story_code(story_code: str):
    CONVERSATION = re.compile(r'\[name="(.*)".*\](.*)', re.I)
    DECISION = re.compile(r'\[decision\(.*options="(.*)".*values="(.*)".*\)\]', re.I)
    DEMAND = re.compile(r'(\[.*\])|(\{\{.*)|(\}\})')
    DIALOG = re.compile(r'\[dialog\]', re.I)
    DIALOG_SEP = "---\n\n"
    LINE_SEP = re.compile(r'((\\r)?\\n)+')
    MULTILINE = re.compile(r'\[multiline\(name="(.*)"(\s*,\s*end=(true))?\)\](.*)', re.I)
    PREDICATE = re.compile(r'\[predicate\(.*references="(.*)".*\)\]', re.I)
    STICKER = re.compile(r'\[sticker\(.*text="(.*?)".*\)\]', re.I)
    SUBTITLE = re.compile(r'\[subtitle\(.*text="(.*?)".*\)\]', re.I)

    story_text = ""
    lines = story_code.split("\n")
    last_line = DIALOG_SEP
    is_multi = False
    for line in lines:
        line = re.sub(LINE_SEP, ' ', remove_html_tag(line.strip()))
        if result := MULTILINE.match(line):
            groups = result.groups()
            name, is_end, sentence = groups[0], bool(groups[2]), groups[3]
            sentence = sentence.strip()  # 部分 sentence 有空格前后缀
            if name and sentence:  # 部分 multiline 为空行
                if not is_multi:
                    is_multi = True
                    last_line = f"**{name}**："
                last_line += sentence
                if is_end:
                    is_multi = False
                    last_line += '\n\n'
                    story_text += last_line
                continue
        elif is_multi:  # 部分 multiline 结束句无 end 标识
            is_multi = False
            last_line += '\n\n'
            story_text += last_line

        if result := CONVERSATION.match(line):
            name, sentence = result.groups()
            sentence = sentence.strip()  # 部分 sentence 有空格前后缀
            if name and sentence:  # 部分 conversation 为空行
                last_line = f"**{name}**：{sentence}\n\n"
                story_text += last_line
        elif result := DECISION.match(line):
            last_line = ""
            for option, value in zip(*map(lambda string: string.split(';'), result.groups())):
                last_line += f"选项 {value}：{option}\n\n"
            story_text += last_line
        elif result := DIALOG.match(line):
            if last_line != DIALOG_SEP:
                last_line = DIALOG_SEP
                story_text += last_line
        elif result := PREDICATE.match(line):
            num = result.group(1)
            last_line = f"选项 {num} 对应剧情：\n\n"
            story_text += last_line
        elif result := STICKER.match(line):
            sentence = result.group(1)
            sentence = sentence.strip()  # 部分 sentence 有空格前后缀
            if sentence:  # 部分 sticker 为空行
                last_line = f"**居中淡入文本**：{sentence}\n\n"
                story_text += last_line
        elif result := SUBTITLE.match(line):
            sentence = result.group(1)
            sentence = sentence.strip()  # 部分 sentence 有空格前后缀
            if sentence:  # 部分 subtitle 为空行
                last_line = f"**居中显示文本**：{sentence}\n\n"
                story_text += last_line
        elif DEMAND.match(line) or line.startswith('//'):
            continue
        elif line:
            last_line = line + '\n\n'
            story_text += last_line
    return story_text


def remove_html_tag(input_string: str) -> str:
    stack, output_string = [], ""
    for char in input_string:
        if char == '<':
            stack.append(char)
        elif char == '>':
            stack.pop()
        elif not stack:
            output_string += char
    assert not stack
    return output_string


async def download_story(story_type: str, story: str, story_urls: dict):
    print(f"正在下载：{story_type} {story}")
    story_text = f"# {story}\n\n"
    if story_type == "干员资料":
        operator_html = etree.HTML(await fetch(story_urls[story]))  # type: ignore
        operator_archive_text = extract_operator_archive_text(operator_html)
        story_text += f"## 干员档案\n\n{operator_archive_text}"
        operator_voice_text = extract_operator_voice_text(operator_html)
        story_text += f"## 语音记录\n\n{operator_voice_text}"
        operator_module_text = extract_operator_module_text(operator_html)
        story_text += f"## 模组文案\n\n{operator_module_text}"
    else:
        for operation in story_urls:
            operation_html = etree.HTML(await fetch(story_urls[operation]))  # type: ignore
            operation_code = operation_html.xpath("//*[@id='datas_txt']")[0].text
            operation_text = parse_story_code(operation_code)
            story_text += f"## {operation}\n\n{operation_text}"

    story_type_dir = os.path.join("downloads", story_type)
    if not os.path.isdir(story_type_dir):
        os.makedirs(story_type_dir)
    with open(os.path.join(story_type_dir, f"明日方舟{story_type}（{story}）.md"), 'w') as f:
        f.write(story_text.strip())

    print(f"下载完成：{story_type} {story}")


async def fetch(url: str) -> str:
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.text()
        except aiohttp.ClientError:
            if hasattr(fetch, "last_warn") and time.time() - fetch.last_warn < 10:
                continue
            fetch.last_warn = time.time()
            print("网络连接出现问题，正在尝试重新连接……")


async def get_operators():
    operator_urls = {}
    operator_view = etree.HTML(await fetch("https://prts.wiki/w/干员一览"))  # type: ignore
    for operator in operator_view.xpath("//*[@id='filter-data']/div/@data-zh") + ELITES:
        operator_urls[operator] = {operator: urllib.parse.urljoin(BASE_URL_W, operator)}
    return operator_urls


async def get_records():
    operator_record_urls = {}
    operator_record_view = json.loads(await fetch(
        "https://prts.wiki/api.php?action=cargoquery&format=json&tables=char_memory&limit=500&fields=_pageName=page,elite,level,favor,storySetName,storyIntro,storyTxt,storyIndex,medal"))
    for json_piece in operator_record_view["cargoquery"]:
        operator = json_piece["title"]["page"]
        record = json_piece["title"]["storySetName"]
        operator_record_urls.setdefault(operator, {})[record] = urllib.parse.urljoin(
            BASE_URL_W, json_piece["title"]["storyTxt"])
    return operator_record_urls


async def get_stories():
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
                exit(0)
            case _:
                print(f"\n无此选项：{user_input}")

    tasks = []
    for choice in main_story_choices:
        tasks.append(download_story("主线剧情", choice, main_story_urls[choice]))
    for choice in event_story_choices:
        tasks.append(download_story("活动剧情", choice, event_story_urls[choice]))
    for choice in operator_record_choices:
        tasks.append(download_story("干员密录", choice, operator_record_urls[choice]))
    for choice in operator_choices:
        tasks.append(download_story("干员资料", choice, operator_urls[choice]))

    await asyncio.gather(*tasks)
    print("\n下载任务已全部完成")


if __name__ == "__main__":
    asyncio.run(main())
