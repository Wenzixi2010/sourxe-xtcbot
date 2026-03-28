from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

imfriendid = on_command(
    "imfriendid", 
    aliases={}, 
    priority=10, 
    block=True
)

@imfriendid.handle()
async def imfriendid_start(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        return
    
    user_id = event.user_id

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 插入用户信息，role可以是user、admin或donor
            cursor.execute("""
                INSERT INTO user_info (user_id, role, created_at, last_login) 
                VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
                ON DUPLICATE KEY UPDATE last_login = CURRENT_TIMESTAMP
            """, (user_id,))

            # 检查用户权限，只有donor和admin可以使用
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            user_role = cursor.fetchone()
            
            # 验证权限
            if not user_role or user_role['role'] not in ['admin', 'donor']:
                await matcher.send(Message(f"[CQ:at,qq={user_id}]权限不足！此功能仅对赞助者和管理员开放"))
                return

            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model 
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()

            if not device_record:
                await matcher.send(Message(f"[CQ:at,qq={user_id}]您还没有绑定设备，请先使用 /bindwatch 命令绑定设备"))
                return
            
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            model = device_record['model']
            
            conn.commit()

            response = Apirequests.getfriend2(watchid, bindnumber, chipid, model)
            
            if response.get('code') == '000001' and 'data' in response:
                friend_list = response['data']
                result_text = "好友imFriendId\n---------------\n"
                for i, friend in enumerate(friend_list, 1):
                    name = friend.get('name', '未知')
                    im_friend_id = friend.get('imFriendId', '未知')
                    result_text += f"{i}: {name}({im_friend_id})\n"
                
                await matcher.send(result_text.strip())
                    
            else:
                await matcher.send(f"获取好友列表失败！\n-----------------\n返回码：{response.get('code', '未知')}\nInfo：{response.get('desc', '未知')}")
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "imfriendid"
__plugin_usage__ = """
获取好友imFriendId插件

命令列表：
/imfriendid - 获取所有好友的imFriendId和姓名（仅赞助者和管理员可用）
"""