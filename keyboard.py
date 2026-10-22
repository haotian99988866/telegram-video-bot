from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import config
import database as db


def build_category_menu() -> InlineKeyboardMarkup:
    cats = db.get_all_categories()
    buttons = []
    for cat in cats:
        buttons.append([
            InlineKeyboardButton(
                text=f"📂 {cat}",
                callback_data=f"cat|{cat}|1"
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="📁 全部剧集",
            callback_data="all|all|1"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="🔍 搜索剧集",
            switch_inline_query_current_chat=""
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_series_menu(page: int = 1, list_override=None) -> InlineKeyboardMarkup:
    names = list_override if list_override is not None else db.get_all_series()
    if not names:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="暂无剧集", callback_data="noop")
        ]])
    total_pages = (len(names) - 1) // config.PER_PAGE + 1
    start = (page - 1) * config.PER_PAGE
    page_items = names[start : start + config.PER_PAGE]
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
        nav_row.append(InlineKeyboardButton(
            text="◀️", callback_data=f"all|all|{page-1}"
        ))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="▶️", callback_data=f"all|all|{page+1}"
        ))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(
        text="⬅️ 返回分类",
        callback_data="home|home|1"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_episode_menu(series_name: str, page: int = 1) -> InlineKeyboardMarkup:
    items = db.get_series_display(series_name)
    if not items:
        # ✅ 暂无集数也显示返回按钮
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ 暂无已收录集数", callback_data="noop")],
            [InlineKeyboardButton(text="⬅️ 返回", callback_data="home|home|1")]
        ])

    total_pages = (len(items) - 1) // config.PER_PAGE + 1
    start = (page - 1) * config.PER_PAGE
    page_items = items[start : start + config.PER_PAGE]

    buttons = []
    row = []
    for idx, it in enumerate(page_items):
        ep = it["episode"]
        available = it["available"]
        video_info = it.get("video")
        vid = video_info.get("id") if video_info else 0

        if available and vid:
            btn = InlineKeyboardButton(
                text=f"✅ 第{ep}集",
                callback_data=f"play|{series_name}|{ep}|{vid}"
            )
        else:
            btn = InlineKeyboardButton(
                text=f"⏳ 第{ep}集",
                callback_data="noop"
            )
        row.append(btn)
        if len(row) == 3 or idx == len(page_items) - 1:
            buttons.append(row)
            row = []

    nav_row = [
        InlineKeyboardButton(text="⬅️ 返回", callback_data="home|home|1")
    ]
    if page > 1:
        nav_row.insert(0, InlineKeyboardButton(
            text="◀️", callback_data=f"eps|{series_name}|{page-1}"
        ))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="▶️", callback_data=f"eps|{series_name}|{page+1}"
        ))
    buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)