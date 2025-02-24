from html import escape
from urllib.parse import quote

from bot import LOGGER
from bot.core.torrent_manager import TorrentManager
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import edit_message, send_message

PLUGINS = []
TELEGRAPH_LIMIT = 300
SEARCH_PLUGINS = [
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/piratebay.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/limetorrents.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torlock.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentscsv.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/eztv.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentproject.py",
    "https://raw.githubusercontent.com/MaurizioRicci/qBittorrent_search_engines/master/kickass_torrent.py",
    "https://raw.githubusercontent.com/MaurizioRicci/qBittorrent_search_engines/master/yts_am.py",
    "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/linuxtracker.py",
    "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaasi.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/ettv.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/glotorrents.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/thepiratebay.py",
    "https://raw.githubusercontent.com/v1k45/1337x-qBittorrent-search-plugin/master/leetx.py",
    "https://raw.githubusercontent.com/nindogo/qbtSearchScripts/master/magnetdl.py",
    "https://raw.githubusercontent.com/msagca/qbittorrent_plugins/main/uniondht.py",
    "https://raw.githubusercontent.com/khensolomon/leyts/master/yts.py",
]


async def initiate_search_tools():
    qb_plugins = await TorrentManager.qbittorrent.search.plugins()
    if qb_plugins:
        names = [plugin.name for plugin in qb_plugins]
        await TorrentManager.qbittorrent.search.uninstall_plugin(names)
        PLUGINS.clear()
    await TorrentManager.qbittorrent.search.install_plugin(SEARCH_PLUGINS)


async def search(key, site, message):
    LOGGER.info(f"PLUGINS Searching: {key} from {site}")
    search = await TorrentManager.qbittorrent.search.start(
        pattern=key,
        plugins=[site],
        category="all",
    )
    search_id = search.id
    while True:
        result_status = await TorrentManager.qbittorrent.search.status(search_id)
        status = result_status[0].status
        if status != "Running":
            break
    dict_search_results = await TorrentManager.qbittorrent.search.results(
        id=search_id,
        limit=TELEGRAPH_LIMIT,
    )
    search_results = dict_search_results.results
    total_results = dict_search_results.total
    if total_results == 0:
        await edit_message(
            message,
            f"No result found for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i>",
        )
        return
    msg = f"<b>Found {min(total_results, TELEGRAPH_LIMIT)}</b>"
    msg += f" <b>result(s) for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i></b>"
    await TorrentManager.qbittorrent.search.delete(search_id)
    link = await get_result(search_results, key, message)
    buttons = ButtonMaker()
    buttons.url_button("🔎 VIEW", link)
    button = buttons.build_menu(1)
    await edit_message(message, msg, button)


async def get_result(search_results, key, message):
    telegraph_content = []
    msg = f"<h4>PLUGINS Search Result(s) For {key}</h4>"
    for index, result in enumerate(search_results, start=1):
        msg += f"<a href='{result.descrLink}'>{escape(result.fileName)}</a><br>"
        msg += f"<b>Size: </b>{get_readable_file_size(result.fileSize)}<br>"
        msg += f"<b>Seeders: </b>{result.nbSeeders} | <b>Leechers: </b>{result.nbLeechers}<br>"
        link = result.fileUrl
        if link.startswith("magnet:"):
            msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(link)}'>Telegram</a><br><br>"
        else:
            msg += f"<a href='{link}'>Direct Link</a><br><br>"

        if len(msg.encode("utf-8")) > 39000:
            telegraph_content.append(msg)
            msg = ""

        if index == TELEGRAPH_LIMIT:
            break

    if msg != "":
        telegraph_content.append(msg)

    await edit_message(
        message,
        f"<b>Creating</b> {len(telegraph_content)} <b>Telegraph pages.</b>",
    )
    path = [
        (
            await telegraph.create_page(
                title="Mirror-leech-bot Torrent Search",
                content=content,
            )
        )["path"]
        for content in telegraph_content
    ]
    if len(path) > 1:
        await edit_message(
            message,
            f"<b>Editing</b> {len(telegraph_content)} <b>Telegraph pages.</b>",
        )
        await telegraph.edit_telegraph(path, telegraph_content)
    return f"https://telegra.ph/{path[0]}"


async def plugin_buttons(user_id):
    buttons = ButtonMaker()
    if not PLUGINS:
        pl = await TorrentManager.qbittorrent.search.plugins()
        for i in pl:
            PLUGINS.append(i.name)
    for siteName in PLUGINS:
        buttons.data_button(
            siteName.capitalize(),
            f"torser {user_id} {siteName} plugin",
        )
    buttons.data_button("All", f"torser {user_id} all plugin")
    buttons.data_button("Cancel", f"torser {user_id} cancel")
    return buttons.build_menu(2)


@new_task
async def torrent_search(_, message):
    user_id = message.from_user.id
    key = message.text.split()
    if len(key) == 1:
        await send_message(message, "Send a search key along with command")
    else:
        button = await plugin_buttons(user_id)
        await send_message(message, "Choose site to search | Plugins:", button)


@new_task
async def torrent_search_update(_, query):
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(maxsplit=1)
    key = key[1].strip() if len(key) > 1 else None
    data = query.data.split()
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "plugin":
        await query.answer()
        button = await plugin_buttons(user_id)
        await edit_message(message, "Choose site:", button)
    elif data[2] != "cancel":
        await query.answer()
        site = data[2]
        await edit_message(
            message,
            f"<b>Searching for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i></b>",
        )
        await search(key, site, message)
    else:
        await query.answer()
        await edit_message(message, "Search has been canceled!")
