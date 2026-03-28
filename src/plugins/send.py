from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection
from modules import im_client 
from modules import Apirequests

send = on_command(
    "send", 
    aliases={}, 
    priority=10, 
    block=True
)

@send.handle()
async def send_start(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        return
    
    user_id = event.user_id
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await matcher.send("请输入正确的参数格式：/send imid 内容")
        return
    
    # 从左边分割，第一个空格前的是imid，后面的是内容
    parts = arg_text.split(' ', 1)
    if len(parts) < 2:
        await matcher.send("请输入正确的参数格式：/send imid 内容")
        return
        
    imid_str = parts[0]
    content = parts[1]
    
    try:
        imid = int(imid_str)
    except ValueError:
        await matcher.send("imid必须是数字！")
        return

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            user_role = cursor.fetchone()
            
            if not user_role or user_role['role'] not in ['admin', 'donor']:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！此功能仅对赞助者和管理员开放"))
                return

            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model, d.imaccountid
                FROM devices_info d
                WHERE d.user_id = %s
            """, (user_id,))
            
            device_record = cursor.fetchone()

            if not device_record:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 您还没有绑定设备，请先使用 /bindwatch 命令绑定设备"))
                return
            
            if not device_record.get('imaccountid'):
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 未获取到imaccountid，请先使用 /refresh 命令刷新设备信息"))
                return
                
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            bindnumber = device_record['bindnumber']
            imaccountid = device_record['imaccountid']
            model = device_record['model']
            
            friend_response = Apirequests.getfriend2(watchid, bindnumber, chipid, model)
            
            if not (friend_response and friend_response.get('code') == '000001' and 'data' in friend_response):
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 获取好友列表失败，请稍后重试！"))
                return
                
            friend_list = friend_response['data']
            valid_friend_ids = [int(friend.get('imFriendId')) for friend in friend_list if friend.get('imFriendId') is not None]
            if imid not in valid_friend_ids:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 目标imid不在您的好友列表中，请先添加好友再发送消息！"))
                return
            result = im_client.send_im_message(bindnumber, watchid, chipid, int(imid), int(imaccountid), content)
            if result:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 微聊消息发送成功！\n"
                                           f"----------------------\n"
                                           f"imfriendid: {imid}\n"
                                           f"内容: {content}"))
            else:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 微聊消息发送失败，请稍后重试！"))
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "send"
__plugin_usage__ = """
发送IM消息插件

命令列表：
/send imid 内容 - 向指定imid发送内容（仅赞助者和管理员可用，且imid必须在好友列表中）
"""