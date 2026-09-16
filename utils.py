import aiohttp
import logging
from aiogram import types
from aiogram.types import InlineKeyboardMarkup

from config import TON_ADDRESS, TON_API_KEY, TON_RATE_RUB


async def safe_edit(callback: types.CallbackQuery, text: str,
                    keyboard: InlineKeyboardMarkup = None, **kwargs):
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, **kwargs)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=keyboard, **kwargs)


def rub_to_ton(rub: float) -> float:
    return round(rub / TON_RATE_RUB, 3)


async def find_ton_payment(expected_comment: str, expected_ton: float) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://toncenter.com/api/v2/getTransactions"
            params = {"address": TON_ADDRESS, "limit": 100, "archival": "true"}
            headers = {"X-API-Key": TON_API_KEY}
            async with session.get(url, params=params, headers=headers, timeout=15) as resp:
                data = await resp.json()
    except Exception as e:
        logging.exception("TON API error: %s", e)
        return False

    if not data.get('ok'):
        return False

    for tx in data.get('result', []):
        in_msg = tx.get('in_msg', {})
        if in_msg.get('destination') != TON_ADDRESS:
            continue
        comment = (in_msg.get('message') or '').strip()
        if comment != expected_comment:
            continue
        try:
            amount_ton = int(in_msg.get('value', 0)) / 1e9
        except (TypeError, ValueError):
            continue
        if expected_ton > 0 and abs(amount_ton - expected_ton) / expected_ton <= 0.05:
            return True
    return False