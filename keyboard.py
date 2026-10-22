from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import config
import database as db


def build_category_menu() -> InlineKeyboardMarkup:
    fixed_order = ["电视剧", "综艺", "电影", "动漫/日漫", "英/美剧", "日韩剧", "网剧"]
    has_content = set(db.get_all_categories())
    
    buttons = []
    row = []
    for cat in fixed_order:
        if cat in has_content:
            btn = InlineKeyboardButton(
                text=f"📂 {cat}",
                callback_data=f"cat|{cat}|1"
            )
        else:
            btn = InlineKeyboardButton(
                text=f"📂 {cat} (暂无)",
                callback_data="noop"
            )
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # ✅ 去掉了搜索按钮，只保留全部剧集
    buttons.append([
        InlineKeyboardButton(text="📁 全部剧集", callback_data="all|all|1")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_series_menu(page: int = 1, list_override=None) -> InlineKeyboardMarkup:
    names = list_override if list_override is not None else db.get_all_series()
    if not names:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="暂无剧集", callback_data="noop")
        ]])
    
    per_page = getattr(config, 'PER_PAGE', 30)
    total_pages = (len(names) - 1) // per_page + 1
    start = (page - 1) * per_page
    page_items = names[start : start + per_page]
    
    buttons = []
    for name in page_items:
        buttons.append([
            InlineKeyboardButton(
                text=f"📺 {name}",
                callback_data=f"eps|{name}|1"
            )
        ])
    
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"all|all|{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"第{page}/{total_pages}页", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"all|all|{page+1}"))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton(text="⬅️ 返回分类", callback_data="home|home|1")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_episode_menu(series_name: str, page: int = 1) -> InlineKeyboardMarkup:
    items = db.get_series_display(series_name)
    if not items:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ 暂无已收录集数", callback_data="noop")],
            [InlineKeyboardButton(text="⬅️ 返回", callback_data="home|home|1")]
        ])
    
    per_page = getattr(config, 'PER_PAGE', 60)
    total_pages = (len(items) - 1) // per_page + 1
    start = (page - 1) * per_page
    page_items = items[start : start + per_page]
    
    buttons = []
    row = []
    for idx, it in enumerate(page_items):
        ep = it["episode"]
        available = it["available"]
        video_info = it.get("video")
        vid = video_info.get("id") if video_info else 0
        
        if available and vid:
            btn = InlineKeyboardButton(
                text=f"✅{ep}",
                callback_data=f"play|{series_name}|{ep}|{vid}"
            )
        else:
            btn = InlineKeyboardButton(
                text=f"⏳{ep}",
                callback_data="noop"
            )
        
        row.append(btn)
        if len(row) == 6 or idx == len(page_items) - 1:
            buttons.append(row)
            row = []
    
    nav_row = []
    if page > 2:
        nav_row.append(InlineKeyboardButton(text="首页", callback_data=f"eps|{series_name}|1"))
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="上一页", callback_data=f"eps|{series_name}|{page-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"第{page}/{total_pages}页", callback_data="noop"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="下一页", callback_data=f"eps|{series_name}|{page+1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="末页", callback_data=f"eps|{series_name}|{total_pages}"))
    
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="⬅️ 返回目录", callback_data="home|home|1")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)