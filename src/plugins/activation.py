from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection
import random
import string
import re
from datetime import datetime, timedelta

generate_codes = on_command(
    "getcodes", 
    aliases={}, 
    priority=10, 
    block=True
)

activate = on_command(
    "ac", 
    aliases={}, 
    priority=10, 
    block=True
)

def generate_activation_code():
    """生成donor格式的激活码 (Zxi-开头，4段格式)"""
    characters = string.ascii_uppercase + string.digits
    code_parts = ['Zxi']  # 固定Zxi开头
    for i in range(3):  # 生成3段，总共4段
        part = ''.join(random.choice(characters) for _ in range(3))
        code_parts.append(part)
    return '-'.join(code_parts)

def is_advanced_activation_code(code):
    """通过数据库查询判断是否为advanced激活码"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT code_type FROM activation_codes 
                WHERE code = %s AND code_type = 'advanced'
            """, (code,))
            result = cursor.fetchone()
            return result is not None
    except Exception:
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def is_donor_activation_code(code):
    """通过数据库查询判断是否为donor激活码"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT code_type FROM activation_codes 
                WHERE code = %s AND code_type = 'donor'
            """, (code,))
            result = cursor.fetchone()
            return result is not None
    except Exception:
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def generate_advanced_activation_code():
    characters = string.ascii_uppercase + string.digits
    code_parts = ['Zxi']  # 固定Zxi开头
    for i in range(3):  # 生成3段，总共4段
        part = ''.join(random.choice(characters) for _ in range(3))
        code_parts.append(part)
    return '-'.join(code_parts)

@generate_codes.handle()
async def generate_codes_handler(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if isinstance(event, GroupMessageEvent):
        await matcher.send("请前往私聊使用此命令！")
        return
    
    user_id = event.user_id
    arg_text = args.extract_plain_text().strip()
    
    if not arg_text:
        await matcher.send("请输入正确的参数格式：/getcodes 数量 [类型]\n类型：donor(默认) 或 advanced")
        return
    
    try:
        parts = arg_text.split()
        count = int(parts[0])
        code_type = parts[1] if len(parts) > 1 else 'donor'
        
        if count <= 0 or count > 100:
            await matcher.send("生成数量必须在1-100之间")
            return
        
        if code_type not in ['donor', 'advanced']:
            await matcher.send("激活码类型必须是 donor 或 advanced")
            return
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT role FROM user_info WHERE user_id = %s
                """, (user_id,))
                current_user_role = cursor.fetchone()
                
                if not current_user_role or current_user_role['role'] != 'admin':
                    await matcher.send("权限不足！此功能仅对管理员开放")
                    return
                
                codes = []
                for i in range(count):
                    if code_type == 'advanced':
                        code = generate_advanced_activation_code()
                    else:
                        code = generate_activation_code()
                    
                    cursor.execute("""
                        INSERT INTO activation_codes (code, code_type, created_by, expires_at) 
                        VALUES (%s, %s, %s, NULL)
                    """, (code, code_type, str(user_id)))
                    codes.append(code)
                
                conn.commit()
                
                codes_text = "\n".join(codes)
                await matcher.send(f"成功生成 {count} 个{code_type}永久激活码：\n{codes_text}")
                
        except Exception as e:
            await matcher.send(f"生成激活码时出错：{str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()
                
    except ValueError:
        await matcher.send("参数格式错误！请使用：/getcodes 数量 [类型]\n类型：donor(默认) 或 advanced")

@activate.handle()
async def activate_handler(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
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
        await matcher.send("请输入激活码：/ac 激活码")
        return
    
    activation_code = arg_text.upper()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 直接查询激活码的有效性和类型
            cursor.execute("""
                SELECT code_type FROM activation_codes 
                WHERE code = %s AND status = 'active' 
                AND (expires_at IS NULL OR expires_at > NOW())
            """, (activation_code,))
            code_record = cursor.fetchone()
            
            if not code_record:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 激活码无效或已过期"))
                return
            
            # 从数据库获取激活码类型
            target_role = code_record['code_type']
            
            # 检查用户当前权限
            cursor.execute("""
                SELECT role FROM user_info WHERE user_id = %s
            """, (str(user_id),))
            user_record = cursor.fetchone()
            
            # 权限升级规则：只能升级到更高权限，不能降级
            role_hierarchy = {'user': 1, 'donor': 2, 'advanced': 3, 'admin': 4}
            current_role_level = role_hierarchy.get(user_record['role'] if user_record else 'user', 1)
            target_role_level = role_hierarchy[target_role]
            
            if current_role_level >= target_role_level:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 您已经是{user_record['role'] if user_record else 'user'}用户，无需使用此激活码"))
                return
            
            # 更新用户权限
            if not user_record:
                cursor.execute("""
                    INSERT INTO user_info (user_id, role, created_at, last_login) 
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (str(user_id), target_role))
            else:
                cursor.execute("""
                    UPDATE user_info SET role = %s, last_login = CURRENT_TIMESTAMP 
                    WHERE user_id = %s
                """, (target_role, str(user_id)))
            
            # 标记激活码为已使用
            cursor.execute("""
                UPDATE activation_codes 
                SET status = 'used', used_by = %s, used_at = CURRENT_TIMESTAMP 
                WHERE code = %s
            """, (str(user_id), activation_code))
            
            conn.commit()
            await matcher.send(Message(f"[CQ:at,qq={user_id}] 激活成功！您已获得{target_role}权限"))
            
    except Exception as e:
        await matcher.send(f"激活过程中出错：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()


__plugin_name__ = "activation"
__plugin_usage__ = """
激活码管理插件
"""