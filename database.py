import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from config import config

VIDEO_DB_FILE = Path("video_index.json")
DATA_FILE = Path("channel_export.json")

video_list: List[Dict] = []
series_info: Dict[str, Dict] = {}
message_id_set: set[int] = set()


def parse_title_info(text: str) -> dict:
    """解析标题，正确区分季数和集数，支持汉字+数字混合格式，增强分类识别"""
    if not text:
        return {"name": "未知剧集", "episode": None, "season": 1, "duration": None, "tags": [], "media_type": "其他"}
    
    # 处理列表型文本结构
    if isinstance(text, list):
        full_text = ""
        for part in text:
            if isinstance(part, dict):
                full_text += part.get("text", "")
            else:
                full_text += str(part)
    else:
        full_text = str(text)
    
    # 提取剧名
    name_match = re.search(r"《([^》]+)》", full_text)
    series_name = name_match.group(1).strip() if name_match else "未知剧集"
    
    # 汉字数字转阿拉伯数字
    hanzi_map = {
        "零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,
        "十":10,"十一":11,"十二":12,"十三":13,"十四":14,"十五":15,"十六":16,
        "十七":17,"十八":18,"十九":19,"二十":20,"二十一":21,"二十二":22,
        "二十三":23,"二十四":24,"二十五":25,"二十六":26,"二十七":27,
        "二十八":28,"二十九":29,"三十":30
    }
    
    def hanzi_to_num(s):
        if not s: return None
        if s.isdigit(): return int(s)
        for length in (3, 2, 1):
            if s[:length] in hanzi_map:
                return hanzi_map[s[:length]]
        return None
    
    # 先提取【季数】—— 明确带"季"字，避免和集数混淆
    season = 1
    season_match = re.search(r"第\s*([零一二三四五六七八九十百\d]+)\s*季", full_text)
    if season_match:
        s_val = season_match.group(1)
        season = int(s_val) if s_val.isdigit() else hanzi_to_num(s_val) or 1
    
    # 再提取【集数】—— 优先"第X集"，然后末尾纯数字兜底
    episode = None
    
    # 优先级1：明确"第X集"，不会和季数混淆
    ep_match = re.search(r"第\s*([零一二三四五六七八九十百\d]+)\s*集", full_text)
    if ep_match:
        e_val = ep_match.group(1)
        episode = int(e_val) if e_val.isdigit() else hanzi_to_num(e_val)
    
    # 优先级2："第二十集20"这种汉字+数字双写，优先取末尾纯数字
    if not episode or episode != 20:
        num_at_end = re.search(r"(\d+)\s*(?:#|$)", full_text)
        if num_at_end:
            episode = int(num_at_end.group(1))  # 直接取20，最准确
    
    # 提取时长
    duration = None
    dur_match = re.search(r"时长[：:]\s*(\d+[:：]\d+)", full_text)
    if dur_match:
        duration = dur_match.group(1).replace("：", ":")
    
    # 提取标签
    tags = re.findall(r"#(\w+)", full_text)
    
    # ========== 增强版分类识别 ==========
    media_type = "其他"
    # 优先级1：标签优先
    if "#电视剧" in full_text:
        media_type = "电视剧"
    elif "#综艺" in full_text:
        media_type = "综艺"
    elif "#电影" in full_text:
        media_type = "电影"
    elif "#动漫" in full_text or "#动画" in full_text:
        media_type = "动漫"
    # 优先级2：关键词智能推测（兼容历史数据）
    else:
        if any(word in full_text for word in ["第", "集", "季", "部"]):
            media_type = "电视剧"
        elif any(word in full_text for word in ["综艺", "节目", "晚会"]):
            media_type = "综艺"
        elif any(word in full_text for word in ["电影", "剧场版"]):
            media_type = "电影"
        elif any(word in full_text for word in ["动漫", "动画", "卡通"]):
            media_type = "动漫"
    
    return {
        "name": series_name,
        "episode": episode,
        "season": season,
        "duration": duration,
        "tags": tags,
        "media_type": media_type,
        "raw_text": full_text
    }


def _save_index():
    with open(VIDEO_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(video_list, f, ensure_ascii=False, indent=2)


def _rebuild_series_info():
    global series_info
    series_info.clear()
    for v in video_list:
        name = v["series"]
        ep = v["episode"]
        if name not in series_info:
            series_info[name] = {"total": 0, "episodes": {}}
        info = series_info[name]
        if ep and ep > info["total"]:
            info["total"] = ep
        if ep:
            info["episodes"][ep] = v


def load_data():
    global video_list, message_id_set
    video_list.clear()
    message_id_set.clear()
    
    if VIDEO_DB_FILE.exists():
        try:
            with open(VIDEO_DB_FILE, "r", encoding="utf-8") as f:
                video_list = json.load(f)
            message_id_set = {v["message_id"] for v in video_list}
            print(f"📂 加载历史索引: {len(video_list)} 个视频")
        except Exception as e:
            print(f"索引库加载失败: {e}")
    
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            msg_list = data.get("messages", [])
            print(f"📂 读取导出文件: 共 {len(msg_list)} 条记录")
            
            for idx, msg in enumerate(msg_list):
                try:
                    mtype = msg.get("media_type")
                    if mtype != "video_file":
                        continue
                    
                    mid = msg["id"]
                    if mid in message_id_set:
                        continue
                    
                    # 提取标题
                    text_parts = []
                    entities = msg.get("text_entities", [])
                    if isinstance(entities, list):
                        for e in entities:
                            if isinstance(e, dict):
                                text_parts.append(e.get("text", ""))
                            else:
                                text_parts.append(str(e))
                    title = "".join(text_parts).strip() or "未命名视频"
                    
                    # 解析信息
                    info = parse_title_info(title)
                    series = info["name"]
                    ep = info["episode"]
                    media_type = info["media_type"]
                    
                    # 无集数自动编号
                    if ep is None:
                        same_count = sum(1 for v in video_list if v["series"] == series)
                        ep = same_count + 1
                        print(f"🔢 自动编号: [{series}] → 第{ep}集")
                    
                    file_id = ""  # 导出文件不含真实ID
                    duration = msg.get("duration_seconds", 0)
                    file_name = msg.get("file_name", "")
                    size = msg.get("file_size", 0)
                    
                    video = {
                        "id": len(video_list) + 1,
                        "message_id": mid,
                        "title": title,
                        "series": series,
                        "episode": ep,
                        "media_type": media_type,
                        "file_id": file_id,
                        "duration": duration,
                        "file_name": file_name,
                        "size": size
                    }
                    video_list.append(video)
                    message_id_set.add(mid)
                except Exception as e:
                    print(f"⚠️ 第 {idx+1} 条跳过: {e}")
                    continue
        except Exception as e:
            print(f"历史文件加载失败: {e}")
    
    _save_index()
    _rebuild_series_info()
    print(f"✅ 就绪: {len(series_info)} 部 / {len(video_list)} 个视频")
    print(f"ℹ️ 注意: 导出文件不含file_id，播放需直接在频道发消息获取")


def add_video(message_id: int, title: str, file_id: str, duration: int, **extra) -> Optional[Dict]:
    if message_id in message_id_set:
        return None
    
    info = parse_title_info(title)
    series = info["name"]
    episode = info["episode"]
    media_type = info["media_type"]
    
    new_id = max((v["id"] for v in video_list), default=0) + 1
    
    if episode is None:
        same_count = sum(1 for v in video_list if v["series"] == series)
        episode = same_count + 1
    
    video = {
        "id": new_id,
        "message_id": message_id,
        "title": title,
        "series": series,
        "episode": episode,
        "media_type": media_type,
        "file_id": file_id,
        "duration": duration,
        **extra
    }
    video_list.append(video)
    message_id_set.add(message_id)
    _save_index()
    _rebuild_series_info()
    print(f"🆕 新增: {series} 第{episode}集 file_id={file_id[:12]}...")
    return video


def get_all_series() -> List[str]:
    return sorted(series_info.keys())


def get_series_display(series_name: str) -> List[Dict]:
    info = series_info.get(series_name)
    if not info:
        return []
    total = info["total"]
    episodes = info["episodes"]
    result = []
    for ep in range(1, total + 1):
        v = episodes.get(ep)
        if v:
            available = bool(v.get("file_id"))
            result.append({"episode": ep, "available": available, "video": v if available else None})
        else:
            result.append({"episode": ep, "available": False, "video": None})
    return result


def search_series_by_keyword(keyword: str) -> List[str]:
    kw = keyword.strip().lower()
    return [name for name in get_all_series() if kw in name.lower()]


def get_video_by_id(vid: int) -> Optional[Dict]:
    return next((v for v in video_list if v["id"] == vid), None)


def get_all_categories():
    seen = set()
    order = ["电视剧", "综艺", "电影", "动漫", "其他"]
    for v in video_list:
        seen.add(v.get("media_type", "其他"))
    return [c for c in order if c in seen] + sorted(seen - set(order))


def get_series_by_category(category):
    names = set()
    for v in video_list:
        if v.get("media_type", "其他") == category:
            names.add(v["series"])
    return sorted(names)


load_data()