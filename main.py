import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ContentType, UpdateType
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


@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        f"📂 视频目录\n"
        f"共收录 {len(db.series_info)} 部剧集 / {len(db.video_list)} 个视频\n\n"
        f"选择分类浏览，新视频自动同步 ✅",
        reply_markup=build_category_menu()
    )


@dp.message(F.text & ~F.text.startswith("/"))
async def do_search(msg: Message):
    kw = msg.text.strip()
    results = db.search_series_by_keyword(kw)
    if not results:
        await msg.answer(f"🔍 「{kw}」未找到匹配剧集")
        return
    await msg.answer(
        f"🔍 搜索结果：{len(results)} 个匹配\n选择进入：",
        reply_markup=build_series_menu(list_override=results)
    )


# ✅ 核心：用简单字符串拆分，100% 匹配
@dp.callback_query(F.data != "noop")
async def on_nav(cq: CallbackQuery):
    data = cq.data.split("|")
    act = data[0]
    param1 = data[1] if len(data) > 1 else ""
    param2 = int(data[2]) if len(data) > 2 and data[2].isdigit() else 1
    param3 = int(data[3]) if len(data) > 3 and data[3].isdigit() else 0

    print(f"回调: act={act}, p1={param1}, p2={param2}")

    if act == "home":
        await cq.message.edit_text(
            f"📂 视频目录\n"
            f"共收录 {len(db.series_info)} 部剧集 / {len(db.video_list)} 个视频\n\n"
            f"选择分类浏览，新视频自动同步 ✅",
            reply_markup=build_category_menu()
        )
        await cq.answer()
        return

    if act == "cat":
        series_list = get_series_by_category(param1)
        if not series_list:
            await cq.message.edit_text(
                f"📂 {param1}\n暂无内容~",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ 返回", callback_data="home|home|1")
                ]])
            )
            await cq.answer()
            return
        await cq.message.edit_text(
            f"📂 {param1}\n共 {len(series_list)} 部作品",
            reply_markup=build_series_menu(list_override=series_list)
        )
        await cq.answer()
        return

    if act == "all":
        await cq.message.edit_text(
            "📁 全部剧集",
            reply_markup=build_series_menu(page=param2)
        )
        await cq.answer()
        return

    if act == "eps":
        await cq.message.edit_text(
            f"📺 {param1}\n选择集数：",
            reply_markup=build_episode_menu(param1, page=param2)
        )
        await cq.answer()
        return

    if act == "play":
        video = db.get_video_by_id(param3)
        if not video or not video.get("file_id"):
            await cq.answer("该集暂未收录，请等待更新", show_alert=True)
            return
        await cq.message.answer_video(
            video=video["file_id"],
            caption=(
                f"📺 {video['series']} 第{video['episode']}集\n"
                f"📹 {video['title']}\n"
                f"⏱ 时长：{video['duration']//60}:{video['duration']%60:02d}"
            )
        )
        await cq.answer("播放已开始 ✅")
        return


@dp.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer("该集尚未更新，请等待上传", show_alert=True)


@dp.message(Command("reload"))
async def reload_cmd(msg: Message):
    if msg.from_user.id != config.ADMIN_ID:
        await msg.answer("❌ 无权限")
        return
    db.load_data()
    await msg.answer("✅ 目录已重新加载")


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
