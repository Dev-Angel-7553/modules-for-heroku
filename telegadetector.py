# meta developer: @dev_angel_7553
__version__ = (1, 1)
from .. import loader, utils
import requests
import json
import asyncio
import io

CALLS_BASE_URL = "https://calls.okcdn.ru"
CALLS_API_KEY = "CHKIPMKGDIHBABABA"
SESSION_DATA = '{"device_id":"telega_detector","version":2,"client_version":"android_8","client_type":"SDK_ANDROID"}'

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
        "chat_checking": "<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> <b>сканирую чат...</b>",
        "chat_result": "<tg-emoji emoji-id=6019548599812103366>🛡</tg-emoji> <b>найдено в чате: {count}</b>",
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
        "chat_checking": "<tg-emoji emoji-id=6025879072368761539>🎯</tg-emoji> <b>сканирую чат...</b>",
        "chat_result": "<tg-emoji emoji-id=6019548599812103366>🛡</tg-emoji> <b>найдено в чате: {count}</b>",
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
    
    async def _get_chat_users(self, chat_id):
        users = []
        async for member in self._client.iter_participants(chat_id):
            if not member.bot and not member.is_self:
                users.append(member)
        return users
    
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
        
    async def _get_telega_chat_users(self, chat_users):
        session_key = self._get_session_key()
        if not session_key:
            return []
            
        telega_users = []
        
        for user in chat_users:
            if self._check_user(user.id, session_key):
                telega_users.append(user)
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
    
    @loader.command(description="<tg-emoji emoji-id=6025879072368761539>👥</tg-emoji> проверить участников чата на telega")
    async def telegachat(self, message):
        """проверить участников чата на telega"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if reply:
            chat = reply.chat_id
        elif args:
            try:
                chat = int(args)
            except ValueError:
                chat = args
        else:
            chat = message.chat_id
            
        await utils.answer(message, self.strings("chat_checking"))
        
        try:
            chat_entity = await self._client.get_entity(chat)
            chat_users = await self._get_chat_users(chat_entity.id)
            
            if not chat_users:
                await utils.answer(message, self.strings("no_users"))
                return
                
            telega_users = await self._get_telega_chat_users(chat_users)
            
            if not telega_users:
                await utils.answer(message, self.strings("not_found"))
                return
                
            result_text = ""
            for user in telega_users:
                name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
                name = name.strip() or "No Name"
                username = f"@{user.username}" if user.username else "@no_username"
                result_text += f"{user.id} {name} {username}\n"
            
            file = io.BytesIO(result_text.encode("utf-8"))
            file.name = "telega_users.txt"
            
            await message.client.send_file(
                "me",
                file,
                caption=self.strings("chat_result").format(count=len(telega_users))
            )
            
            await utils.answer(message, self.strings("chat_result").format(count=len(telega_users)))
            
        except Exception as e:
            await utils.answer(message, self.strings("error").format(error=str(e)))
