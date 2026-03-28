#!/usr/bin/env python3
"""
视频动态插件 - 发送视频到好友圈
"""

import json
import hashlib
import uuid
import os
import subprocess
import requests
import datetime
import zlib
from pathlib import Path
from nonebot import on_command, get_driver
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.bot import Bot
from nonebot.matcher import Matcher
from bot import get_db_connection
import aiohttp
import asyncio

# 创建命令处理器
moment_vid_cmd = on_command(
    "momentvid", 
    aliases={}, 
    priority=10, 
    block=True
)

# 临时文件存储目录
TEMP_DIR = Path("tmp/moment_vid")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 封面图片保存目录
COVER_DIR = Path("tmp/moment_vid")
COVER_DIR.mkdir(parents=True, exist_ok=True)

# 固定上传域名
UPLOAD_DOMAIN = "http://upload.qiniup.com"

@moment_vid_cmd.handle()
async def handle_moment_vid(event: MessageEvent, matcher: Matcher, bot: Bot, args: Message = CommandArg()):
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
    temp_video_path = None
    temp_cover_path = None
    upload_data = {}

    try:
        await matcher.send("正在处理您的请求\n提示：Pro服务已开始出售\n捐赠可以使用微聊转发功能，如需购买前往群公告网址")
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_info (user_id, role, created_at, last_login) 
                VALUES (%s, 'user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
                ON DUPLICATE KEY UPDATE last_login = CURRENT_TIMESTAMP
            """, (qqid,))
            
            cursor.execute("""
                SELECT d.watchid, d.chipid, d.bindnumber, d.model
                FROM devices_info d
                WHERE d.user_id = %s
            """, (qqid,))
            device_record = cursor.fetchone()
            
            conn.commit()
            
            if not device_record:
                await matcher.send("您还没有绑定设备，请先使用 /bindwatch 命令绑定设备")
                return
            
            watchid = device_record['watchid']
            chipid = device_record['chipid']
            model = device_record['model']
            bindnumber = device_record['bindnumber']

            # ========== 1. 获取视频并计算哈希 ==========
            video_url = await extract_video_url(bot, event)
            if not video_url:
                await matcher.send("请发送或引用包含MP4视频的消息")
                return

            user_temp_dir = TEMP_DIR / str(qqid)
            user_temp_dir.mkdir(parents=True, exist_ok=True)
            
            temp_video_path, md5_hash = await process_video(video_url, user_temp_dir)
            if not md5_hash:
                await matcher.send("缺少视频MD5,跳过该步骤")

            # ========== 2. 提取视频第一帧作为封面 ==========
            try:
                # 从视频文件中提取第一帧作为封面，保存在用户QQ号目录下
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_cover_path = COVER_DIR / str(qqid) / f"cover_{timestamp}.webp"
                
                temp_cover_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 构建ffmpeg命令
                # -ss 00:00:01 表示从第1秒开始（避免黑屏）
                # -vframes 1 只提取一帧
                # -s 320x360 调整尺寸为320x360
                # -q:v 2 设置质量（数值越小质量越好）
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-y',  # 覆盖现有文件
                    '-i', temp_video_path,
                    '-ss', '00:00:01',
                    '-vframes', '1',
                    '-s', '320x360',
                    '-q:v', '1',
                    '-f', 'image2',
                    str(temp_cover_path)
                ]
                
                # 执行ffmpeg命令
                process = subprocess.run(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )            
                if process.returncode != 0:
                    await matcher.send(Message(f'[CQ:at,qq={qqid}] 提取视频封面失败！\n错误信息：{process.stderr}'))
                    return
                
                if not os.path.exists(temp_cover_path):
                    await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面图片保存失败！'))
                    return
                
                # 计算封面CRC32值（先保存，后面上传时需要）
                with open(temp_cover_path, "rb") as f:
                    cover_data = f.read()
                    cover_crc32 = str(zlib.crc32(cover_data) & 0xFFFFFFFF)
                
            except subprocess.SubprocessError as e:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] ffmpeg处理错误，动态发布失败: {str(e)}'))
                return
            except Exception as e:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面处理出错，动态发布失败: {str(e)}'))
                return

            # ========== 3. 获取上传凭证 ==========
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            headers = {
                'User-Agent': "okhttp/3.12.0",
                'Connection': "Keep-Alive",
                'Accept-Encoding': "gzip",
                'Content-Type': "application/json",
                'model': model,
                'imSdkVersion': "102",
                'packageVersion': "49800",
                'Eebbk-Sign': "A1CDF0FFA3E7096A453B202CC7638B0A",
                'Base-Request-Param': json.dumps({
                    "accountId": watchid,
                    "appId": "2",
                    "deviceId": bindnumber,
                    "imFlag": "1",
                    "mac": "02:00:00:00:00:00",
                    "program": "watch",
                    "registId": 0,
                    "timestamp": current_time,
                    "token": chipid
                }),
                'dataCenterCode': "CN_BJ",
                'Version': "W_1.6.9",
                'Grey': "0",
                'Accept-Language': "zh-CN",
                'Watch-Time-Zone': "GMT+08:00",
                'Content-Type': "application/json; charset=UTF-8"
            }

            response = requests.post(
                "https://moment.watch.okii.com/moment/file/video/transfer?uuid=a03b990242274bfcac76a65fc65f1470",
                headers=headers,
                json={
                    "format": ".mp4",
                    "iconFormat": ".webp",
                    "localPornCensorSwitch": False,
                    "md5": md5_hash,
                    "sendType": 7,
                    "type": 5,
                    "videoType": 0,
                    "watchId": watchid
                },
                timeout=30
            )

            if response.status_code != 200:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 获取凭证失败\n状态码：{response.status_code}'))
                return
            
            json_data = response.json()
            upload_data = {
                "upload_token": json_data.get("data", {}).get("uploadToken"),
                "icon_upload_token": json_data.get("data", {}).get("iconUploadToken"),
                "source_key": json_data.get("data", {}).get("source", {}).get("key"),
                "source_download_url": json_data.get("data", {}).get("source", {}).get("downloadUrl"),
                "icon_key": json_data.get("data", {}).get("icon", {}).get("key"),
                "icon_download_url": json_data.get("data", {}).get("icon", {}).get("downloadUrl")
            }

            # ========== 4. 七牛云查询 ==========
            requests.get(
                "https://uc.qbox.me/v2/query?ak=IAM-uzPzpo9uYvtmU9hilIip3yCj2Bj6CWYqeovnpgsq&bucket=smartwatch-moment",
                headers={
                    'User-Agent': "QiniuAndroid/7.3.13 (13; XTC-Z7S; 1755239428539322; )",
                    'Accept-Encoding': "gzip"
                },
                timeout=5
            )
            
            # ========== 5. 上传封面到七牛云 ==========
            new_pic_key = None
            
            if not upload_data.get("icon_upload_token") or not upload_data.get("icon_key"):
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 获取七牛云上传凭证失败\n'
                                           f'--------------------\n'
                                           f'返回码: {response.json()["code"]}\n'
                                           f'Info: {response.json()["desc"]}'))
                return
            
            try:
                with open(temp_cover_path, 'rb') as cover_file:
                    files = [('file', (os.path.basename(temp_cover_path), cover_file, 'image/webp'))]
                    
                    response = requests.post(
                        UPLOAD_DOMAIN,
                        data={
                            'crc32': cover_crc32,
                            'key': upload_data["icon_key"],
                            'token': upload_data["icon_upload_token"]
                        },
                        files=files,
                        headers={
                            'User-Agent': "QiniuAndroid/7.3.13 (13; XTC-Z7S; 1755341437561202; IAM-uzPzpo9uYvtm)",
                            'Connection': "Keep-Alive",
                            'Accept-Encoding': "gzip"
                        },
                        timeout=30
                    )

                if response.status_code != 200:
                    await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面上传失败，动态发布失败！\n状态码：{response.status_code}'))
                    return
                
                try:
                    new_json = response.json()
                    if 'data' in new_json and isinstance(new_json['data'], dict):
                        new_pic_key = new_json['data'].get("key")
                        resource_url = new_json['data'].get("url")
                    else:
                        new_pic_key = new_json.get("key")
                        resource_url = None
                    
                    if not new_pic_key:
                        await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面上传成功但未返回key，动态发布失败！'))
                        return
                except json.JSONDecodeError:
                    await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面上传成功但响应格式错误，动态发布失败！'))
                    return

            except requests.RequestException as e:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面上传网络错误，动态发布失败: {str(e)}'))
                return
            except Exception as e:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 封面上传出错，动态发布失败: {str(e)}'))
                return
                
            # ========== 6. 上传视频到七牛云 ==========
            await matcher.send(Message(f'[CQ:at,qq={qqid}] 开始上传动态视频，时长可能较久请稍安勿躁'))
            file_name = os.path.basename(temp_video_path)
            with open(temp_video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            response = requests.post(
                UPLOAD_DOMAIN,
                data={
                    'key': upload_data["source_key"],
                    'token': upload_data["upload_token"],
                    'crc32': str(zlib.crc32(video_data) & 0xFFFFFFFF)
                },
                files={
                    'file': (file_name, video_data, 'video/mp4')
                },
                headers={
                    'User-Agent': 'QiniuAndroid/7.3.13',
                    'Accept-Encoding': 'gzip'
                },
                timeout=30
            )

            if response.status_code != 200:
                await matcher.send(Message(f'[CQ:at,qq={qqid}] 视频上传失败\n状态码：{response.status_code}'))
                return

            # ========== 7. 发布动态 ==========
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

            # 计算过期时间戳（当前时间+1小时）
            deadline = int(datetime.datetime.now().timestamp() * 1000) + 3600000

            # 构建content JSON
            content_json = {
                "dialogType": 6,
                "type": "1",
                "uploadTokenDeadLine": deadline,
                "zone": "z0",
                "icon": {
                    "downloadUrl": upload_data["icon_download_url"],
                    "height": 360,
                    "key": new_pic_key,
                    "urlDeadline": deadline,
                    "width": 320
                },
                "iconUploadTokenDeadLine": deadline,
                "source": {
                    "downloadUrl": upload_data["source_download_url"],
                    "height": 360,
                    "key": upload_data["source_key"],
                    "urlDeadline": deadline,
                    "width": 320
                },
                "transfer": {
                    "downloadUrl": upload_data["source_download_url"],
                    "height": 360,
                    "key": upload_data["source_key"],
                    "urlDeadline": deadline,
                    "width": 320
                }
            }
            
            # 构建resource JSON
            resource_content = {
                "content": json.dumps(content_json),
                "dialogType": 0,
                "picKey": new_pic_key,
                "videoKey": upload_data["source_key"]
            }
            
            payload = {
                "content": json.dumps(content_json),
                "emotionId": 0,
                "resource": json.dumps(resource_content),
                "resourceId": 0,
                "type": 6,
                "watchId": watchid
            }

            response = requests.post(
                "https://moment.watch.okii.com/moment/public?uuid=015e8e8da657421ea3119d0e4bdd8019",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            json_data = response.json()
            code = json_data.get("code")
            report = json_data.get("desc")
            
            if code == '000001':
                await matcher.send(Message(f"[CQ:at,qq={qqid}] 视频动态发布成功！\n"
                                  f"----------------------\n"
                                  f"返回码：{code}\n"
                                  f"Info：{report}\n"
                                  f"视频Key：{upload_data['source_key']}\n"
                                  f"封面Key：{new_pic_key}\n"
                                  ))
            else:
                await matcher.send(Message(f"[CQ:at,qq={qqid}] 视频动态发布失败！\n"
                                  f"----------------------\n"
                                  f"返回码：{code}\n"
                                  f"Info：{report}"
                                  ))

    except Exception as error:
        await matcher.send(Message(f"[CQ:at,qq={qqid}] 出错了！原因：{str(error)}"))
    finally:
        # 清理所有临时文件（视频和封面）
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
            except:
                pass
        if temp_cover_path and os.path.exists(temp_cover_path):
            try:
                os.remove(temp_cover_path)
            except:
                pass
        user_dir = TEMP_DIR / str(qqid)
        if user_dir.exists() and os.path.isdir(user_dir):
            try:
                if not os.listdir(user_dir):
                    os.rmdir(user_dir)
            except:
                pass
        if 'conn' in locals():
            conn.close()

async def extract_video_url(bot: Bot, event: GroupMessageEvent) -> str:
    for seg in event.message:
        if seg.type == "video":
            return seg.data["url"]
    
    if event.reply:
        reply_msg = await bot.get_msg(message_id=event.reply.message_id)
        for seg in reply_msg["message"]:
            if seg["type"] == "video":
                print(f"提取到视频URL: {seg['data']['url']}, 视频ID: {reply_msg}")
                return seg["data"]["url"]
    return ""

async def process_video(video_url: str, user_temp_dir: Path) -> tuple:
    temp_path = user_temp_dir / f"{uuid.uuid4().hex}.mp4"
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            
            result = await _download_video_async(video_url, temp_path)
            if result[0] is None or result[1] is None:
                raise Exception("视频下载失败")
            return result
                
        except Exception as e:
            error_msg = str(e)
            print(f"下载尝试 {attempt + 1} 失败: {error_msg}")
            
            if '视频文件已过期' in error_msg:
                raise Exception("视频文件已过期，请重新发送视频")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            else:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                return None, None

async def _download_video_async(video_url: str, temp_path: Path) -> tuple:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'video/mp4,video/webm,video/*;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://qun.qq.com/'
    }
    
    timeout = aiohttp.ClientTimeout(total=120)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(video_url, headers=headers) as response:
                print(f"HTTP状态码: {response.status}")
                print(f"响应头: {dict(response.headers)}")
                
                if response.status != 200:
                    content = await response.text()
                    if 'retcode' in content and 'file has expired' in content:
                        raise Exception("视频文件已过期，无法下载")
                    raise Exception(f"HTTP错误: {response.status}")
                
                total_size = int(response.headers.get('content-length', 0))
                content_type = response.headers.get('content-type', '')
                
                print(f"开始下载视频: {video_url}")
                print(f"内容类型: {content_type}, 文件大小: {total_size}字节")
                
                downloaded_size = 0
                with open(temp_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                
                actual_size = os.path.getsize(temp_path)
                print(f"实际下载大小: {actual_size}字节")
                
                if actual_size == 0:
                    raise Exception("下载文件为空")
                
                if actual_size < 1024:
                    raise Exception("文件过小，可能下载失败")
                
                try:
                    with open(temp_path, "rb") as f:
                        video_data = f.read()
                        md5_hash = hashlib.md5(video_data).hexdigest().upper()
                except Exception as e:
                    raise Exception(f"计算MD5失败: {str(e)}")
                
                print(f"视频下载成功: {temp_path}, 大小: {actual_size}字节, MD5: {md5_hash}")
                return str(temp_path), md5_hash
                
    except aiohttp.ClientError as e:
        raise Exception(f"网络错误: {str(e)}")
    except asyncio.TimeoutError:
        raise Exception("下载超时，请稍后重试")
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise Exception(f"下载失败: {str(e)}")

__plugin_name__ = "momentvid"
__plugin_usage__ = """
视频动态插件

命令列表：
/momentvid - 发送视频到好友圈（请在发送命令时附带或引用MP4视频）

"""