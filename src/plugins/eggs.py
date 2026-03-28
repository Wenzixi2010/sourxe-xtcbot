#!/usr/bin/env python3
"""
帮助插件
"""

import random
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot import get_driver

eggs_cmd = on_command(
    "???", 
    aliases={}, 
    priority=5, 
    block=True)

# 页面内容
eggs_pages = [
    """过年了，不要再讨论什么蛇年权益卡，福卡，龙卡，主页点赞，一键抢红包和运动装备，也不要再讨论哪个机型好，哪个机型不好了，你带任何手表回到家并不能给你带来任何实质性作用，朋友们兜里掏出一大把钱吃喝玩乐，你默默的在家里摆弄你的小78手表，刷NatureOS，刷CaremeOS，折腾XP和分区。亲戚朋友吃饭问你收获了什么，你说我学会了绕V3 ADB，学会了一键ROOT，学会了搞Magisk和冻结系统升级，学会了9008救砖，亲戚们懵逼了，你还在心里默默嘲笑他们，笑他们不懂你的刷Debug固件，刷TWRP，刷XP框架，刷WeichatPro2，刷SystemPlus，刷XTC Patch，装各种模块；笑他们买国行Apple.Watch比你贵好几千，充电还比你慢还不能拍照，信号不好还容易烫；笑他们不懂Z6DFB拍出来的照片多么好看。你父母的同事都在说自己的子女一年的收获，儿子买了个房，女儿买了个车，姑娘升职加薪了，你的父母默默无言，只能说我的儿子买了个手表，在家里不停的拔出数据线，插上数据线，每天早上起床第一件事是看看手表有没有被云控，看看微聊有没有人因为不点主页把你删了，经常盯着亮了又黑黑了又亮的手表又哭又笑，盯着电脑上的一个个进度条傻乐。亲戚们又懵了，随后笑笑说每个孩子爱好不一样""",
    """这怎么一半敖丙一半哪吒呀🤔🤔🤔这是哪吒的地盘😱😱😱所以把敖丙拿出去😡😡😡搁这🥴🥴🥴咋的🙄🙄🙄这明明是敖丙的地盘啊🤪🤪🤪你看我命由我不由天😓😓😓这句话是谁说的😏😏😏出去😡😡😡操蛋了🥵🥵🥵这还被人撵出来了😭😭😭我就要把你撵出去😋😋😋拿来😀😀😀这给我😨😨😨不是我说这少一块😍😍😍这是你让我拿来的🤤🤤🤤这就是我的了😏😏😏你的就你的有什么了不起的😱😱😱唉看来呀还是我收养敖丙吧🥰🥰🥰我还要把他给拼上呀😨😨😨拼就拼敖丙长的这么帅😍😍😍我一定会把他拼好的😭😭😭""",
    """你知道吗？你可以通过 /??? 来查看小彩蛋""",
    "锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷錕斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷錕斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷锟斤拷錕斤拷锟斤拷锟斤拷锟斤拷"
]

@eggs_cmd.handle()
async def handle_eggs(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    # 随机选择一句彩蛋内容
    random_egg = random.choice(eggs_pages)
    await matcher.send(random_egg)

# ==================== 插件元信息 ====================
__plugin_name__ = "eggs"
__plugin_usage__ = """
命令列表：
/??? - 随机显示一句小彩蛋
"""