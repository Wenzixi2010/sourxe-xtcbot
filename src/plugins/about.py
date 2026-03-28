#!/usr/bin/env python3
"""
关于插件
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot import get_driver

about_cmd = on_command(
    "about", 
    aliases={}, 
    priority=5, 
    block=True)

# 关于页面内容
about_pages = """-----ZxeBot-----
本机器人为公益免费机器人
Only V1

开发者：Zxi2233（849340551）
特别感谢：
难安、乐轩、音绪、Windows、零御ZeroY、若颜
以及SourXe Team和所有支持我们开发的朋友(^▽^)

最终解释权归SourXe Team所有
SourXe Team官方群号：590196390
                                                                                  
Powered by Nonebot2
"""

@about_cmd.handle()
async def handle_about(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    await matcher.send(about_pages)

# ==================== 插件元信息 ====================
__plugin_name__ = "about"
__plugin_usage__ = """
命令列表：
/about
/about [页码] - 显示指定页码
"""