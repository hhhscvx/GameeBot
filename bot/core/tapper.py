import asyncio
import json
from pprint import pprint
from urllib.parse import unquote

import aiohttp
from better_proxy import Proxy
from pyrogram.client import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView

from bot.exceptions import InvalidSession
from bot.utils import logger


class Gamee:
    def __init__(self, tg_client: Client) -> None:
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.gamee_url = "https://api.gamee.com/"
        self.uuid_file = "gamee_uuid.json"

    async def get_tg_web_data(self, proxy: str | None):
        if proxy:
            proxy: Proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password,
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('gamee')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f'{self.session_name} | FloodWait {fl}')
                    fls *= 2
                    logger.info(f'{self.session_name} | Sleep {fls}s')

                    await asyncio.sleep(fls)

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=peer,
                bot=peer,
                platform='android',
                from_bot_menu=False,
                url='https://prizes.gamee.com/telegram/watracer'
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0]
            )

            print('auth_url:', auth_url)
            print('tg_web_data:', tg_web_data)

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, tg_web_data: str):
        data = {
            "jsonrpc": "2.0",
            "id": "user.authentication.loginUsingTelegram",
            "method": "user.authentication.loginUsingTelegram",
            "params": {"initData": tg_web_data},
        }
        try:
            response = await http_client.post(url=self.gamee_url, data=json.dumps(data))
            resp_json: dict = await response.json()

            result: dict | None = resp_json.get("result")
            if result is None:
                raise KeyError(f'result not found in response on {self.gamee_url}')

            access_token = result["tokens"]["authenticate"]
            print(f'ACCESS TOKEN: {access_token}')
            return access_token

        except Exception as error:
            logger.error(f'{self.session_name} | Unknown error while getting Access Token: {error}')
