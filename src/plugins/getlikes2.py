#!/usr/bin/env python3
"""
获取好友点赞列表
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

likeslist = on_command(
    "getlikes2", 
    aliases={}, 
    priority=5, 
    block=True)

@likeslist.handle()
async def handle_likeslist(event: MessageEvent, matcher: Matcher):
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
                SELECT d.watchid, d.chipid, d.bindnumber, d.model 
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()

            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备（直接发送后面不用跟参数）")
                return
    
            conn.commit()

            watchid = device_record['watchid']
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            model = device_record['model']
            response = Apirequests.getlike_hasid(watchid, bindnumber, chipid, model)
            if response == True:
                await matcher.send("所有好友已达到可点赞上限")
            else:
                try:
                    if response[0] == False:
                        if isinstance(response[1], list):
                            message = "未达到可点赞上限的好友：\n" + "\n".join(response[1])
                            await matcher.send(message)
                except Exception as e:
                    await matcher.send(f"获取好友列表失败！\n"
                                        f"----------------------\n"
                                        f"返回码：{response['code']}\n"
                                        f"Info：{response['desc']}\n")
            
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"命令执行失败 {e}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "likeslist2"
__plugin_usage__ = """
获取设备信息插件

命令列表：
/getlikes2 - 获取好友列表
"""