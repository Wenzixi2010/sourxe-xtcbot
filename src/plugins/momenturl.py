import json
import requests
import datetime
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection
from modules import Apirequests

post_moment = on_command("momenturl", priority=50, block=True)

@post_moment.handle()
async def handle_post_moment(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
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
    user_input = args.extract_plain_text().strip()
    
    if not user_input:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 请输入正确的参数格式：/momenturl [网址] [描述]"
                                   f"如：/momenturl https://shop.sourxe.team 这是一个链接"))
        return
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:

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
            
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                desc_text = "Zxe BOT"
                url_text = parts[0]
            else:
                desc_text, url_text = parts
        
            response = Apirequests.momentlink(watchid, chipid, bindnumber, model, desc_text, url_text)
            if response['code'] == "000001":
                await matcher.send(f"链接动态发布成功！\n"
                                   f"-----------------\n"
                                   f"返回码: {response['code']}\n"
                                   f"Info: {response['desc']}")
            else:
                await matcher.send(f"动态发布失败！\n"
                                   f"-----------------\n"
                                   f"返回码: {response['code']}\n"
                                   f"Info: {response['desc']}")
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "momenturl"
__plugin_usage__ = """
发布网址动态插件

命令列表：
/momenturl 网址 [描述] - 发布包含网址的动态（仅赞助者和管理员可用）
"""