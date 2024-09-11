import asyncio
import json
from pprint import pprint
from random import random
from urllib.parse import unquote

import aiohttp
from better_proxy import Proxy
from pyrogram.client import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView

from bot.exceptions import InvalidSession
from bot.utils import logger
from bot.config import settings


class Gamee:
    def __init__(self, tg_client: Client) -> None:
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.gamee_url = "https://api.gamee.com/"
        self.uuid_file = "gamee_uuid.json"
        self.event_id = 26

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

            await self.tg_client.send_message('gamee', f'/start {settings.REF_CODE}')
            await asyncio.sleep(random() + 1)

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

    async def login(self, http_client: aiohttp.ClientSession, tg_web_data: str) -> str:
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

            access_token: str = result["tokens"]["authenticate"]
            print(f'ACCESS TOKEN: {access_token}')
            return access_token

        except Exception as error:
            logger.error(f'{self.session_name} | Unknown error while getting Access Token: {error}')

    async def spin(self, http_client: aiohttp.ClientSession) -> tuple[str]:
        """Бля тут недоделанная хуйня, надо подредачить будет как у akasakaid. а еще на тикеты купить спин и чекнуть запрос"""
        try:
            daily_get_prizes = {
                "jsonrpc": "2.0",
                "id": "dailyReward.getPrizes",
                "method": "dailyReward.getPrizes",
                "params": {},
            }

            daily_claim_prizes = {
                "jsonrpc": "2.0",
                "id": "dailyReward.claimPrize",
                "method": "dailyReward.claimPrize",
                "params": {},
            }

            buy_spin_using_ticket = {
                "jsonrpc": "2.0",
                "id": "dailyReward.buySpinUsingTickets",
                "method": "dailyReward.buySpinUsingTickets",
                "params": {},
            }

            resp = await http_client.post(self.gamee_url, data=json.dumps(daily_get_prizes))

            resp_json: dict = await resp.json()

            daily_result: dict | None = resp_json.get("result")
            if daily_result is None:
                logger.error(f"{self.session_name} | result is None")
                return False

            daily_reward: dict = daily_result.get("dailyReward")
            daily_spin = daily_reward.get("spinsCountAvailable")
            spin_using_ticket_price = daily_reward.get("dailyRewardBonusSpinsPriceTickets")

            user_tickets = resp_json['user']['tickets']['count']

            if daily_spin > 0:
                for _ in range(daily_spin):
                    resp = await http_client.post(self.gamee_url, data=json.dumps(daily_claim_prizes))
                    resp_json = await resp.json()

                    reward_type = resp_json['result']['reward']['type']
                    key = "usdCents" if reward_type == "money" else reward_type
                    reward = resp_json['result']['reward'][key]

                    logger.success(f'{self.session_name} | Successfully spinned! | '
                                   f'Earned: <c>{reward}</c> | Type: <e>{reward_type}</e>')
            if settings.USE_TICKETS_TO_SPIN is False:
                return

            while True:  # todo: бля это все по хорошему в run вынести
                if spin_using_ticket_price < user_tickets:
                    logger.info(
                        f'{self.session_name} | Not enough tickets for spin ({user_tickets} / {spin_using_ticket_price})')
                    return
                if spin_using_ticket_price > settings.MAX_USE_TICKETS_TO_SPIN:
                    logger.info(f'{self.session_name} | Price to spin by tickets too high ({spin_using_ticket_price})')
                    return

                await http_client.post(self.gamee_url, data=json.dumps(buy_spin_using_ticket))
                resp = await http_client.post(self.gamee_url, data=json.dumps(daily_claim_prizes))
                resp_json = await resp.json()

                reward_type = resp_json["result"]["reward"]["type"]
                key = "usdCents" if reward_type == "money" else reward_type
                reward = resp_json["result"]["reward"][key]
                logger.info(f"{self.session_name} | Earned by spin : {reward} {reward_type}")

                resp = await http_client.post(
                    self.gamee_url,
                    json.dumps(daily_get_prizes),
                )
                resp_json = await resp.json()

                result = resp_json.get("result")
                daily_reward = result.get("dailyReward")
                daily_spin = daily_reward.get("spinsCountAvailable")
                spin_using_ticket_price = daily_reward.get(
                    "dailyRewardBonusSpinsPriceTickets"
                )
                
                tickets = resp_json["user"]["tickets"]["count"]
                logger.info(f"{self.session_name} | Available tickets: {tickets}")
                logger.info(
                    f"{self.session_name} | Price to spin: {spin_using_ticket_price} tickets"
                )

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error on Spin: {error}")
            await asyncio.sleep(delay=3)

    async def start_mining(self, http_client: aiohttp.ClientSession):
        ...

    async def claim_mining(self, http_client: aiohttp.ClientSession):
        data_claim_mining = {
            "jsonrpc": "2.0",
            "id": "miningEvent.claim",
            "method": "miningEvent.claim",
            "params": {
                "miningEventId": self.event_id,
            },
        }
