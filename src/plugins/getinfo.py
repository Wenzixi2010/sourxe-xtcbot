#!/usr/bin/env python3
"""
获取手表信息
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

getinfo = on_command(
    "getinfo", 
    aliases={}, 
    priority=5, 
    block=True)

@getinfo.handle()
async def handle_getinfo(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("请前往群聊使用Bot！(SourXe BotGroup: 1063758858)")
        return
    if isinstance(event, GroupMessageEvent):
        driver = get_driver()
        allowed_groups = driver.config.allowed_groups
        if str(event.group_id) not in allowed_groups:
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
            
            response = Apirequests.get_info(bindnumber, chipid)
            response2 = Apirequests.getyk(watchid, bindnumber, chipid, model)
            imaccountid = response['data']['imAccountInfo']['imAccountId']
            watchid2 = response['data']['id']
            if response['code'] == '000001':
                if response2['code'] == '000001':
                    ykstatus = '未云控'
                elif response2['code'] == '000007':
                    ykstatus = '也许被云控'
                elif response2['code'] == '000003':
                    ykstatus = '设备信息未刷新，请执行/refresh指令后重试'
                else:
                    ykstatus = '无法获取云控状态'
                message = (f"返回码：{response['code']}\n"
                        f"Info：{response['desc']}\n"
                        f"---------------------------\n"
                        f"watchid：{watchid2}\n"
                        f"imAccountid：{imaccountid}\n"
                        f"名称：{response['data']['name']}\n"
                        f"机型：{response['data']['model']}\n"
                        f"内部代号：{response['data']['innerModel']}\n"
                        f"系统版本：{response['data']['firmware']}\n"
                        f"语言: {response['data']['language']}\n"
                        f"属地：{response['data']['pushProvince']}\n"
                        f"电量：{response['data']['battery']}%\n"
                        f"是否低电量保护: {response['data']['powerLowProtectSwitch']}\n"
                        f"云控状态：{ykstatus}")
                await matcher.send(message)
            else:
                await matcher.send(f"获取设备信息失败！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}")
            
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"命令执行失败 {e}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "getinfo"
__plugin_usage__ = """
获取设备信息插件

命令列表：
/getinfo - 获取当前用户的设备信息
"""