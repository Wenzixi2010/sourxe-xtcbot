#!/usr/bin/env python3
"""
图片动态插件 - 发送图片到好友圈
"""

import json
import hashlib
import uuid
import os
import requests
import datetime
import zlib
import subprocess
from pathlib import Path
from nonebot import on_command, get_driver
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.bot import Bot
from nonebot.matcher import Matcher
from bot import get_db_connection

# 创建命令处理器
moment_pic_cmd = on_command(
    "momentpic", 
    aliases={}, 
    priority=10, 
    block=True
)

# 临时文件存储目录
TEMP_DIR = Path("tmp/moment_pic")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

@moment_pic_cmd.handle()
async def handle_moment_pic(event: MessageEvent, matcher: Matcher, bot: Bot):
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
    
    qqid = event.user_id
    temp_image_path = None
    source_key = None
    
    try:
        await matcher.send("正在处理您的请求\n提示：Pro服务已开始出售\n捐赠可以使用微聊转发功能，如需购买前往群公告网址")
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model
                FROM devices_info d
                WHERE d.user_id = %s
            """, (qqid,))
            device_record = cursor.fetchone()
            
            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备（直接发送后面不用跟参数）")
                return
            
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            model = device_record['model']
            bindnumber = device_record['bindnumber']
        
        # 提取图片URL
        image_url = await extract_image_url(bot, event)
        if not image_url:
            await matcher.send("请发送或引用包含图片的消息")
            return

        # 处理图片
        temp_image_path, md5_hash = await process_image(image_url)
        if not md5_hash:
            await matcher.send("图片处理失败")
            return

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备请求头
        headers = {
            "model": model,
            "imSdkVersion": "102",
            "packageVersion": "53200",
            "Eebbk-Sign": "1AA7CF224B9485CE713F0DF3CDB4092C",
            "Base-Request-Param": json.dumps({
                "accountId": watchid,
                "appId": "2",
                "deviceId": bindnumber,
                "imFlag": "1",
                "mac": "unkown",
                "program": "watch",
                "registId": 0,
                "timestamp": current_time,
                "token": chipid
            }),
            "User-Agent": "okhttp/3.12.0",
            "Content-Type": "application/json; charset=UTF-8",
            "dataCenterCode": "CN_BJ",
            "Version": "W_1.6.9",
            "Grey": "0",
            "Accept-Language": "zh-CN",
            "Watch-Time-Zone": "GMT+08:00"
        }

        # 获取上传凭证
        await matcher.send(Message(f"[CQ:at,qq={qqid}] 正在获取上传凭证..."))
        response = requests.post(
            "https://moment.watch.okii.com/moment/file/pic/transfer?uuid=8006960b657b410dbb8cc4b85c6ac080",
            headers=headers,
            json={
                "md5": md5_hash,
                "watchId": watchid,
                "dialogType": 5,
                "format": ".webp"
            },
            timeout=30
        )

        if response.status_code != 200:
            await matcher.send(Message(f'[CQ:at,qq={qqid}] 获取凭证失败'))
            return
        
        try:
            json_data = response.json()
            
            # 检查响应结构
            if "code" not in json_data:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] API响应格式异常'))
                return
                
            # 检查是否返回正确的响应码
            if json_data["code"] != "000001":
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 获取凭证失败\n'
                                           f'---------------\n'
                                           f'返回码：{json_data["code"]}'))
                return

            upload_token = json_data.get("data", {}).get("uploadToken")

            if "data" in json_data and isinstance(json_data["data"], dict):
                if "source" in json_data["data"] and isinstance(json_data["data"]["source"], dict):
                    source_key = json_data["data"]["source"].get("key")
                else:
                    source_key = json_data["data"].get("key")

            if not upload_token:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 获取上传token失败'))
                return
                
            if not source_key:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 获取文件key失败'))
                return
                            
        except json.JSONDecodeError as e:
            await matcher.send(Message(f'[CQ:at,qq={qqid}] 解析API响应失败，返回内容不是有效的JSON\n错误：{str(e)}\n响应内容：{response.text[:200]}'))
            return

        # 七牛云查询
        try:
            requests.get(
                "https://uc.qbox.me/v2/query?ak=IAM-uzPzpo9uYvtmU9hilIip3yCj2Bj6CWYqeovnpgsq&bucket=smartwatch-moment",
                headers={
                    'User-Agent': "QiniuAndroid/7.3.13 (13; XTC-Z7S; 1755239428539322; )",
                    'Accept-Encoding': "gzip"
                },
                timeout=5
            )
        except Exception as e:
            await matcher.send(f"[CQ:at,qq={qqid}] 七牛云查询异常：{str(e)}，继续尝试上传...")

        # 上传图片
        file_name = os.path.basename(temp_image_path)
        with open(temp_image_path, 'rb') as image_file:
            files = [('file', (file_name, image_file, 'image/webp'))]
            
            # 计算CRC32值
            with open(temp_image_path, 'rb') as f:
                crc32_value = str(zlib.crc32(f.read()) & 0xFFFFFFFF)
            
            response = requests.post(
                "http://upload.qiniup.com",
                data={
                    'key': source_key,
                    'token': upload_token,
                    'crc32': crc32_value
                },
                files=files,
                headers={
                    'User-Agent': 'QiniuAndroid/7.3.13',
                    'Accept-Encoding': 'gzip'
                },
                timeout=30
            )

        # 更新时间戳参数
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        headers["Base-Request-Param"] = json.dumps({
            "accountId": watchid,
            "appId": "2",
            "deviceId": bindnumber,
            "imFlag": "1",
            "mac": "02:00:00:00:00:00",
            "program": "watch",
            "registId": 0,
            "timestamp": current_time,
            "token": chipid
        })

        # 发布动态
        response = requests.post(
            "https://moment.watch.okii.com/moment/public?uuid=b16d92fdd3a44ad4a1a8c243d1f02e66",
            headers=headers,
            json={
                "content": json.dumps({
                    "appIcon": "Qk3KDAAAAAAAAIoAAAB8AAAAHAAAABwAAAABACAAAwAAAEAMAAAAAAAAAAAAAAAAAAAAAAAAAAD/AAD/AAD/AAAAAAAA/wEAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAA//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/////////////////8+fr//Pn6//////////////////////////////////////////////////////////////////////////////////////////////////////////////////no7v/zyNX/997l//v3+f/vxs3/3n+O/+GTn//79vf////////////////////////////////////////////////////////////////////////////////////////////////////////////0z9X/66Gu//LK1v/ttMP/3X6O/9+Om//bcoL/+e/u//rv5//79O7//Pfz//rs4//8+PT//PXr//rv4f/58uj/+vPt//v29P/67uz/+/T2//jk6P/31+H/+Nvm//38/f//////////////////////+Onr/+eUnf/r0NH/9NHb//C7yf/gjJr/5qmz//rz7v/23c7/9tPB//bSw//449X/99y+//fct//238X/9s2x//bRwf/68vD/87m4//G6wf/vm6//8J+4/+6jwP/45u7////////////////////////////TpqH/q2NV//He3v/1097/6aO0//js7//78er/9tfF//bczv/0wbz/+e3k//bYsP/32bf/++/o//XGs//0vLP/+vPy//TK0P/wqLb/86/E/++Ss//tirT/99Tj///////////////////////w6ub/o21Z/8WHgP/LgHz/48/L//TN2f/43+f//Pf0//jh1f/57OP/+Ofe//ffxv/57Nr/+Ona//v18f/229T/9M3K//PP0v/xsr7/8Juz//O90f/xsMr/8rTP//z1+P//////////////////////yquf/6FoVP++l4r/nVZC/9OEhP/usr3/88PR//78/P////7///////////////7////////////////////////////57O//9tXc//ni6//1z9///v7+//7+/v///////////////////////////8yxpv+WVT7/q3hn/+PUz//23eD/8LvF//XY4P/+/f7////////////////////////////////////////////////////////////////////////////////////////////////////////////6+Pf/7eXi//n29f////////////7////+/v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////w==",
                    "appName": "来自ZxeBOT",
                    "packageName": "com.xtc.equitycard",
                    "trackMd5Value": json.dumps({"md5": md5_hash, "watchId": watchid}),
                    "transaction": f"{int(datetime.datetime.now().timestamp())}c4075-5f17-4561-b57c-6baa9c3a7890"
                }),
                "emotionId": 247,
                "packageName": "com.xtc.equitycard",
                "resource": source_key,
                "resourceId": 0,
                "type": 8,
                "watchId": watchid
            },
            timeout=30
        )
        try:
            json_data = response.json()
            code = json_data.get("code")
            report = json_data.get("desc")
            if code == '000001':
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 图片动态发布成功\n'
                                   f'----------------\n'
                                   f'返回码：{code}\n'
                                   f'Info：{report}'))
                return
            else:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 图片动态发布失败\n'
                                   f'----------------\n'
                                   f'返回码：{code}\n'
                                   f'Info：{report}'))
                return
        except json.JSONDecodeError:
            await matcher.send(Message(f'[CQ:at,qq={qqid}] 发布动态响应解析失败\n响应内容：{response.text[:200]}'))
            return

    except Exception as error:
        await matcher.send(Message(f"[CQ:at,qq={qqid}] 出错了！原因：{str(error)}"))
        import traceback
        print(f"Error in momentpic.py: {str(error)}")
        print(traceback.format_exc())
        return
    finally:
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
            except:
                pass
        if 'conn' in locals():
            try:
                conn.close()
            except:
                pass 

async def extract_image_url(bot: Bot, event: GroupMessageEvent) -> str:
    """
    提取图片URL
    """
    # 检查当前消息中的图片
    for seg in event.message:
        if seg.type == "image":
            return seg.data["url"]
    
    # 检查回复消息中的图片
    if event.reply:
        reply_msg = await bot.get_msg(message_id=event.reply.message_id)
        for seg in reply_msg["message"]:
            if seg["type"] == "image":
                return seg["data"]["url"]
    return ""

async def process_image(image_url: str) -> tuple:
    """
    下载图片并计算MD5，同时转换为WebP格式
    """
    temp_original_path = TEMP_DIR / f"{uuid.uuid4().hex}_original.jpg"
    temp_webp_path = TEMP_DIR / f"{uuid.uuid4().hex}.webp"
    
    try:
        # 下载原图
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()
        
        with open(temp_original_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        
        # 使用FFmpeg转换为WebP格式
        cmd = [
            "ffmpeg",
            "-i", str(temp_original_path),
            "-vf", "scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2:white",
            "-quality", "80",
            "-compression_level", "6",
            "-preset", "photo",
            "-loop", "0",
            str(temp_webp_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Exception(f"FFmpeg转换失败: {result.stderr}")
        
        # 计算WebP图片的MD5
        with open(temp_webp_path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest().upper()
        if os.path.exists(temp_original_path):
            os.remove(temp_original_path)
            
        return str(temp_webp_path), md5
    except Exception as e:
        print(f"图片处理失败: {str(e)}")
        for path in [temp_original_path, temp_webp_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        return None, None

__plugin_name__ = "momentpic"
__plugin_usage__ = """
图片动态插件

命令列表：
/momentpic - 发送图片到好友圈（请在发送命令时附带或引用图片）

"""