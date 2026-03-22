#meta developer: @dev_angel_7553
from .. import loader, utils
import re
import asyncio
from io import BytesIO
from math import sqrt
from telethon.tl.functions.payments import GetUniqueStarGiftRequest
from telethon import types

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def extract_slug(text):
    text = text.strip()
    if re.match(r'^[a-zA-Z0-9_-]+$', text):
        return text
    
    patterns = [
        r't\.me/nft/([a-zA-Z0-9_-]+)',
        r'https?://t\.me/nft/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

async def get_gift_data(slug, client):
    try:
        res = await client(GetUniqueStarGiftRequest(slug=slug))
        gift = getattr(res, 'gift', None)
        if not gift:
            return None
        
        gift_data = {
            'slug': slug,
            'title': getattr(gift, 'title', 'Unknown'),
            'number': getattr(gift, 'number', getattr(gift, 'num', '?')),
            'tgs_files': [],
            'image_files': [],
            'bg_colors': None,
        }
        
        for attr in gift.attributes:
            doc = getattr(attr, 'document', None)
            if isinstance(doc, types.Document):
                mime = doc.mime_type or ""
                file_info = {
                    'doc': doc,
                    'mime': mime,
                    'size': doc.size,
                    'id': doc.id
                }
                if "tgsticker" in mime or mime == "application/x-tgsticker":
                    gift_data['tgs_files'].append(file_info)
                elif "image" in mime:
                    gift_data['image_files'].append(file_info)
        
        for attr in gift.attributes:
            if hasattr(attr, 'center_color') and hasattr(attr, 'edge_color'):
                gift_data['bg_colors'] = {
                    'center': attr.center_color,
                    'edge': attr.edge_color
                }
                break
        
        gift_data['tgs_files'].sort(key=lambda x: x['size'], reverse=True)
        return gift_data
    except Exception:
        return None

def hex_to_rgb(color_int):
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return (r, g, b)

def create_circular_background(center_color, edge_color):
    if not HAS_PIL:
        return None
    
    try:
        width, height = 512, 512
        center = hex_to_rgb(center_color)
        edge = hex_to_rgb(edge_color)
        
        img = Image.new('RGB', (width, height))
        center_x, center_y = width // 2, height // 2
        max_radius = sqrt(center_x**2 + center_y**2)
        
        for y in range(height):
            for x in range(width):
                dx = x - center_x
                dy = y - center_y
                distance = sqrt(dx*dx + dy*dy)
                ratio = min(distance / max_radius, 1.0)
                r = int(center[0] * (1 - ratio) + edge[0] * ratio)
                g = int(center[1] * (1 - ratio) + edge[1] * ratio)
                b = int(center[2] * (1 - ratio) + edge[2] * ratio)
                img.putpixel((x, y), (r, g, b))
        
        buffer = BytesIO()
        img.save(buffer, format='WEBP', quality=95)
        buffer.seek(0)
        return buffer
    except Exception:
        return None

@loader.tds
class GiftTools(loader.Module):
    """Модуль для получения модели/паттерна/фона подарка https://github.com/Dev-Angel-7553/modules-for-heroku/blob/main/README.md"""
    
    strings = {"name": "GiftTools"}

    @loader.command(description="<emoji document_id=5332787662803729739>🎁</emoji> Получить все файлы подарка как стикеры и документы: анимированную модель (TGS), статичный паттерн (изображение) и сгенерированный круговой фон. Просто укажи slug или ссылку на подарок.")
    async def giftfullcmd(self, message):
        """ <slug/ссылка>""" 
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "<emoji document_id=5409235172979672859>⚠️</emoji> Укажи slug или ссылку на подарок")
            return
        
        slug = extract_slug(args)
        if not slug:
            await utils.answer(message, "<emoji document_id=5409235172979672859>⚠️</emoji> Не удалось извлечь slug")
            return
        
        gift_data = await get_gift_data(slug, self.client)
        if not gift_data:
            await utils.answer(message, "<emoji document_id=5409235172979672859>⚠️</emoji> Подарок не найден или ошибка")
            return
        
        sent_parts = []
        
        try:
            for i, tgs in enumerate(gift_data['tgs_files']):
                buffer = BytesIO()
                await self.client.download_media(tgs['doc'], buffer)
                buffer.seek(0)
                
                caption = "Модель" if i == 0 else None
                
                await self.client.send_file(
                    message.peer_id,
                    buffer,
                    caption=caption,
                    reply_to=message.reply_to_msg_id,
                    attributes=[
                        types.DocumentAttributeSticker(
                            alt="",
                            stickerset=types.InputStickerSetEmpty(),
                        ),
                        types.DocumentAttributeFilename(f"{slug}_model{i+1 if i > 0 else ''}.tgs")
                    ],
                    mime_type="application/x-tgsticker",
                )
                sent_parts.append("Модель" if i == 0 else f"TGS {i+1}")
                buffer.close()
                await asyncio.sleep(0.6)
            
            for i, img in enumerate(gift_data['image_files']):
                buffer = BytesIO()
                await self.client.download_media(img['doc'], buffer)
                buffer.seek(0)
                
                mime = img['mime']
                ext = ".png" if "png" in mime else ".jpg" if "jpg" in mime else ".webp"
                
                await self.client.send_file(
                    message.peer_id,
                    buffer,
                    caption="Паттерн",
                    reply_to=message.reply_to_msg_id,
                    force_document=True,
                    attributes=[types.DocumentAttributeFilename(f"{slug}_pattern{ext}")]
                )
                sent_parts.append("Паттерн")
                buffer.close()
                await asyncio.sleep(0.5)
            
            if gift_data['bg_colors'] and HAS_PIL:
                colors = gift_data['bg_colors']
                buffer = create_circular_background(colors['center'], colors['edge'])
                if buffer:
                    await self.client.send_file(
                        message.peer_id,
                        buffer,
                        caption="Фон",
                        reply_to=message.reply_to_msg_id,
                        attributes=[
                            types.DocumentAttributeSticker(
                                alt="",
                                stickerset=types.InputStickerSetEmpty(),
                            ),
                            types.DocumentAttributeFilename(f"{slug}_background.webp")
                        ],
                        mime_type="image/webp",
                    )
                    sent_parts.append("Фон")
                    buffer.close()
            
            if sent_parts:
                title = gift_data['title']
                number = gift_data['number']
                final = f"<emoji document_id=5404754074685966817>✅</emoji> Отправлено {len(sent_parts)} элементов\n<emoji document_id=5332787662803729739>🎁</emoji> {title} #{number}\nSlug: {slug}"
                await utils.answer(message, final)
            else:
                await utils.answer(message, "<emoji document_id=5409235172979672859>⚠️</emoji> Не удалось извлечь файлы")
                
        except Exception as e:
            await utils.answer(message, f"<emoji document_id=5409235172979672859>⚠️</emoji> Ошибка: {str(e)}")