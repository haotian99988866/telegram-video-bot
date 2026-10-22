import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from config import config

VIDEO_DB_FILE = Path("video_index.json")
DATA_FILE = Path("channel_export.json")

video_list: List[Dict] = []
series_info: Dict[str, Dict] = {}
message_id_set: set[int] = set()

def parse_title_info(text: str) -> Tuple[str, Optional[int], str, str]:
    text = text.strip() or "未命名视频"
    name_match = re.search(r"《(.+?)》", text)
    series_name = name_match.group(1).strip() if name_match else "其他"

        # 识别类型：优先匹配标签 #电视剧 #综艺 #电影 #动漫 #美剧 #英剧 等
    media_type = "其他"
    if re.search(r"#电视剧|电视剧|#美剧|美剧|#英剧|英剧|#韩剧|韩剧|#日剧|日剧|剧集|剧", text):
        media_type = "电视剧"
    elif re.search(r"#综艺|综艺|真人秀|晚会|访谈|脱口秀", text):
        media_type = "综艺"
    elif re.search(r"#电影|电影|影片|院线|剧场版", text):
        media_type = "电影"
    elif re.search(r"#动漫|动漫|动画|番剧|#日漫|日漫|#国漫|国漫", text):
        media_type = "动漫"

    # 识别集数 —— 适配「第一集01」「第六集06」格式
    ep_match = re.search(r"第(?:[一二三四五六七八九十百千万]+|\d+)\s*集\s*(\d+)", text)
    if not ep_match:
        ep_match = re.search(r"集\s*(\d+)|(\d+)\s*集", text)
    episode = None
    if ep_match:
        num_str = ep_match.group(1) or ep_match.group(2)
        if num_str:
            episode = int(num_str)

    return series_name, episode, text, media_type
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
        except Exception as e:
            print(f"索引库加载失败: {e}")

    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for msg in data.get("messages", []):
                if msg.get("media_type") != "video_file":
                    continue
                mid = msg["id"]
                if mid in message_id_set:
                    continue
                title = "".join(e.get("text", "") for e in msg.get("text_entities", [])).strip() or "未命名视频"
                series, ep, _ = parse_title_info(title)
                video = {
                    "id": len(video_list) + 1,
                    "message_id": mid,
                    "title": title,
                    "series": series,
                    "episode": ep,
                    "media_type": media_type,  # ← 新增
                    "file_id": msg.get("file_id", ""),
                    "duration": msg.get("duration_seconds", 0),
                    "file_name": msg.get("file_name", ""),
                    "size": msg.get("file_size", 0)
                }
                video_list.append(video)
                message_id_set.add(mid)
        except Exception as e:
            print(f"历史文件加载失败: {e}")

    _save_index()
    _rebuild_series_info()
    print(f"✅ 就绪: {len(series_info)} 部 / {len(video_list)} 个视频")

def add_video(message_id: int, title: str, file_id: str, duration: int, **extra) -> Optional[Dict]:
    if message_id in message_id_set:
        return None
    series, episode, _, media_type = parse_title_info(title)
    new_id = max((v["id"] for v in video_list), default=0) + 1
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
    if episode:
        print(f"🆕 新增: {series} 第{episode}集")
    else:
        print(f"🆕 新增: {title}")
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
            result.append({"episode": ep, "available": True, "video": v})
        else:
            result.append({"episode": ep, "available": False, "video": None})
    return result

def search_series_by_keyword(keyword: str) -> List[str]:
    kw = keyword.strip().lower()
    return [name for name in get_all_series() if kw in name.lower()]

def get_video_by_id(vid: int) -> Optional[Dict]:
    return next((v for v in video_list if v["id"] == vid), None)

def get_all_categories() -> List[str]:
    """获取所有分类"""
    cats = set()
    for v in video_list:
        cats.add(v.get("media_type", "其他"))
    return sorted(cats)

def get_series_by_category(category: str) -> List[str]:
    """按分类获取剧名列表"""
    names = set()
    for v in video_list:
        if v.get("media_type", "其他") == category:
            names.add(v["series"])
    return sorted(names)
def get_all_categories() -> List[str]:
    seen = set()
    order = ["电视剧", "综艺", "电影", "动漫", "其他"]
    for v in video_list:
        seen.add(v.get("media_type", "其他"))
    return [c for c in order if c in seen] + sorted(seen - set(order))

def get_series_by_category(category: str) -> List[str]:
    names = set()
    for v in video_list:
        if v.get("media_type", "其他") == category:
            names.add(v["series"])
    return sorted(names)
    
load_data()
