#!/usr/bin/env python3

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Message, MessageSegment, GroupMessageEvent
from nonebot.matcher import Matcher
import os
from nonebot import get_driver
import time

bindhelp_cmd = on_command(
    "bindhelp", 
    aliases={}, 
    priority=5, 
    block=True)

@bindhelp_cmd.handle()
async def handle_bindhelp(event: MessageEvent, matcher: Matcher):
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "movies", "bindhelp.mp4")
    
    text_message = """绑定教程：
首先在群内点击Bot头像，然后点击发消息，在临时对话窗口发送bindwatch这个命令进行账号绑定
z6及以下chipid在 自检 - 信息查看 - Barcode信息 - 点击Barcode信息中的二维码查看, 字符串前面带有chipid字样的就是chipid（可以扫码二维码直接复制）
z6以上需要自备id换号 直接私聊bindwatch然后依次发送你id的chipid和绑定号即可绑定
----------------------------------
使用自备id的用户！！！
绑定完id后请先后发送getinfo查看是否云控，若显示云控不推荐继续下面的操作（除非你不怕你的号也被云）
然后参考以下视频教程换号操作↓
Tips：换号完成后记得发送refresh命令刷新否则会000003返回码无法使用，还有在执行命令，如全点时请勿换号换回原表，否则无法继续执行操作"""
    
    try:
        await matcher.send(text_message)
        video_message = MessageSegment.video(f"file:///{video_path}")
        await matcher.send(video_message)
        
    except Exception as e:
        await matcher.send(f"发送失败：{str(e)}")

__plugin_name__ = "bindhelp"
__plugin_usage__ = """
命令列表：
/bindhelp - 显示绑定帮助视频
"""