#!/usr/bin/env python3

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

personalinfo = on_command(
    "personalinfo", 
    aliases={}, 
    priority=5, 
    block=True)

@personalinfo.handle()
async def handle_personalinfo(event: MessageEvent, matcher: Matcher):
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
            
            response = Apirequests.personalinfo(watchid, bindnumber, chipid, model)
            if response['code'] == '000001':
                data = response['data']
                genius_account = data['geniusAccount']
                personal_info = data['personalInfo']
                simple_medal = data['simpleMedal']
                socialize_user = data['socializeUser']
                
                medal_names = [medal['name'] for medal in simple_medal['medals']] if simple_medal.get('medals') else []
                
                await matcher.send(f"主页信息\n"
                                   f"-----------------\n"
                                   f"昵称：{genius_account['name']}\n"
                                   f"等级：{genius_account['level']}\n"
                                   f"积分：{genius_account['score']}\n"
                                   f"好友数：{genius_account['friends']}\n"
                                   f"联系人：{genius_account['contacts']}\n"
                                   f"个性签名：{personal_info['signature']}\n"
                                   f"获赞数(biu)：{personal_info['fuzzyLikes']}\n"
                                   f"勋章：{', '.join(medal_names) if medal_names else '无'}")
            else:
                await matcher.send(f"获取主页信息失败\n"
                                   f"-----------------\n"
                                   f"返回码：{response['code']}\n"
                                   f"Info：{response['desc']}")
            
    except Exception as e:
        await matcher.send(f"命令执行失败 {e}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "personalinfo"
__plugin_usage__ = """
命令列表：
/personalinfo
"""