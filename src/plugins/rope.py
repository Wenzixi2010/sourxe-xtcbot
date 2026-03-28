#!/usr/bin/env python3
"""
1分钟跳绳
"""

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

rope = on_command(
    "rope", 
    aliases={}, 
    priority=10, 
    block=True
)

@rope.handle()
async def handle_rope(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
            return
        
    try:
        user_id = event.user_id
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(user_id),))
            user_record = cursor.fetchone()
            
            # 允许的权限：admin、donor、advanced
            allowed_roles = ['admin', 'donor', 'advanced']
            if not user_record or user_record['role'] not in allowed_roles:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！请前往https://shop.sourxe.team购买Zxebot基础版激活码[5r]并使用/ac 激活码 激活后使用(不然我要亏死了)"))
                return
                
    except Exception as e:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限检查过程中出错：{str(e)}"))
        return
    finally:
        if 'conn' in locals():
            conn.close()
    
    content = args.extract_plain_text().strip()
    if not content:
        await matcher.send("请输入个数：\n"
                            "/rope count - 指定数量（个/一分钟）\n")
        return
    if int(content) > 114514:
        await matcher.send("个数过多（最多114514个）")
        return
    elif int(content) < 0:
        await matcher.send("个数不可小于0")
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
            
            response = Apirequests.sport_rope(watchid, bindnumber, chipid, model, content)
            if response['code'] == '000001':
                try:
                    await matcher.send(f"一分钟跳绳请求成功！\n"
                                        f"个数：{content}\n"
                                        f"----------------------\n"
                                        f"返回标题：{response['data']['achievementRecordVos'][0]['subTitle']}\n"
                                        f"返回码：{response['code']}\n"
                                        f"Info：{response['desc']}"
                                        )
                except Exception as e:
                    await matcher.send(f"一分钟跳绳请求成功！\n"
                                        f"修改个数：{content}\n"
                                        f"----------------------\n"
                                        f"返回码：{response['code']}\n"
                                        f"Info：{response['desc']}"
                                        )
            else:
                await matcher.send(f"一分钟跳绳数量修改失败！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}")
            
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"数据库操作失败，请稍后重试:{e}")
    finally:    
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "rope"
__plugin_usage__ = """
一分钟跳绳数量插件

命令列表：
/rope [Count] - 一分钟跳绳数量修改
例如：/rope 999
"""