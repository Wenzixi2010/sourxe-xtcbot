import asyncio
import random
import time
import requests
from datetime import datetime
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageEvent, Message, GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot import get_driver
from bot import get_db_connection

del_moments = on_command("delmoment", priority=50, block=True)

@del_moments.handle()
async def handle_del(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
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
    text = args.extract_plain_text().strip()
    
    if not text:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 请输入正确的参数格式：/delmoment 数量"))
        return
    
    try:
        text = int(text)
    except ValueError:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 请输入有效的数字"))
        return

    if text < 1:
        await matcher.send("请输入正确的格式：/delmoment [num]")
        return

    if text > 50:
        await matcher.send(Message(f"[CQ:at,qq={user_id}] 单次删除数量不能超过50，请减少数量后重试"))
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
            
            await matcher.send(Message(f"[CQ:at,qq={user_id}] 正在执行删除 {text} 条好友圈动态，时间可能比较久，请耐心等待..."))
            
            current_timestamp_ms = int(datetime.now().timestamp() * 1000)
            friend_url = "https://moment.watch.okii.com/moment/search?uuid=03c155909b8046458e850d4a3bf9112b"
            
            group_size = 20
            groups = []
            remaining = text
            current_from = 0
            
            while remaining > 0:
                take = min(remaining, group_size)
                groups.append((current_from, take))
                remaining -= take
                current_from += take
            
            all_moments = []
            
            for from_val, size_val in groups:
                friend_headers = {
                    "model": f"{model}",
                    "imSdkVersion": "102",
                    "packageVersion": "110630",
                    "packageName": "com.xtc.moment",
                    "Eebbk-Sign": "A51D62CFC092145332203E9BF6398A88",
                    "Base-Request-Param": '{"accountId":"?","appId":"2","deviceId":"*","imFlag":"1","mac":"unkown","program":"watch","registId":0,"timestamp":"","token":"%"}', 
                    "dataCenterCode": "CN_BJ",
                    "Version": "W_5.0.2",
                    "Grey": "0",
                    "Accept-Language": "zh-CN",
                    "Watch-Time-Zone": "GMT+08:00",
                    "Content-Type": "application/json; charset=UTF-8",
                    "Host": "moment.watch.okii.com",
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "User-Agent": "okhttp/3.12.0"
                }
                friend_headers["Base-Request-Param"] = friend_headers["Base-Request-Param"].replace('"?"', f'"{watchid}"')
                friend_headers["Base-Request-Param"] = friend_headers["Base-Request-Param"].replace('"*"', f'"{bindnumber}"')
                friend_headers["Base-Request-Param"] = friend_headers["Base-Request-Param"].replace('"%"', f'"{chipid}"')
                
                friend_data = {
                    "commentPageSize": str(5),
                    "currentWatchId": watchid,
                    "end": str(current_timestamp_ms),
                    "friend": str(0),
                    "from": str(from_val),
                    "lastLikeTime": str(current_timestamp_ms),
                    "searchPermission": str(0),
                    "size": str(size_val),
                    "watchId": watchid
                }
                
                friend_response = requests.post(friend_url, headers=friend_headers, json=friend_data)
                
                if friend_response.status_code != 200:
                    await matcher.send(Message(f"[CQ:at,qq={user_id}] 获取动态列表失败，HTTP状态码：{friend_response.status_code}"))
                    return
                
                friend_json = friend_response.json()
                if friend_json.get("code") != "000001":
                    await matcher.send(Message(f"[CQ:at,qq={user_id}] 获取动态列表失败，返回信息：{friend_json.get('desc', '未知错误')}"))
                    return
                
                current_moments = friend_json['data'].get("watchMoments", [])
                all_moments.extend(current_moments)
                
                if len(groups) > 1:
                    await asyncio.sleep(random.uniform(1, 3))
            
            total_moments = len(all_moments)
            if total_moments == 0:
                await matcher.send(Message(f"[CQ:at,qq={user_id}] 未获取到任何动态，无法进行删除"))
                return
            
            avg_delay = 2
            estimated_seconds = int(total_moments * avg_delay)
            minutes, seconds = divmod(estimated_seconds, 60)
            await matcher.send(Message(f"[CQ:at,qq={user_id}] 共获取到{total_moments}条动态，开始执行删除操作，预计完成时间：{minutes}分{seconds}秒"))
            
            del_url = "https://moment.watch.okii.com/moment/delete?uuid=36d3b1c99cae4e2bb42599b3f9327f12"
            success = []
            fail = []
            
            for friend in all_moments:
                delay = random.uniform(1, 3)
                await asyncio.sleep(delay)
                
                del_moment = friend.get('momentId', 'N/A')
                
                del_headers = {
                    'User-Agent': "okhttp/3.12.0",
                    'Connection': "Keep-Alive",
                    'Accept-Encoding': "gzip",
                    'Content-Type': "application/json; charset=UTF-8",
                    'model': f"{model}",
                    'imSdkVersion': "102",
                    'packageVersion': "53200",
                    'Eebbk-Sign': "6E102731E6ECE21377EBBDE86EFCBC1D",
                    "packageName": "com.xtc.moment",
                    'Base-Request-Param': '{"accountId":"?","appId":"2","mac":"unkown","deviceId":"*","token":"%","timestamp":"","imFlag":"1","registId":0,"program":"watch"}',
                    'dataCenterCode': "CN_BJ",
                    'Version': "W_2.6.5",
                    'Grey': "0",
                    "Host": "moment.watch.okii.com",
                    'Accept-Language': "zh-CN",
                    'Watch-Time-Zone': "GMT+08:00"
                }
                del_headers["Base-Request-Param"] = del_headers["Base-Request-Param"].replace('"?"', f'"{watchid}"')
                del_headers["Base-Request-Param"] = del_headers["Base-Request-Param"].replace('"*"', f'"{bindnumber}"')
                del_headers["Base-Request-Param"] = del_headers["Base-Request-Param"].replace('"%"', f'"{chipid}"')
                
                del_payload = {
                    "momentId": del_moment,
                    "watchId": watchid
                }
                
                try:
                    del_response = requests.post(del_url, headers=del_headers, json=del_payload, timeout=30)
                    del_json = del_response.json()
                    
                    if del_response.status_code == 200 and del_json.get("code") == "000001":
                        success.append(del_moment)
                    else:
                        fail.append(del_moment)
                except Exception as e:
                    fail.append(f"{del_moment}(异常: {str(e)})")
            
            result_msg = f"[CQ:at,qq={user_id}] 删除操作完成，成功: {len(success)}条，失败: {len(fail)}条"
            await matcher.send(Message(result_msg))
            
    except Exception as e:
        await matcher.send(f"执行错误：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

__plugin_name__ = "delmoment"
__plugin_usage__ = """
删除好友圈动态插件

命令列表：
/delmoment 数量 - 删除指定数量的好友圈动态（仅赞助者和管理员可用）
"""