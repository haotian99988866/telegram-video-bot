import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ContentType, UpdateType
from aiogram.types import InputMediaVideo
from config import config
import database as db
from keyboard import build_series_menu, build_episode_menu, build_category_menu
from database import get_series_by_category

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="Markdown")
)
dp = Dispatcher()

TARGET_CHANNEL_ID = config.CHANNEL_ID
if TARGET_CHANNEL_ID.startswith("-"):
    TARGET_CHANNEL_ID = int(TARGET_CHANNEL_ID)

# 保存用户菜单消息ID —— 全程复用一条，不新增
user_menu_msg: dict[int, int] = {}


async def process_new_video_message(msg: Message):
    title = (msg.caption or "").strip() or f"视频 {msg.message_id}"
    file_id = msg.video.file_id
    duration = msg.video.duration or 0
    
    added = db.add_video(
        message_id=msg.message_id,
        title=title,
        file_id=file_id,
        duration=duration,
        file_name=getattr(msg.video, "file_name", ""),
        size=getattr(msg.video, "file_size", 0)
    )
    
    if added and config.ADMIN_ID:
        series = added["series"]
        ep = added["episode"]
        total = db.series_info.get(series, {}).get("total", ep or 1)
        await bot.send_message(
            config.ADMIN_ID,
            f"✅ 自动收录成功\n"
            f"📺 剧名：{series}\n"
            f"📝 集数：第{ep}集 / 共{total}集\n"
            f"📹 标题：{added['title']}\n"
            f"⏱ 时长：{duration//60}:{duration%60:02d}\n"
            f"🔗 目录已实时刷新，用户可直接播放"
        )


@dp.message(F.chat.id == TARGET_CHANNEL_ID, F.content_type == ContentType.VIDEO)
async def on_channel_video_message(msg: Message):
    await process_new_video_message(msg)


@dp.channel_post(F.chat.id == TARGET_CHANNEL_ID, F.content_type == ContentType.VIDEO)
async def on_channel_video_post(msg: Message):
    await process_new_video_message(msg)


# ========== 固定菜单核心：删旧发新，永远在最底部 ==========
async def update_fixed_menu(user_id: int, text: str, reply_markup=None):
    if user_id in user_menu_msg:
        try:
            await bot.delete_message(chat_id=user_id, message_id=user_menu_msg[user_id])
        except Exception:
            pass
    
    new_msg = await bot.send_message(user_id, text, reply_markup=reply_markup)
    user_menu_msg[user_id] = new_msg.message_id


@dp.message(CommandStart())
async def cmd_start(msg: Message):
    text = (
        f"📂 视频目录\n"
        f"共收录 {len(db.series_info)} 部剧集 / {len(db.video_list)} 个视频\n\n"
        f"选择分类浏览，新视频自动同步 ✅"
    )
    
    # 删掉用户输入的 /start，不留痕迹
    try:
        await msg.delete()
    except Exception:
        pass
    
    await update_fixed_menu(msg.from_user.id, text, reply_markup=build_category_menu())


@dp.message(F.text & ~F.text.startswith("/"))
async def do_search(msg: Message):
    kw = msg.text.strip()
    results = db.search_series_by_keyword(kw)
    
    # 删掉搜索文字
    try:
        await msg.delete()
    except Exception:
        pass
    
    if not results:
        hint = await msg.answer(f"🔍 「{kw}」未找到匹配剧集")
        await asyncio.sleep(2)
        try:
            await hint.delete()
        except Exception:
            pass
        return
    
    text = f"🔍 搜索结果：{len(results)} 个匹配\n选择进入："
    await update_fixed_menu(msg.from_user.id, text, reply_markup=build_series_menu(list_override=results))
    await msg.answer("")  # 空 = 收键盘 + 不弹窗 ✅


@dp.callback_query(F.data != "noop")
async def on_nav(cq: CallbackQuery):
    data = cq.data.split("|")
    act = data[0]
    param1 = data[1] if len(data) > 1 else ""
    param2 = int(data[2]) if len(data) > 2 and data[2].isdigit() else 1
    param3 = int(data[3]) if len(data) > 3 and data[3].isdigit() else 0
    
    user_id = cq.from_user.id
    print(f"回调: act={act}, p1={param1}, p2={param2}")

    if act == "home":
        text = (
            f"📂 视频目录\n"
            f"共收录 {len(db.series_info)} 部剧集 / {len(db.video_list)} 个视频\n\n"
            f"选择分类浏览，新视频自动同步 ✅"
        )
        await update_fixed_menu(user_id, text, reply_markup=build_category_menu())
        await cq.answer("")  # 不弹窗、只收键盘 ✅
        return

    if act == "cat":
        series_list = get_series_by_category(param1)
        if not series_list:
            text = f"📂 {param1}\n暂无内容~"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ 返回", callback_data="home|home|1")
            ]])
        else:
            text = f"📂 {param1}\n共 {len(series_list)} 部作品"
            kb = build_series_menu(list_override=series_list)
        await update_fixed_menu(user_id, text, reply_markup=kb)
        await cq.answer("")
        return

    if act == "all":
        text = "📁 全部剧集"
        await update_fixed_menu(user_id, text, reply_markup=build_series_menu(page=param2))
        await cq.answer("")
        return

    if act == "eps":
        text = f"📺 {param1}\n选择集数："
        await update_fixed_menu(user_id, text, reply_markup=build_episode_menu(param1, page=param2))
        await cq.answer("")
        return

    if act == "play":
        video = db.get_video_by_id(param3)
        
        if not video or not video.get("file_id"):
            await cq.answer("", show_alert=True)  # 真正错误时才弹窗
            return
        
        await cq.message.edit_media(
            media=InputMediaVideo(
                media=video["file_id"],
                caption=(
                    f"📺 {video['series']} 第{video['episode']}集\n"
                    f"📹 {video['title']}\n"
                    f"⏱ 时长：{video['duration']//60}:{video['duration']%60:02d}"
                )
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="◀ 返回目录",
                    callback_data=f"eps|{param1}|1"
                )
            ]])
        )
        await cq.answer("")  # 播放成功不弹窗
        return


@dp.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer("", show_alert=True)


@dp.message(Command("reload"))
async def reload_cmd(msg: Message):
    if msg.from_user.id != config.ADMIN_ID:
        await msg.answer("❌ 无权限")
        return
    db.load_data()
    await update_fixed_menu(
        msg.from_user.id,
        f"✅ 目录已重新加载\n"
        f"共收录 {len(db.series_info)} 部剧集 / {len(db.video_list)} 个视频",
        reply_markup=build_category_menu()
    )
    await msg.answer("")


async def main():
    if not config.BOT_TOKEN or not config.CHANNEL_ID:
        print("❌ 请检查环境变量：BOT_TOKEN / CHANNEL_ID 必填")
        return
    print(f"🤖 启动成功，监听频道: {config.CHANNEL_ID}")
    await dp.start_polling(
        bot,
        allowed_updates=[
            UpdateType.MESSAGE,
            UpdateType.CALLBACK_QUERY,
            UpdateType.CHANNEL_POST
        ]
    )


if __name__ == "__main__":
    asyncio.run(main())