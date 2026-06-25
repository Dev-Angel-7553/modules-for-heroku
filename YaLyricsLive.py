# meta developer: @dev_angel_7553
# name: YaLyricsLive
# description: Живой текст песни с автообновлением
# requires: git+https://github.com/MarshalX/yandex-music-api aiohttp

import asyncio
import re
import json
import random
import string

import aiohttp
import yandex_music
from yandex_music.exceptions import UnauthorizedError, NotFoundError

from .. import loader, utils


@loader.tds
class YaLyricsLive(loader.Module):
    """Живой текст песни с Яндекс.Музыки"""

    strings = {
        "name": "YaLyricsLive",
        "now_playing": "<emoji document_id=5873146865637133757>🎤</emoji> <b>{current}</b>\n\n<emoji document_id=5222108309795908493>✨</emoji> <i>{next}</i>\n\n<b>{artist} — {title}</b>\n<emoji document_id=5213323516832667837>🎵</emoji> <a href='https://music.yandex.ru/track/{track_id}'>Открыть в Яндекс.Музыке</a>",
        "no_lyrics": "<emoji document_id=5422873450786079977>😔</emoji> <b>В этой песне нет синхронизированного текста</b>\n\n<b>{artist} — {title}</b>\n<emoji document_id=5213323516832667837>🎵</emoji> <a href='https://music.yandex.ru/track/{track_id}'>Открыть в Яндекс.Музыке</a>",
        "no_playing": "<emoji document_id=5350496629008917458>🚫</emoji> <b>Сейчас ничего не играет</b>",
        "invalid_token": "❌ <b>Неверный или отсутствует токен</b>\nНастрой: .config YaLyricsLive token твой_токен",
        "end_of_song": "<emoji document_id=5213323516832667837>🎵</emoji> <emoji document_id=5352940967911517739>⏳</emoji> <b>Песня закончилась</b>",
        "loading": "<i>Загружаю живой текст...</i>",
        "stopped": "<emoji document_id=5350342542762209455>😀</emoji> <b>Автообновление остановлено</b>",
        "track_changed": "<emoji document_id=5222108309795908493>✨</emoji> <b>Новая песня! Обновляю текст...</b>",
        "_cls_doc": "Живой текст песни с автообновлением каждые ~2–3 сек",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "token",
                None,
                lambda: "OAuth-токен Яндекс.Музыки. Получи здесь: https://yandex-music.rtfd.io/en/main/token.html",
                validator=loader.validators.Hidden(),
            )
        )
        self.bg_task = None
        self.last_track_id = None
        self.current_lyrics = None

    async def on_unload(self):
        if self.bg_task:
            self.bg_task.cancel()

    @loader.command(ru_doc="Запустить живой текст песни")
    async def ytcmd(self, message):
        token = self.config["token"]
        if not token:
            return await utils.answer(message, self.strings("invalid_token"))

        msg = await utils.answer(message, self.strings("loading"))

        if self.bg_task:
            self.bg_task.cancel()

        self.bg_task = asyncio.create_task(self._lyrics_loop(token, msg))

    @loader.command(ru_doc="Остановить живой текст песни")
    async def ytstopcmd(self, message):
        if self.bg_task:
            self.bg_task.cancel()
            self.bg_task = None
            await utils.answer(message, self.strings("stopped"))
        else:
            await utils.answer(message, "<emoji document_id=5350342542762209455>😀</emoji> Автообновление и так не запущено")

    async def _lyrics_loop(self, token, message):
        last_current = None
        ym = None
        track_info = None

        try:
            ym = await yandex_music.ClientAsync(token).init()
        except UnauthorizedError:
            await utils.answer(message, self.strings("invalid_token"))
            return

        while True:
            try:
                ynison = await self._get_ynison(token)

                queue = ynison.get("player_state", {}).get("player_queue", {})
                if not queue.get("playable_list"):
                    await utils.answer(message, self.strings("no_playing"))
                    break

                idx = queue["current_playable_index"]
                if idx < 0 or idx >= len(queue["playable_list"]):
                    await utils.answer(message, self.strings("no_playing"))
                    break

                raw_track = queue["playable_list"][idx]
                if raw_track.get("playable_type") == "LOCAL_TRACK":
                    await utils.answer(message, self.strings("no_playing"))
                    break

                track_id = raw_track["playable_id"]
                progress_ms = int(ynison["player_state"]["status"]["progress_ms"])
                duration_ms = int(ynison["player_state"]["status"]["duration_ms"])

                if track_id != self.last_track_id:
                    self.last_track_id = track_id
                    track_info = None
                    self.current_lyrics = None
                    last_current = None
                    await utils.answer(message, self.strings("track_changed"))

                if track_info is None:
                    try:
                        track_obj = (await ym.tracks(track_id))[0]
                        track_info = {
                            "title": track_obj.title,
                            "artist": ", ".join(track_obj.artists_name()),
                            "track_id": track_id,
                        }
                    except Exception:
                        track_info = {"title": "Неизвестно", "artist": "Неизвестный артист", "track_id": track_id}

                if progress_ms + 3000 >= duration_ms:
                    await utils.answer(message, self.strings("end_of_song"))
                    await asyncio.sleep(2.5)
                    continue

                if self.current_lyrics is None:
                    try:
                        lyrics_obj = await ym.tracks_lyrics(track_id, "LRC")
                        async with aiohttp.ClientSession() as session:
                            async with session.get(lyrics_obj.download_url) as resp:
                                if resp.status != 200:
                                    raise Exception("Не удалось загрузить текст")
                                self.current_lyrics = await resp.text()
                    except (NotFoundError, Exception):
                        await utils.answer(message, self.strings("no_lyrics").format(**track_info))
                        self.current_lyrics = ""
                        await asyncio.sleep(2.5)
                        continue

                current = ""
                next_line = ""

                for line in self.current_lyrics.splitlines():
                    m = re.match(r"\[(\d+):(\d+\.\d+)\](.*)", line.strip())
                    if not m:
                        continue

                    min_, sec, txt = m.groups()
                    try:
                        ts = (int(min_) * 60 + float(sec)) * 1000
                    except:
                        continue

                    txt = txt.strip()
                    if not txt:
                        continue

                    if ts <= progress_ms:
                        current = txt
                    elif current and not next_line:
                        next_line = txt
                        break

                if not current:
                    await asyncio.sleep(2.5)
                    continue

                if current == last_current:
                    await asyncio.sleep(2.5)
                    continue

                last_current = current

                text = self.strings("now_playing").format(
                    current=current,
                    next=next_line or "конец текста",
                    **track_info
                )

                try:
                    await utils.answer(message, text)
                except Exception:
                    break

                await asyncio.sleep(2.5)

            except Exception:
                await asyncio.sleep(8)

        self.bg_task = None
        self.last_track_id = None
        self.current_lyrics = None

    async def _get_ynison(self, token):
        device_id = "".join(random.choices(string.ascii_lowercase, k=16))
        ws_proto = {
            "Ynison-Device-Id": device_id,
            "Ynison-Device-Info": json.dumps({"app_name": "Chrome", "type": 1}),
        }

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison",
                headers={
                    "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                    "Origin": "https://music.yandex.ru",
                    "Authorization": f"OAuth {token}",
                },
            ) as ws:
                resp = await ws.receive()
                redirect = json.loads(resp.data)

            ws_proto["Ynison-Redirect-Ticket"] = redirect["redirect_ticket"]

            payload = {
                "update_full_state": {
                    "player_state": {
                        "player_queue": {
                            "current_playable_index": -1,
                            "entity_id": "",
                            "entity_type": "VARIOUS",
                            "playable_list": [],
                            "options": {"repeat_mode": "NONE"},
                            "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                            "version": {"device_id": device_id, "version": 9021243204784341000, "timestamp_ms": 0},
                        },
                        "status": {
                            "duration_ms": 0,
                            "paused": True,
                            "playback_speed": 1,
                            "progress_ms": 0,
                            "version": {"device_id": device_id, "version": 8321822175199937000, "timestamp_ms": 0},
                        },
                    },
                    "device": {
                        "capabilities": {"can_be_player": True, "can_be_remote_controller": False, "volume_granularity": 16},
                        "info": {"device_id": device_id, "type": "WEB", "title": "Chrome Browser", "app_name": "Chrome"},
                        "volume_info": {"volume": 0},
                        "is_shadow": True,
                    },
                    "is_currently_active": False,
                },
                "rid": "ac281c26-a047-4419-ad00-e4fbfda1cba3",
                "player_action_timestamp_ms": 0,
                "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT",
            }

            async with session.ws_connect(
                f"wss://{redirect['host']}/ynison_state.YnisonStateService/PutYnisonState",
                headers={
                    "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
                    "Origin": "https://music.yandex.ru",
                    "Authorization": f"OAuth {token}",
                },
            ) as ws:
                await ws.send_str(json.dumps(payload))
                resp = await ws.receive()
                return json.loads(resp.data)
