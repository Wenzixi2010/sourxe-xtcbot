from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection

addpro = on_command(
    "addpro", 
    aliases={}, 
    priority=10, 
    block=True
)

removepro = on_command(
    "removepro", 
    aliases={}, 
    priority=10, 
    block=True
)

addpro2 = on_command(
    "addpro2", 
    aliases={}, 
    priority=10, 
    block=True
)

def extract_qq_from_message(event: MessageEvent, args: Message):
    arg_text = args.extract_plain_text().strip()
    
    if arg_text:
        try:
            return int(arg_text)
        except ValueError:
            pass
    
    if hasattr(event, 'message') and event.message:
        for segment in event.message:
            if segment.type == 'at' and segment.data.get('qq'):
                try:
                    return int(segment.data['qq'])
                except (ValueError, KeyError):
                    continue
    
    return None

@addpro.handle()
async def addpro_handler(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        await matcher.send("此群聊未授权，请前往授权群聊使用Bot！")
        return
    
    user_id = event.user_id
    target_qq = extract_qq_from_message(event, args)
    
    if target_qq is None:
        await matcher.send("请@指定用户或输入QQ号：/addpro @用户 或 /addpro QQ号")
        return
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            current_user_role = cursor.fetchone()
            
            if not current_user_role or current_user_role['role'] != 'admin':
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！此功能仅对管理员开放"))
                return
            
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(target_qq),))
            target_user = cursor.fetchone()
            
            if not target_user:
                cursor.execute("""
                    INSERT INTO user_info (user_id, role, created_at, last_login) 
                    VALUES (%s, 'donor', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (str(target_qq),))
                result_message = f"用户 {target_qq} 不存在，已创建并设置为donor权限"
            else:
                cursor.execute("""
                    UPDATE user_info SET role = 'donor', last_login = CURRENT_TIMESTAMP 
                    WHERE user_id = %s
                """, (str(target_qq),))
                result_message = f"用户 {target_qq} 的权限已更新为donor"
            
            conn.commit()
            await matcher.send(Message(f"[CQ:at,qq={user_id}] {result_message}"))
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@removepro.handle()
async def removepro_handler(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        await matcher.send("此群聊未授权，请前往授权群聊使用Bot！")
        return
    
    user_id = event.user_id
    target_qq = extract_qq_from_message(event, args)
    
    if target_qq is None:
        await matcher.send("请@指定用户或输入QQ号：/removepro @用户 或 /removepro QQ号")
        return
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            current_user_role = cursor.fetchone()
            
            if not current_user_role or current_user_role['role'] != 'admin':
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！此功能仅对管理员开放"))
                return
            
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(target_qq),))
            target_user = cursor.fetchone()
            
            if not target_user:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 用户 {target_qq} 不存在"))
                return
            
            cursor.execute("""
                UPDATE user_info SET role = 'user', last_login = CURRENT_TIMESTAMP 
                WHERE user_id = %s
            """, (str(target_qq),))
            
            conn.commit()
            await matcher.send(Message(f"[CQ:at,qq={user_id}] 用户 {target_qq} 的权限已恢复为user"))
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@addpro2.handle()
async def addpro2_handler(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        await matcher.send("此群聊未授权，请前往授权群聊使用Bot！")
        return
    
    user_id = event.user_id
    target_qq = extract_qq_from_message(event, args)
    
    if target_qq is None:
        await matcher.send("请@指定用户或输入QQ号：/addpro2 @用户 或 /addpro2 QQ号")
        return
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (user_id,))
            current_user_role = cursor.fetchone()
            
            if not current_user_role or current_user_role['role'] != 'admin':
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 权限不足！此功能仅对管理员开放"))
                return
            
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(target_qq),))
            target_user = cursor.fetchone()
            
            if not target_user:
                cursor.execute("""
                    INSERT INTO user_info (user_id, role, created_at, last_login) 
                    VALUES (%s, 'advanced', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (str(target_qq),))
                result_message = f"用户 {target_qq} 不存在，已创建并设置为基础权限"
            else:
                cursor.execute("""
                    UPDATE user_info SET role = 'advanced', last_login = CURRENT_TIMESTAMP 
                    WHERE user_id = %s
                """, (str(target_qq),))
                result_message = f"用户 {target_qq} 的权限已更新为advanced"
            
            conn.commit()
            await matcher.send(Message(f"[CQ:at,qq={user_id}] {result_message}"))
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "promanage"
__plugin_usage__ = """
权限管理插件

命令列表：
/addpro @用户 或 /addpro QQ号 - 给指定用户添加donor权限（仅管理员可用）
/removepro @用户 或 /removepro QQ号 - 移除指定用户的donor权限，恢复为user权限（仅管理员可用）
"""