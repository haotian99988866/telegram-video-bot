from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from config import config
import database as db

class Nav(CallbackData, prefix="nav"):
    act: str
    name: str = ""
    page: int = 1
    ep: int = 0
    vid: int = 0

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
                callback_data=Nav(act="eps", name=name, page=1).pack()
            )
        ])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(
            "◀️", callback_data=Nav(act="series", page=page - 1).pack()
        ))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            "▶️", callback_data=Nav(act="series", page=page + 1).pack()
        ))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(
        "🔍 搜索剧集", switch_inline_query_current_chat=""
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_episode_menu(series_name: str, page: int = 1) -> InlineKeyboardMarkup:
    items = db.get_series_display(series_name)
    if not items:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="暂无集数", callback_data="noop")
        ]])
    total_pages = (len(items) - 1) // config.PER_PAGE + 1
    start = (page - 1) * config.PER_PAGE
    page_items = items[start : start + config.PER_PAGE]

    buttons = []
    row = []
    for idx, it in enumerate(page_items):
        ep = it["episode"]
        if it["available"]:
            btn = InlineKeyboardButton(
                text=f"✅ 第{ep}集",
                callback_data=Nav(act="play", name=series_name, ep=ep, vid=it["video"]["id"]).pack()
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
        InlineKeyboardButton(
            "📂 返回", callback_data=Nav(act="series", page=1).pack()
        )
    ]
    if page > 1:
        nav_row.insert(0, InlineKeyboardButton(
            "◀️", callback_data=Nav(act="eps", name=series_name, page=page - 1).pack()
        ))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            "▶️", callback_data=Nav(act="eps", name=series_name, page=page + 1).pack()
        ))
    buttons.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)