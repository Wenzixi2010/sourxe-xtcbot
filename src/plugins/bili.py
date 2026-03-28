from nonebot import on_command, get_driver
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, MessageEvent
from nonebot.matcher import Matcher
from bot import get_db_connection
import requests
import json
import hashlib
import uuid
import os
import subprocess
import datetime
import zlib
from pathlib import Path

bili_cmd = on_command(
    "bili", 
    aliases={}, 
    priority=10, 
    block=True
)

confirm_cmd = on_command(
    "确认发送", 
    aliases={}, 
    priority=10, 
    block=True
)

TEMP_DIR = Path("tmp/bili_vid")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

COVER_DIR = Path("tmp/bili_vid")
COVER_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DOMAIN = "http://upload.qiniup.com"

user_video_data = {}

@bili_cmd.handle()
async def handle_bili(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
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
    video_url = str(args).strip()
    
    if not video_url:
        await matcher.send("使用方法：/bili 哔哩哔哩视频链接")
        return
    
    try:
        await matcher.send("正在解析哔哩哔哩视频...")
        
        api_url = f"https://api.mir6.com/api/bzjiexi?url={video_url}&type=json"
        response = requests.get(api_url, timeout=30)
        
        if response.status_code != 200:
            await matcher.send("视频解析API请求失败")
            return
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            await matcher.send("视频解析API返回了无效的JSON格式")
            return
        
        if data['code'] != 200:
            await matcher.send(f"视频解析失败：{data['msg']}")
            return
        
        video_info = data['data'][0]
        title = data['title']
        cover = data['imgurl']
        desc = data['desc']
        user_name = data['user']['name']
        video_url = video_info['video_url']
        
        message = (f"视频标题：{title}\n"
                  f"视频描述：{desc}\n"
                  f"UP主：{user_name}\n"
                  f"视频链接：{video_url}\n\n"
                  f"请回复\"确认发送\"来发送该视频到好友圈")
        
        user_video_data[qqid] = {
            'video_url': video_url,
            'title': title,
            'cover': cover,
            'desc': desc,
            'user_name': user_name
        }
        
        await matcher.send(message)
        await matcher.send(Message(f'[CQ:image,file={cover}]'))
        
    except Exception as e:
        await matcher.send(f"操作失败：{str(e)}")

@confirm_cmd.handle()
async def handle_confirm(event: MessageEvent, matcher: Matcher):
    if not isinstance(event, GroupMessageEvent):
        await matcher.send("请前往群聊使用Bot！")
        return
    
    driver = get_driver()
    allowed_groups = getattr(driver.config, 'allowed_groups', [])
    if allowed_groups and str(event.group_id) not in allowed_groups:
        await matcher.send("此群聊未授权，请前往授权群聊使用Bot！")
        return
    
    qqid = event.user_id
    
    if qqid not in user_video_data:
        await matcher.send("请先使用 /bili 命令解析视频")
        return
    
    video_data = user_video_data[qqid]
    temp_video_path = None
    temp_cover_path = None
    
    try:
        await matcher.send("开始下载视频并准备发送...")
        
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

            user_temp_dir = TEMP_DIR / str(qqid)
            user_temp_dir.mkdir(parents=True, exist_ok=True)
            
            temp_video_path = user_temp_dir / f"video_{uuid.uuid4().hex}.mp4"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.bilibili.com/'
            }
            
            response = requests.get(video_data['video_url'], stream=True, headers=headers, timeout=60)
            if response.status_code != 200:
                await matcher.send("视频下载失败")
                return
            
            with open(temp_video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            with open(temp_video_path, 'rb') as f:
                video_data_bytes = f.read()
                md5_hash = hashlib.md5(video_data_bytes).hexdigest()

            # ========== 2. 提取视频第一帧作为封面 ==========
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_cover_path = COVER_DIR / str(qqid) / f"cover_{timestamp}.webp"
                temp_cover_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 构建ffmpeg命令
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
                    await matcher.send(f"提取视频封面失败！\n错误信息：{process.stderr}")
                    return
                
                if not os.path.exists(temp_cover_path):
                    await matcher.send("封面图片保存失败！")
                    return
                
                # 计算封面CRC32值
                with open(temp_cover_path, "rb") as f:
                    cover_data = f.read()
                    cover_crc32 = str(zlib.crc32(cover_data) & 0xFFFFFFFF)
                
            except subprocess.SubprocessError as e:
                await matcher.send(f"ffmpeg处理错误，动态发布失败: {str(e)}")
                return
            except Exception as e:
                await matcher.send(f"封面处理出错，动态发布失败: {str(e)}")
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
                await matcher.send(f"获取凭证失败\n状态码：{response.status_code}")
                return
            
            json_data = response.json()
            
            data = json_data.get("data", {})
            source = data.get("source", {})
            icon = data.get("icon", {})
            
            upload_data = {
                "upload_token": data.get("uploadToken"),
                "icon_upload_token": data.get("iconUploadToken"),
                "source_key": source.get("key"),
                "source_download_url": source.get("downloadUrl"),
                "icon_key": icon.get("key"),
                "icon_download_url": icon.get("downloadUrl")
            }

            # 检查必要的凭证字段是否存在
            if not upload_data.get("upload_token") or not upload_data.get("icon_upload_token"):
                await matcher.send(f"获取七牛云上传凭证失败\n--------------------\n返回码: {json_data.get('code', '未知')}\nInfo: {json_data.get('desc', '未知错误')}")
                return
            
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
                await matcher.send(f"获取七牛云上传凭证失败\n--------------------\n返回码: {response.json()['code']}\nInfo: {response.json()['desc']}")
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
                    await matcher.send(f"封面上传失败，动态发布失败！\n状态码：{response.status_code}")
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
                        await matcher.send("封面上传成功但未返回key，动态发布失败！")
                        return
                except json.JSONDecodeError:
                    await matcher.send("封面上传成功但响应格式错误，动态发布失败！")
                    return

            except requests.RequestException as e:
                await matcher.send(f"封面上传网络错误，动态发布失败: {str(e)}")
                return
            except Exception as e:
                await matcher.send(f"封面上传出错，动态发布失败: {str(e)}")
                return
                
            # ========== 6. 上传视频到七牛云 ==========
            await matcher.send("开始上传动态视频，时长可能较久请稍安勿躁")
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
                await matcher.send(f"视频上传失败\n状态码：{response.status_code}")
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
                await matcher.send(f"哔哩哔哩视频动态发布成功！\n"
                                  f"----------------------\n"
                                  f"返回码：{code}\n"
                                  f"Info：{report}\n"
                                  f"视频Key：{upload_data['source_key']}\n"
                                  f"封面Key：{new_pic_key}\n"
                                  )
            else:
                await matcher.send(f"哔哩哔哩视频动态发布失败！\n"
                                  f"----------------------\n"
                                  f"返回码：{code}\n"
                                  f"Info：{report}"
                                  )

            del user_video_data[qqid]
            
    except Exception as e:
        await matcher.send(f"操作失败：{str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if temp_cover_path and os.path.exists(temp_cover_path):
            os.remove(temp_cover_path)

__plugin_name__ = "bili"
__plugin_usage__ = """
哔哩哔哩视频插件

命令列表：
/bili 视频链接 - 解析哔哩哔哩视频信息
确认发送 - 确认发送解析的视频到好友圈
"""