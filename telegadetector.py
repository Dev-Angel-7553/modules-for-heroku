# meta developer: @dev_angel_7553

from .. import loader, utils
import requests
import json
import asyncio

CALLS_BASE_URL = "https://calls.okcdn.ru"
CALLS_API_KEY = "CHKIPMKGDIHBABABA"
SESSION_DATA = '{"device_id":"telega_detector","version":2,"client_version":"android_8","client_type":"SDK_ANDROID"}'

WARNING_MESSAGE = """привет.
вижу, что ты используешь telega.

у тебя есть два варианта:

1. удаляешь его прямо сейчас и завершаешь сессию в настройках аккаунта.
2. летишь в чс.

почему — можешь ознакомиться здесь: dontusetelega.lol
если коротко: это не клиент, а дыра, через которую утекает всё, включая переписки. обезопась себя и тех, с кем общаешься.

выявлено ботом"""

@loader.tds
class TelegaDetectorMod(loader.Module):
    """поиск пользователей telega"""
    
    strings = {
        "name": "TelegaDetector",
        "checking": "<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> <b>проверяю диалоги...</b>",
        "not_found": "<tg-emoji emoji-id=6021868492037298942>🛡</tg-emoji> <b>telega не обнаружен</b>",
        "found": "<tg-emoji emoji-id=6019548599812103366>🛡</tg-emoji> <b>найдено пользователей telega: {count}</b>",
        "error": "<tg-emoji emoji-id=6019102674832595118>⚠️</tg-emoji> <b>ошибка при проверке</b>\n\n<code>{error}</code>",
        "sending_start": "<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> <b>отправляю предупреждения...</b>",
        "sending_done": "<tg-emoji emoji-id=6021868492037298942>🛡</tg-emoji> <b>отправлено {sent} пользователям</b>\n<tg-emoji emoji-id=6019102674832595118>⚠️</tg-emoji> <b>не отправлено: {failed}</b>",
        "no_users": "<tg-emoji emoji-id=6021868492037298942>🛡</tg-emoji> <b>пользователи telega не найдены</b>",
    }
    
    strings_ru = {
        "name": "TelegaDetector",
        "checking": "<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> <b>проверяю диалоги...</b>",
        "not_found": "<tg-emoji emoji-id=6021868492037298942>🛡</tg-emoji> <b>telega не обнаружен</b>",
        "found": "<tg-emoji emoji-id=6019548599812103366>🛡</tg-emoji> <b>найдено пользователей telega: {count}</b>",
        "error": "<tg-emoji emoji-id=6019102674832595118>⚠️</tg-emoji> <b>ошибка при проверке</b>\n\n<code>{error}</code>",
        "sending_start": "<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> <b>отправляю предупреждения...</b>",
        "sending_done": "<tg-emoji emoji-id=6021868492037298942>🛡</tg-emoji> <b>отправлено {sent} пользователям</b>\n<tg-emoji emoji-id=6019102674832595118>⚠️</tg-emoji> <b>не отправлено: {failed}</b>",
        "no_users": "<tg-emoji emoji-id=6021868492037298942>🛡</tg-emoji> <b>пользователи telega не найдены</b>",
    }
    
    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        
    def _get_session_key(self):
        try:
            resp = requests.post(
                f"{CALLS_BASE_URL}/api/auth/anonymLogin",
                json={
                    "application_key": CALLS_API_KEY,
                    "session_data": SESSION_DATA
                },
                timeout=10
            )
            data = resp.json()
            return data.get("session_key", "")
        except Exception:
            return ""
            
    def _check_user(self, user_id, session_key):
        try:
            external_ids = json.dumps([{"id": str(user_id), "ok_anonym": False}])
            
            resp = requests.post(
                f"{CALLS_BASE_URL}/api/vchat/getOkIdsByExternalIds",
                json={
                    "application_key": CALLS_API_KEY,
                    "session_key": session_key,
                    "externalIds": external_ids
                },
                timeout=15
            )
            data = resp.json()
            ids = data.get("ids", [])
            
            for item in ids:
                external = item.get("external_user_id", {})
                if str(external.get("id", "")) == str(user_id):
                    return True
            return False
            
        except Exception:
            return False
            
    async def _get_all_users(self):
        users = []
        async for dialog in self._client.iter_dialogs():
            if dialog.is_user:
                if not hasattr(dialog.entity, "bot") or not dialog.entity.bot:
                    users.append(dialog.entity.id)
        return list(set(users))
    
    async def _get_telega_users(self):
        all_users = await self._get_all_users()
        if not all_users:
            return []
            
        session_key = self._get_session_key()
        if not session_key:
            return []
            
        telega_users = []
        
        for user_id in all_users:
            if self._check_user(user_id, session_key):
                telega_users.append(user_id)
            await asyncio.sleep(0.3)
        return telega_users
        
    @loader.command(description="<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> выявить пользователей telega")
    async def telega(self, message):
        """выявить пользователей telega"""
        await utils.answer(message, self.strings("checking"))
        
        try:
            telega_users = await self._get_telega_users()
                
            if not telega_users:
                await utils.answer(message, self.strings("not_found"))
                return
                
            await utils.answer(
                message,
                self.strings("found").format(count=len(telega_users))
            )
            
        except Exception as e:
            await utils.answer(message, self.strings("error").format(error=str(e)))
            
    @loader.command(description="<tg-emoji emoji-id=6025879072368761539>📨</tg-emoji> предупредить пользователей telega")
    async def telegasend(self, message):
        """предупредить пользователей telega"""
        await utils.answer(message, self.strings("sending_start"))
        
        try:
            telega_users = await self._get_telega_users()
                
            if not telega_users:
                await utils.answer(message, self.strings("no_users"))
                return
                
            sent = 0
            failed = 0
            
            for user_id in telega_users:
                try:
                    entity = await self._client.get_entity(user_id)
                    await self._client.send_message(entity, WARNING_MESSAGE)
                    sent += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.5)
                
            await utils.answer(
                message,
                self.strings("sending_done").format(sent=sent, failed=failed)
            )
            
        except Exception as e:
            await utils.answer(message, self.strings("error").format(error=str(e)))