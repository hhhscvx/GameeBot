import asyncio
import json
from pprint import pprint
from random import randint, random, uniform
from time import time
from urllib.parse import unquote
import uuid

import aiofiles
import aiohttp
from better_proxy import Proxy
from pyrogram.client import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView
from aiohttp_proxy import ProxyConnector
from fake_useragent import UserAgent

from bot.exceptions import InvalidSession
from bot.utils import logger
from bot.config import settings
from .headers import headers


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

            await self.tg_client.send_message('gamee', '/start')
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

            resp = await http_client.post(url=self.gamee_url, data=json.dumps(daily_get_prizes))

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
                    resp = await http_client.post(url=self.gamee_url, data=json.dumps(daily_claim_prizes))
                    resp_json = await resp.json()

                    reward_type = resp_json['result']['reward']['type']
                    key = "usdCents" if reward_type == "money" else reward_type
                    reward = resp_json['result']['reward'][key]

                    logger.success(f'{self.session_name} | Successfully spinned! | '
                                   f'Earned: <c>{reward}</c> | Type: <e>{reward_type}</e>')
            if settings.USE_TICKETS_TO_SPIN is False:
                return

            while True:
                if spin_using_ticket_price > user_tickets:
                    logger.info(
                        f'{self.session_name} | Not enough tickets for spin ({user_tickets} / {spin_using_ticket_price})')
                    return
                if spin_using_ticket_price > settings.MAX_USE_TICKETS_TO_SPIN:
                    logger.info(f'{self.session_name} | Price to spin by tickets too high ({spin_using_ticket_price})')
                    return

                await http_client.post(url=self.gamee_url, data=json.dumps(buy_spin_using_ticket))
                resp = await http_client.post(url=self.gamee_url, data=json.dumps(daily_claim_prizes))
                resp_json = await resp.json()

                reward_type = resp_json["result"]["reward"]["type"]
                key = "usdCents" if reward_type == "money" else reward_type
                reward = resp_json["result"]["reward"][key]
                logger.info(f"{self.session_name} | Earned by spin : {reward} {reward_type}")

                resp = await http_client.post(
                    url=self.gamee_url,
                    data=json.dumps(daily_get_prizes),
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

    async def claim_mining(self, http_client: aiohttp.ClientSession):
        try:
            data = {
                "jsonrpc": "2.0",
                "id": "user.getActivities",
                "method": "user.getActivities",
                "params": {"filter": "all", "pagination": {"offset": 0, "limit": 100}},
            }
            print('Http Client headers:')
            pprint(dict(http_client.headers))
            resp = await http_client.post(
                url=self.gamee_url,
                data=json.dumps(data),
            )
            resp.raise_for_status()

            resp_json = await resp.json()
            pprint(resp_json)
            result = resp_json.get("result")
            if result is None:
                logger.error(f"{self.session_name} | Result not found in user activities")
                return False
            activities = result["activities"]
            for activity in activities:
                activity_id = activity["id"]
                activity_type = activity["type"]
                is_claim = activity["isClaimed"]
                if is_claim:
                    logger.info(f"{self.session_name} | Claimed activity {activity_type}")
                    continue

                logger.info(f"{self.session_name} | Activity to claim: {activity_type}")
                rewards = activity["rewards"]
                virtual_token = rewards["virtualTokens"]
                for token in virtual_token:
                    name = token["currency"]["ticker"]
                    amount = token["amountMicroToken"] / 1000000
                    data = {
                        "jsonrpc": "2.0",
                        "id": "user.claimActivity",
                        "method": "user.claimActivity",
                        "params": {"activityId": activity_id},
                    }
                    resp = await http_client.post(
                        url=self.gamee_url,
                        data=json.dumps(data),
                    )
                    if resp.status != 200:
                        logger.error(f"{self.session_name} | Error when claiming mining reward! (status code 200)")
                        continue
                    logger.success(f"{self.session_name} | Successfully claimed {amount} {name} !")
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when claiming mining: {error}")
            await asyncio.sleep(delay=3)

    async def start_mining(self, http_client: aiohttp.ClientSession):
        try:
            event_id = 26
            data = {
                "jsonrpc": "2.0",
                "id": "miningEvent.get",
                "method": "miningEvent.get",
                "params": {
                    "miningEventId": event_id,
                },
            }
            data_start_mining = {
                "jsonrpc": "2.0",
                "id": "miningEvent.startSession",
                "method": "miningEvent.startSession",
                "params": {"miningEventId": event_id},
            }

            resp = await http_client.post(
                url=self.gamee_url,
                data=json.dumps(data),
            )
            resp_json = await resp.json()
            assets = resp_json["user"]["assets"]
            for asset in assets:
                currency = asset["currency"]["ticker"]
                amount = asset["amountMicroToken"] / 1000000
                logger.info(f"{self.session_name} | Balance: {amount} {currency}")

            mining = resp_json["result"]["miningEvent"]["miningUser"]
            if mining is None:
                logger.info(f"{self.session_name} | Mining not started")
                while True:
                    resp = await http_client.post(
                        url=self.gamee_url,
                        data=json.dumps(data_start_mining),
                    )
                    resp_json = await resp.json()
                    if "error" in resp_json.keys():
                        await asyncio.sleep(2)
                        continue

                    if "miningEvent" in resp_json["result"]:
                        logger.success(f"{self.session_name} | Mining start successfully!")
                        return
            end = mining["miningSessionEnded"]
            earn = mining["currentSessionMicroToken"] / 1000000
            mine = mining["currentSessionMicroTokenMined"] / 1000000
            total_mine = mining["cumulativeMicroTokenMined"] / 1000000

            logger.info(f"{self.session_name} | Total mining: {total_mine}")
            logger.info(f"{self.session_name} | Max mining: {earn}")
            logger.info(f"{self.session_name} | Current mining: {mine}")

            if end:
                logger.info(f"{self.session_name} | Mining has end!")
                while True:
                    resp = await http_client.post(
                        url=self.gamee_url,
                        data=json.dumps(data_start_mining),
                    )
                    resp_json = await resp.json()
                    result = resp_json["result"]
                    error = resp_json.get("error")
                    if error is not None:
                        msg = error.get("message").lower()
                        if msg == "mining session in progress.":
                            logger.info(f"{self.session_name} | Mining in progress")
                            return
                        await asyncio.sleep(2)
                        continue

                    if result.get("miningEvent") is not None:
                        logger.success(f"{self.session_name} | Mining start successfully!")
                        return

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when claiming mining: {error}")
            await asyncio.sleep(delay=3)

    async def run(self, proxy: str | None = None):
        access_token_created_time = 0
        farms = 3

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        tg_web_data = await self.get_tg_web_data(proxy=None)
        tg_web_data_res = unquote(string=tg_web_data)
        print('tg_web_data_res:', tg_web_data_res)
        user_id = tg_web_data_res.split('id":', maxsplit=1)[1].split(',"first_name', maxsplit=1)[0]
        print('user_id:', user_id)

        async with aiofiles.open(self.uuid_file) as uuid_file:
            uuids: dict = json.loads(await uuid_file.read())

        user_uuid = uuids.get(user_id)
        if user_uuid is None:
            user_uuid = uuid.uuid4().__str__()
            uuids[user_id] = user_uuid
            async with aiofiles.open(self.uuid_file, "w") as uuid_file:
                await uuid_file.write(json.dumps(uuids))

        headers['X-Install-Uuid'] = user_uuid
        headers['User-Agent'] = UserAgent(os='android').random

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn) as http_client:
            while True:
                farms -= 1

                if time() - access_token_created_time >= 3600:
                    access_token = await self.login(http_client, tg_web_data=tg_web_data)
                    http_client.headers['Authorization'] = f'Bearer {access_token}'
                    headers['Authorization'] = f'Bearer {access_token}'
                    access_token_created_time = time()

                await self.claim_mining(http_client)
                await self.start_mining(http_client)
                await self.spin(http_client)
                if farms == 0:
                    sleep_time = uniform(*settings.SLEEP_BETWEEN_FARM)
                    logger.info(f"{self.session_name} | Sleep {sleep_time}s")
                    await asyncio.sleep(sleep_time)
                    farms = 3
                else:
                    sleep_time = randint(2, 4)
                    logger.info(f"{self.session_name} | Sleep {sleep_time}s")
                    await asyncio.sleep(sleep_time)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Gamee(tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
