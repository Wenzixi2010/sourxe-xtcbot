#!/usr/bin/env python3
"""
自检算码插件
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot import get_driver
from modules.NumCrypto import process_adb_new
from bot import get_db_connection

adb = on_command(
    "adb", 
    aliases={}, 
    priority=5, 
    block=True)

@adb.handle()
async def handle_adb(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    
    user_id = event.user_id
    
    number = args.extract_plain_text().strip()
    
    if not number:
        await matcher.send(Message(f"[CQ:at,qq={event.user_id}] 请输入自检校验码，如：/adb 114514"))
        return
    
    if not number.isdigit():
        await matcher.send(Message(f"[CQ:at,qq={event.user_id}] 请输入有效的校验码"))
        return
    
    try:
        result = process_adb_new(number)
        await matcher.send(Message(f"[CQ:at,qq={event.user_id}] 结果：{result}"))
        return
        
    except Exception as e:
        await matcher.send(Message(f"[CQ:at,qq={event.user_id}] 算码过程中出现错误：{str(e)}"))
        return

__plugin_name__ = "adb"
__plugin_usage__ = """
"""