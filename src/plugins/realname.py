#!/usr/bin/env python3
"""
更改名称插件
"""

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

realname = on_command(
    "realname", 
    aliases={}, 
    priority=10, 
    block=True
)

@realname.handle()
async def realname_start(event: MessageEvent, matcher: Matcher, state: T_State, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    user_id = event.user_id
    content = args.extract_plain_text().strip()
    
    if not content:
        await matcher.send("请发送要修改的新名称，例如：/realname Zxi2233")
        return
    
    try:
        await matcher.send("正在处理您的请求\n提示：Pro服务已开始出售\n捐赠可以使用微聊转发功能，如需购买前往群公告网址")
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_info (user_id, role, created_at, last_login) 
                VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
                ON DUPLICATE KEY UPDATE last_login = CURRENT_TIMESTAMP
            """, (user_id,))

            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model 
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()

            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备（直接发送后面不用跟参数）")
                return
            
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            model = device_record['model']
            
            conn.commit()

            response = Apirequests.realname(watchid, bindnumber, chipid, model, content)
            
            if response.get('code') == '000001':
                await matcher.send(f"更改真实名称成功！\n"
                                    f"----------------------\n"
                                    f"New realname：{content}\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}")
            else:
                await matcher.send(f"更改名称失败！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}")
            
    except Exception as e:
        print(f"更改名称失败：{e}")
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_realname__ = "realname"
__plugin_usage__ = """
发送好友圈动态插件

命令列表：
/realname [realname] - 直接发送指定内容的动态
例如：/realname 222
"""