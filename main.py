import asyncio
import json
from urllib.parse import unquote
import uuid

import aiofiles
from aiohttp import ClientSession
from pyrogram import Client
from fake_useragent import UserAgent

from bot.core.registrator import register_sessions
from bot.core.tapper import Gamee
from bot.core.headers import headers
from bot.config import settings


async def main():
    # await register_sessions()
    tg_client = Client(
        name='test_main',
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        workdir="sessions/"
    )
    await tg_client.start()
    gamee = Gamee(tg_client=tg_client)

    tg_web_data = await gamee.get_tg_web_data(proxy=None)
    tg_web_data_res = unquote(string=tg_web_data)
    print('tg_web_data_res:', tg_web_data_res)
    user_id = tg_web_data_res.split('id":', maxsplit=1)[1].split(',"first_name', maxsplit=1)[0]
    print('user_id:', user_id)

    async with aiofiles.open(gamee.uuid_file) as uuidr:
        uuids: dict = json.loads(await uuidr.read())

    uuuid = uuids.get(user_id)
    if uuuid is None:
        print('uuuid is None')
        uuuid = uuid.uuid4().__str__()
        uuids[user_id] = uuuid
        async with aiofiles.open(gamee.uuid_file, "w") as uw:
            await uw.write(json.dumps(uuids))

    headers['X-Install-Uuid'] = uuuid
    headers['User-Agent'] = UserAgent(os='android').random

    http_client = ClientSession(headers=headers)
    try:
        access_token = await gamee.login(http_client=http_client, tg_web_data=tg_web_data)
        headers['Authorization'] = f'Bearer {access_token}'
    finally:
        await http_client.close()
    await tg_client.stop()


if __name__ == "__main__":
    asyncio.run(main())
