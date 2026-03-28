#!/usr/bin/env python3
"""
羽毛球
"""

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

sportbm = on_command(
    "sportbm", 
    aliases={}, 
    priority=10, 
    block=True
)

@sportbm.handle()
async def handle_sportbm(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
    
    content = args.extract_plain_text().strip()
    
    if not content:
        await matcher.send("请输入个数：\n"
                          "如：/sportbm 1145 - 1145个\n")
        return

    user_id = event.user_id
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
                SELECT d.chipid, d.bindnumber, d.watchid, d.model
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            conn.commit()

            device_record = cursor.fetchone()
            
            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备（直接发送后面不用跟参数）")
                return
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            watchid = device_record['watchid']
            model = device_record['model']
            
            response = Apirequests.sport_fifty(watchid, bindnumber, chipid, model, content)
            if response['code'] == '000001':
                await matcher.send(f"sport羽毛球执行成功！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}\n"
                                    f"Count：{content}"
                                    )
            else:
                await matcher.send(f"sport羽毛球执行失败！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}")
            
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"命令执行失败 {e}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "sportbm"
__plugin_usage__ = """
sportbm米时间修改插件

命令列表：
/sportbm [Second] - sportbm米时间修改
例如：/sportbm 6
"""