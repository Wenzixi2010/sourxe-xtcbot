#!/usr/bin/env python3

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot import get_driver
import modules.Apirequests as Apirequests
from bot import get_db_connection

appsearch_cmd = on_command(
    "appsearch", 
    aliases={}, 
    priority=5, 
    block=True)

@appsearch_cmd.handle()
async def handle_appsearch(event: MessageEvent, matcher: Matcher):
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

    args = str(event.get_message()).strip()
    if not args or len(args.split()) < 2:
        await matcher.send("使用方法：/appsearch 应用名称")
        return
    
    app_name = args.split(maxsplit=1)[1]
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
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备")
                return
            
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            watchid = device_record['watchid']
            model = device_record['model']
            
            response = Apirequests.appsearch(watchid, bindnumber, chipid, model, app_name)
            
            if response['code'] != '000001':
                await matcher.send(f"查找失败：{response['desc']}")
                return
            
            if not response['data']['searchList']:
                await matcher.send(f"未找到应用：{app_name}")
                return
            
            app = response['data']['searchList'][0]
            message = (f"应用名称：{app['name']}\n"
                      f"应用ID：{app['appId']}\n"
                      f"版本：{app['versionName']}\n"
                      f"包名：{app['packageName']}\n"
                      f"大小：{app['sizeShow']}\n"
                      f"评分：{app['score']}\n"
                      f"开发者：{app['developer']}\n"
                      f"更新时间：{app['upDateShow']}\n"
                      f"更新内容：{app['upgradeInfo']}\n"
                      f"描述：{app['summary']}\n"
                      f"下载链接：{app['url']}")
            
            await matcher.send(message)
            
    except Exception as e:
        await matcher.send(f"操作失败：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "appsearch"
__plugin_usage__ = """
应用查找插件

命令列表：
/appsearch 应用名称 - 查找指定应用并返回第一个结果
"""