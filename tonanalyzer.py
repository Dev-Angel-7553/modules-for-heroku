#meta developer: @dev_angel_7553

import time
import asyncio
import aiohttp

from .. import loader, utils
from herokutl.tl.types import Message


@loader.tds
class TonAnalyzer(loader.Module):
    """Анализ оборота TON в кошельке"""

    strings = {"name": "TonAnalyzer"}

    strings_ru = {
        "no_key": (
            "<b>API ключ не задан!</b>\n\n"
            "Получи бесплатный ключ у <a href='https://t.me/tonapibot'>@tonapibot</a> "
            "в боте, затем пропиши:\n"
            "<code>.cfg TonAnalyzer</code> поле <b>api_key</b>"
        ),
        "no_addr": "Укажи адрес: <code>.tonscan UQ...</code>",
        "not_found": "Транзакций не найдено",
        "err": "<b>Ошибка:</b> <code>{}</code>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                "",
                "API ключ от @tonapibot.",
                validator=loader.validators.Hidden(),
            )
        )

    BASE_URL = "https://toncenter.com/api/v3"
    LIMIT = 256
    MIN_VAL = 10_000_000

    def nano_to_ton(self, nano) -> float:
        return int(nano or 0) / 1e9

    def usd_str(self, ton: float, price: float) -> str:
        if price <= 0 or ton < 0.001:
            return ""
        return f"≈ <b>${ton * price:,.2f}</b>"

    def _headers(self):
        h = {}
        if self.config["api_key"]:
            h["X-Api-Key"] = self.config["api_key"]
        return h

    async def fetch_transactions(self, session, address: str, form):
        all_txs = []
        offset = 0
        while True:
            params = {"account": address, "limit": self.LIMIT, "offset": offset, "sort": "desc"}
            async with session.get(
                f"{self.BASE_URL}/transactions",
                params=params, headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
            if "transactions" not in data:
                raise Exception(data.get("error") or str(data)[:200])
            batch = data["transactions"]
            if not batch:
                break
            all_txs.extend(batch)
            if len(batch) < self.LIMIT:
                break
            offset += len(batch)
            
            # Меняем старое сообщение через form.edit() вместо повторного вызова self.inline.form
            await form.edit(
                text=(
                    f'<tg-emoji emoji-id="5350773074578916842">🙏</tg-emoji> '
                    f"<b>Загружено:</b> {len(all_txs)} транзакций...\n"
                ),
                reply_markup=[[{"text": "Закрыть", "action": "close", "style": "danger"}]]
            )
            await asyncio.sleep(0.15)
        return all_txs

    async def fetch_ton_price(self, session) -> float:
        try:
            async with session.get(
                "https://tonapi.io/v2/rates?tokens=ton&currencies=usd",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
            return float(data["rates"]["TON"]["prices"]["USD"])
        except Exception:
            return 0.0

    @loader.command()
    async def tonscan(self, message: Message):
        """<адрес> — полный оборот GRAM кошелька"""

        if not self.config["api_key"]:
            await self.inline.form(
                message=message,
                text=self.strings_ru["no_key"],
                reply_markup=[[{"text": "Закрыть", "action": "close", "style": "danger"}]]
            )
            return

        address = utils.get_args_raw(message)
        if not address:
            await self.inline.form(
                message=message,
                text=self.strings_ru["no_addr"],
                reply_markup=[[{"text": "Закрыть", "action": "close", "style": "danger"}]]
            )
            return

        address = address.strip()
        
        # Создаем начальную инлайн-форму
        form = await self.inline.form(
            message=message,
            text=(
                f'<b>Загружаю транзакции...</b>\n'
                f"<code>{address}</code>"
            ),
            reply_markup=[[{"text": "Закрыть", "action": "close", "style": "danger"}]]
        )

        try:
            async with aiohttp.ClientSession() as session:
                all_txs, ton_price_usd = await asyncio.gather(
                    self.fetch_transactions(session, address, form),
                    self.fetch_ton_price(session),
                )
        except Exception as e:
            await form.edit(
                text=self.strings_ru["err"].format(utils.escape_html(str(e))),
                reply_markup=[[{"text": "Закрыть", "action": "close", "style": "danger"}]]
            )
            return

        if not all_txs:
            await form.edit(
                text=self.strings_ru["not_found"],
                reply_markup=[[{"text": "Закрыть", "action": "close", "style": "danger"}]]
            )
            return

        total_in = 0
        total_out = 0
        count_in = 0
        count_out = 0
        fees_total = 0

        for tx in all_txs:
            in_msg = tx.get("in_msg") or {}
            out_msgs = tx.get("out_msgs") or []
            in_val = int(in_msg.get("value") or 0)
            if in_val >= self.MIN_VAL:
                total_in += in_val
                count_in += 1
            for m in out_msgs:
                out_val = int(m.get("value") or 0)
                if out_val >= self.MIN_VAL:
                    total_out += out_val
                    count_out += 1
            fees_total += int(tx.get("total_fees") or 0)

        ton_in = self.nano_to_ton(total_in)
        ton_out = self.nano_to_ton(total_out)
        ton_fees = self.nano_to_ton(fees_total)

        recent_lines = []
        for tx in all_txs:
            if len(recent_lines) >= 10:
                break
            in_msg = tx.get("in_msg") or {}
            out_msgs = tx.get("out_msgs") or []
            in_val = int(in_msg.get("value") or 0)
            out_val = sum(int(m.get("value") or 0) for m in out_msgs)

            if in_val < self.MIN_VAL and out_val < self.MIN_VAL:
                continue

            ts = tx.get("now") or tx.get("utime") or 0
            dt = time.strftime("%d.%m.%y %H:%M", time.localtime(ts))

            if in_val >= self.MIN_VAL:
                usd = self.usd_str(in_val / 1e9, ton_price_usd)
                src = (in_msg.get("source") or "—")[:16]
                recent_lines.append(
                    f'  <tg-emoji emoji-id="5350700390847365132">⏬</tg-emoji> '
                    f"<code>+{in_val/1e9:.3f}</code> GRAM {usd}\n"
                    f"      {dt} · <code>{src}</code>"
                )

            if out_val >= self.MIN_VAL:
                dst = (out_msgs[0].get("destination") or "—")[:16] if out_msgs else "—"
                usd = self.usd_str(out_val / 1e9, ton_price_usd)
                recent_lines.append(
                    f'  <tg-emoji emoji-id="5350305520144106741">⏫</tg-emoji> '
                    f"<code>-{out_val/1e9:.3f}</code> GRAM {usd}\n"
                    f"      {dt} · <code>{dst}</code>"
                )

        recent_block = "\n\n".join(recent_lines) if recent_lines else "  —"

        price_line = (
            f'\n<tg-emoji emoji-id="5350815453021234828">💱</tg-emoji> '
            f"<b>Курс GRAM:</b> <code>${ton_price_usd:,.2f}</code>"
            if ton_price_usd > 0 else ""
        )

        # Выводим финальный результат в ту же самую форму
        await form.edit(
            text=(
                f'<tg-emoji emoji-id="5350613306090482956">📊</tg-emoji> <b>Статистика кошелька</b>\n'
                f"<code>{address}</code>"
                f"{price_line}\n\n"
                f'<blockquote><tg-emoji emoji-id="5350700390847365132">⏬</tg-emoji> <b>Пришло:</b>\n'
                f"  <code>+{ton_in:.4f}</code> GRAM  {self.usd_str(ton_in, ton_price_usd)}\n"
                f"  ({count_in} транзакций)</blockquote>\n"
                f'<blockquote><tg-emoji emoji-id="5350305520144106741">⏫</tg-emoji> <b>Ушло:</b>\n'
                f"  <code>-{ton_out:.4f}</code> GRAM  {self.usd_str(ton_out, ton_price_usd)}\n"
                f"  ({count_out} транзакций)</blockquote>\n"
                f'<tg-emoji emoji-id="5280479668422610048">⚜️</tg-emoji> <b>Комиссии:</b>\n'
                f"  <code>-{ton_fees:.4f}</code> GRAM  {self.usd_str(ton_fees, ton_price_usd)}\n\n"
                f'<tg-emoji emoji-id="5350613306090482956">📊</tg-emoji> '
                f"<b>Всего транзакций:</b> {len(all_txs)}"
                f"\n\n"
                f'<tg-emoji emoji-id="5350667865060043135">💼</tg-emoji> <b>Последние операции:</b>\n'
                f"<blockquote expandable>{recent_block}</blockquote>"
            ),
            reply_markup=[
                [
                    {
                        "text": "Закрыть",
                        "action": "close",
                        "style": "danger",
                    }
                ]
            ]
        )
