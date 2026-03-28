from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from modules import Apirequests
from bot import get_db_connection

refresh = on_command(
    "refresh", 
    aliases={}, 
    priority=5, 
    block=True)

@refresh.handle()
async def handle_refresh(event: MessageEvent, matcher: Matcher):
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
            
            cursor.execute("DESCRIBE devices_info")
            columns = [column['Field'] for column in cursor.fetchall()]
            
            if 'imaccountid' in columns:
                cursor.execute("""
                    SELECT d.chipid, d.bindnumber, d.watchid, d.model, d.imaccountid
                    FROM devices_info d
                    WHERE d.user_id = %s
                """, (user_id,))
            else:
                # 如果字段不存在，则不查询它
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
            old_watchid = device_record['watchid']
            old_model = device_record['model']
            
            response = Apirequests.get_info(bindnumber, chipid)
            if response['code'] == '000001':
                new_watchid = response['data']['id']
                new_model = response['data']['innerModel']
                imaccountid = response['data'].get('imAccountInfo', {}).get('imAccountId', '')
                
                if 'imaccountid' in columns:
                    cursor.execute("""
                        UPDATE devices_info 
                        SET watchid = %s, model = %s, imaccountid = %s
                        WHERE user_id = %s
                    """, (new_watchid, new_model, imaccountid, user_id))
                else:
                    cursor.execute("""
                        UPDATE devices_info 
                        SET watchid = %s, model = %s
                        WHERE user_id = %s
                    """, (new_watchid, new_model, user_id))
                
                conn.commit()
                
                await matcher.send(f"设备信息刷新成功！\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}\n"
                                    f"---------------------------\n"
                                    f"刷新前watchID：{old_watchid}\n"
                                    f"刷新后watchID：{new_watchid}\n"
                                    f"imaccountID：{imaccountid}\n"
                                    f"旧机型：{old_model} → 新机型：{new_model}\n"
                                    f"名称：{response['data']['name']}\n"
                                    f"系统版本：{response['data']['firmware']}\n"
                                    f"属地：{response['data']['pushProvince']}\n"
                                    f"电量：{response['data']['battery']}%"
                                    )
            else:
                await matcher.send(f"刷新设备信息失败！\n"
                                    f"----------------------\n"
                                    f"返回码：{response['code']}\n"
                                    f"Info：{response['desc']}\n")
            
    except Exception as e:
        print(f"数据库操作失败：{e}")
        await matcher.send(f"数据库操作失败：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "refresh"
__plugin_usage__ = """
刷新设备信息插件

命令列表：
/refresh - 刷新当前用户的设备信息
"""