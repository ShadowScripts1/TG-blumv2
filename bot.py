import os
import re
import sys
import json
import anyio
from payload import get_payload
import httpx
import random
import uuid
import requests
import asyncio
import argparse
import aiofiles
import aiofiles.os
from base64 import b64decode
import aiofiles.ospath
from colorama import init, Fore, Style
from urllib.parse import parse_qs
from datetime import datetime
import time
from models import (
    get_by_id,
    update_useragent,
    insert,
    update_balance,
    update_token,
    init as init_db,
)
import python_socks
from httpx_socks import AsyncProxyTransport
from fake_useragent import UserAgent

# Initialize logging
init(autoreset=True)
red = Fore.LIGHTRED_EX
blue = Fore.LIGHTBLUE_EX
green = Fore.LIGHTGREEN_EX
yellow = Fore.LIGHTYELLOW_EX
black = Fore.LIGHTBLACK_EX
white = Fore.LIGHTWHITE_EX
reset = Style.RESET_ALL
magenta = Fore.LIGHTMAGENTA_EX
line = white + "~" * 50
log_file = "http.log"
proxy_file = "proxies.txt"
data_file = "data.txt"
config_file = "config.json"

class Config:
    def __init__(self, auto_task, auto_game, auto_claim, low, high, clow, chigh):
        self.auto_task = auto_task
        self.auto_game = auto_game
        self.auto_claim = auto_claim
        self.low = low
        self.high = high
        self.clow = clow
        self.chigh = chigh
        self.max_session_duration = 7200  # 2 hours max session duration
        self.max_actions_per_session = 1000  # Max actions per session

def get_random_user_agent():
    ua = UserAgent(browsers=['chrome', 'firefox', 'safari', 'edge'])
    return ua.random

async def random_sleep(min_time, max_time, jitter=0.1):
    base_time = random.uniform(min_time, max_time)
    jitter_time = random.uniform(0, jitter * base_time)
    total_time = base_time + jitter_time
    await asyncio.sleep(total_time)

async def humanized_typing(text, min_delay=0.05, max_delay=0.2):
    for char in text:
        yield char
        await random_sleep(min_delay, max_delay)

class BlumTod:
    def __init__(self, id, query, proxies, config: Config):
        self.p = id
        self.query = query
        self.proxies = proxies
        self.cfg = config
        self.valid = True
        parser = {key: value[0] for key, value in parse_qs(query).items()}
        user = parser.get("user")
        if user is None:
            self.valid = False
            self.log(f"{red}this account data has the wrong format.")
            return None
        self.user = json.loads(user)
        if len(self.proxies) > 0:
            proxy = self.get_random_proxy(id, False)
            transport = AsyncProxyTransport.from_url(proxy)
            self.ses = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(10.0))
        else:
            self.ses = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": get_random_user_agent(),
            "content-type": "application/json",
            "origin": "https://telegram.blum.codes",
            "x-requested-with": "org.telegram.messenger",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://telegram.blum.codes/",
            "accept-encoding": "gzip, deflate",
            "accept-language": "en,en-US;q=0.9",
        }
        self.session_start_time = time.time()
        self.action_count = 0

    def log(self, msg):
        now = datetime.now().isoformat().split("T")[1].split(".")[0]
        print(
            f"{black}[{now}]{white}-{blue}[{white}acc {self.p + 1}{blue}]{white} {msg}{reset}"
        )

    async def ipinfo(self):
        ipinfo_urls = [
            "https://ipapi.co/json/",
            "https://ipwho.is/",
            "https://freeipapi.com/api/json"
        ]
        headers = {"user-agent": get_random_user_agent()}
        for url in random.sample(ipinfo_urls, len(ipinfo_urls)):
            try:
                res = await self.http(url, headers)
                data = res.json()
                ip = data.get("ip") or data.get("ipAddress")
                country = data.get("country") or data.get("country_code")
                if ip and country:
                    self.log(f"{green}ip : {white}{ip} {green}country : {white}{country}")
                    return
            except Exception:
                continue
        self.log(f"{green}ip : {white}None {green}country : {white}None")

    def get_random_proxy(self, isself, israndom=False):
        if israndom:
            return random.choice(self.proxies)
        return self.proxies[isself % len(self.proxies)]

    async def http(self, url, headers, data=None):
        max_retries = 3
        for _ in range(max_retries):
            try:
                if not await aiofiles.ospath.exists(log_file):
                    async with aiofiles.open(log_file, "w") as w:
                        await w.write("")

                logsize = await aiofiles.ospath.getsize(log_file)

                if logsize / 1024 / 1024 > 1:
                    async with aiofiles.open(log_file, "w") as w:
                        await w.write("")

                headers['User-Agent'] = get_random_user_agent()

                if data is None:
                    res = await self.ses.get(url, headers=headers)
                elif data == "":
                    res = await self.ses.post(url, headers=headers)
                else:
                    res = await self.ses.post(url, headers=headers, data=data)
                
                async with aiofiles.open(log_file, "a", encoding="utf-8") as hw:
                    await hw.write(f"{res.status_code} {res.text}\n")
                
                if "<title>" in res.text:
                    self.log(f"{yellow}failed get json response !")
                    return None

                return res
            except (httpx.ProxyError, python_socks._errors.ProxyTimeoutError, python_socks._errors.ProxyError):
                proxy = self.get_random_proxy(0, israndom=True)
                transport = AsyncProxyTransport.from_url(proxy)
                self.ses = httpx.AsyncClient(transport=transport)
                self.log(f"{yellow}proxy error, selecting random proxy !")
                await random_sleep(1, 3)
            except httpx.NetworkError:
                self.log(f"{yellow}network error !")
                await random_sleep(1, 3)
            except httpx.TimeoutException:
                self.log(f"{yellow}connection timeout !")
                await random_sleep(1, 3)
            except (httpx.RemoteProtocolError, anyio.EndOfStream):
                self.log(f"{yellow}connection close without response !")
                await random_sleep(1, 3)
        return None

    def is_expired(self, token):
        if token is None or isinstance(token, bool):
            return True
        header, payload, sign = token.split(".")
        payload = b64decode(payload + "==").decode()
        jload = json.loads(payload)
        now = round(datetime.now().timestamp()) + 300
        exp = jload["exp"]
        if now > exp:
            return True
        return False

    async def login(self):
        auth_url = "https://user-domain.blum.codes/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP"
        data = {
            "query": self.query,
        }
        res = await self.http(auth_url, self.headers, json.dumps(data))
        token = res.json().get("token")
        if not token:
            message = res.json().get("message", "")
            if "signature is invalid" in message:
                self.log(f"{red}data has the wrong format or data is outdated.")
                return False
            self.log(f"{red}{message}, check log file http.log !")
            return False
        token = token.get("access")
        uid = self.user.get("id")
        await update_token(uid, token)
        self.log(f"{green}success get access token !")
        self.headers["authorization"] = f"Bearer {token}"
        return True

    async def create_payload(self, game_id, points, dogs):
        payload_data = {'gameId': game_id,
                'points': str(points),
                "dogs": dogs}

        PAYLOAD_SERVER_URL = "https://server2.ggtog.live/api/game"
        resp = requests.post(PAYLOAD_SERVER_URL, json=payload_data)

        if resp is not None:
            try:
                data = resp.json()
                if "payload" in data:
                    return json.dumps({"payload": data["payload"]})
            except Exception as e:
                self.log(e)
                return None

    async def simulate_human_behavior(self):
        if random.random() < 0.1:  # 10% chance of taking a break
            break_duration = random.uniform(60, 300)  # 1-5 minutes
            self.log(f"{yellow}Taking a short break for {break_duration:.0f} seconds")
            await random_sleep(break_duration, break_duration + 30)

        session_duration = time.time() - self.session_start_time
        experience_factor = min(1.0, session_duration / 3600)  # Max experience after 1 hour
        action_delay = random.uniform(1, 5) * (1 - 0.5 * experience_factor)
        await random_sleep(action_delay, action_delay + 2)

        self.action_count += 1

    async def start(self):
        rtime = random.uniform(self.cfg.clow, self.cfg.chigh)
        await random_sleep(rtime, rtime + 10)
        if not self.valid:
            return int(datetime.now().timestamp()) + (3600 * 8)
        balance_url = "https://game-domain.blum.codes/api/v1/user/balance"
        friend_balance_url = "https://user-domain.blum.codes/api/v1/friends/balance"
        farming_claim_url = "https://game-domain.blum.codes/api/v1/farming/claim"
        farming_start_url = "https://game-domain.blum.codes/api/v1/farming/start"
        checkin_url = "https://game-domain.blum.codes/api/v1/daily-reward?offset=-420"
        if len(self.proxies) > 0:
            await self.ipinfo()
        uid = self.user.get("id")
        first_name = self.user.get("first_name")
        self.log(f"{green}login as {white}{first_name}")
        result = await get_by_id(uid)
        if not result:
            await insert(uid, first_name)
            result = await get_by_id(uid)
        useragent = result.get("useragent")
        if useragent is None:
            useragent = get_random_user_agent()
            await update_useragent(uid, useragent)
        self.headers["user-agent"] = useragent
        token = result.get("token")
        expired = self.is_expired(token=token)
        if expired:
            result = await self.login()
            if not result:
                return int(datetime.now().timestamp()) + 300
        else:
            self.headers["authorization"] = f"Bearer {token}"
        res = await self.http(checkin_url, self.headers)
        if res.status_code == 404:
            self.log(f"{yellow}already check in today !")
        else:
            res = await self.http(checkin_url, self.headers, "")
            self.log(f"{green}success check in today !")
        while True:
            res = await self.http(balance_url, self.headers)
            timestamp = res.json().get("timestamp")
            if timestamp == 0:
                timestamp = int(datetime.now().timestamp() * 1000)
            if not timestamp:
                continue
            timestamp = timestamp / 1000
            break
        balance = res.json().get("availableBalance", 0)
        await update_balance(uid, balance)
        farming = res.json().get("farming")
        end_iso = datetime.now().isoformat(" ")
        end_farming = int(datetime.now().timestamp() * 1000) + random.randint(
            3600000, 7200000
        )
        self.log(f"{green}balance : {white}{balance}")
        refres = await self.http(friend_balance_url, self.headers)
        amount_claim = refres.json().get("amountForClaim")
        can_claim = refres.json().get("canClaim", False)
        self.log(f"{green}referral balance : {white}{amount_claim}")
        if can_claim:
            friend_claim_url = "https://user-domain.blum.codes/api/v1/friends/claim"
            clres = await self.http(friend_claim_url, self.headers, "")
            if clres.json().get("claimBalance") is not None:
                self.log(f"{green}success claim referral reward !")
            else:
                self.log(f"{red}failed claim referral reward !")
        if self.cfg.auto_claim:
            while True:
                if farming is None:
                    _res = await self.http(farming_start_url, self.headers, "")
                    if _res.status_code != 200:
                        self.log(f"{red}failed start farming !")
                    else:
                        self.log(f"{green}success start farming !")
                        farming = _res.json()
                if farming is None:
                    res = await self.http(balance_url, self.headers)
                    farming = res.json().get("farming")
                    if farming is None:
                        continue
                end_farming = farming.get("endTime")
                if timestamp > (end_farming / 1000):
                    res_ = await self.http(farming_claim_url, self.headers, 

 "")
                    if res_ and res_.status_code != 200:
                        self.log(f"{red}failed claim farming !")
                    else:
                        self.log(f"{green}success claim farming !")
                        farming = None
                        continue
                else:
                    self.log(f"{yellow}not time to claim farming !")
                end_iso = (
                    datetime.fromtimestamp(end_farming / 1000)
                    .isoformat(" ")
                    .split(".")[0]
                )
                break
            self.log(f"{green}end farming : {white}{end_iso}")
        if self.cfg.auto_task:
            task_url = "https://earn-domain.blum.codes/api/v1/tasks"
            res = await self.http(task_url, self.headers)
            if res:
                for tasks in res.json():
                    if isinstance(tasks, str):
                        self.log(f"{yellow}failed get task list !")
                        break
                    for k in list(tasks.keys()):
                        if k != "tasks" and k != "subSections":
                            continue
                        for t in tasks.get(k):
                            if isinstance(t, dict):
                                subtasks = t.get("subTasks")
                                if subtasks is not None:
                                    for task in subtasks:
                                        await self.solve(task)
                                    await self.solve(t)
                                    continue
                            _tasks = t.get("tasks")
                            if not _tasks:
                                continue
                            for task in _tasks:
                                await self.solve(task)
        if self.cfg.auto_game:
            play_url = "https://game-domain.blum.codes/api/v2/game/play"
            claim_url = "https://game-domain.blum.codes/api/v2/game/claim"
            dogs_url = 'https://game-domain.blum.codes/api/v2/game/eligibility/dogs_drop'

            try:
                random_uuid = str(uuid.uuid4())
                point = random.randint(self.cfg.low, self.cfg.high)
                data = await get_payload(gameId=random_uuid, points=point)

                if "payload" in data:
                    self.log(f"{green}Games available right now!")
                    game = True
                else:
                    self.log(f"{red}Failed start games")
                    self.log(f"{red}Install node.js!")
                    game = False
            except Exception as e:
                self.log(f"{red}Failed start games - {e}")
                self.log(f"{red}Install node.js!")
                game = False

            while game:
                res = await self.http(balance_url, self.headers)

                play = res.json().get("playPasses")
                if play is None:
                    self.log(f"{yellow}failed get game ticket !")
                    break
                self.log(f"{green}you have {white}{play}{green} game ticket")
                if play <= 0:
                    break

                for i in range(play):
                    if self.is_expired(self.headers.get("authorization").split(" ")[1]):
                        result = await self.login()
                        if not result:
                            break
                        continue

                    res = await self.http(play_url, self.headers, "")
                    game_id = res.json().get("gameId")

                    if game_id is None:
                        message = res.json().get("message", "")
                        if message == "cannot start game":
                            self.log(f"{yellow}{message}")
                            game = False
                            break
                        self.log(f"{yellow}{message}")
                        continue

                    while True:
                        point = random.randint(self.cfg.low, self.cfg.high)

                        try:
                            res = await self.http(dogs_url, self.headers)
                            if res is not None:
                                eligible = res.json().get('eligible', False)
                        except Exception as e:
                            self.log(f"Failed elif dogs, error: {e}")
                            eligible = None

                        if eligible:
                            dogs = random.randint(25, 30) * 5
                            self.log(f'dogs = {dogs}')
                            payload = await get_payload(gameId=game_id, points=point)
                        else:
                            payload = await get_payload(gameId=game_id, points=point)

                        await random_sleep(31, 40)

                        res = await self.http(claim_url, self.headers, payload)

                        if "OK" in res.text:
                            self.log(
                                f"{green}success earn {white}{point}{green} from game !"
                            )
                            break
                        else:
                            self.log(f"{red}failed earn {white}{point}{red} from game !")
                        break

                    await self.simulate_human_behavior()

        res = await self.http(balance_url, self.headers)
        balance = res.json().get("availableBalance", 0)
        self.log(f"{green}balance :{white}{balance}")
        now = datetime.now().strftime("%Yx%mx%d %H:%M")
        async with aiofiles.open("balance.log", "a", encoding="utf-8") as f:
            await f.write(f"{now} - {self.p} - {balance} - {first_name}\n")
        await update_balance(uid, balance)
        return round(end_farming / 1000)

    async def solve(self, task: dict):
        task_id = task.get("id")
        task_title = task.get("title")
        task_status = task.get("status")
        task_type = task.get("type")
        validation_type = task.get("validationType")
        start_task_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/start"
        claim_task_url = f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/claim"
        while True:
            if task_status == "FINISHED":
                self.log(f"{yellow}already complete task id {white}{task_title} !")
                return
            if task_status == "READY_FOR_CLAIM" or task_status == "STARTED":
                _res = await self.http(claim_task_url, self.headers, "")
                message = _res.json().get("message")
                if message:
                    return
                _status = _res.json().get("status")
                if _status == "FINISHED":
                    self.log(f"{green}success complete task id {white}{task_title} !")
                    return
            if task_status == "NOT_STARTED" and task_type == "PROGRESS_TARGET":
                return
            if task_status == "NOT_STARTED":
                _res = await self.http(start_task_url, self.headers, "")
                await random_sleep(2, 4)
                try:
                    message = _res.json().get("message")
                    if message:
                        return
                    task_status = _res.json().get("status")
                    continue
                except Exception as e:
                    self.log(e)
                    return
            if validation_type == "KEYWORD" or task_status == "READY_FOR_VERIFY":
                await random_sleep(2, 4)
                verify_url = (
                    f"https://earn-domain.blum.codes/api/v1/tasks/{task_id}/validate"
                )
                answer_url = "https://raw.githubusercontent.com/boytegar/BlumBOT/d55dcc033e508ee8dc10218f72f7ac369de1039f/verif.json"
                res_ = await self.http(answer_url, {"User-Agent": get_random_user_agent()})
                answers = res_.json()
                answer = answers.get(task_id)
                if not answer:
                    self.log(f"{yellow}answers to quiz tasks are not yet available.")
                    break
                data = {"keyword": answer}
                res = await self.http(verify_url, self.headers, json.dumps(data))
                if res:
                    message = res.json().get("message")
                    if message:
                        self.log(message)
                        break
                    task_status = res.json().get("status")
                    continue
                else:
                    break
            else:
                break

async def get_data(data_file, proxy_file):
    async with aiofiles.open(data_file) as w:
        read = await w.read()
        datas = [i for i in read.splitlines() if len(i) > 10]
    async with aiofiles.open(proxy_file) as w:
        read = await w.read()
        proxies = [i for i in read.splitlines() if len(i) > 5]
    return datas, proxies

async def main():
    init()
    banner = f"""{Fore.GREEN}
 ██████  ██   ██   █████  ██████   ██████  ██     ██
██       ██   ██  ██   ██ ██   ██ ██    ██ ██     ██
███████  ███████  ███████ ██   ██ ██    ██ ██  █  ██
     ██  ██   ██  ██   ██ ██   ██ ██    ██ ██ ███ ██
███████  ██   ██  ██   ██ ██████   ██████   ███ ███  
    Auto Claim Bot For Blum - shadow Automation
    Github  : https://github.com/ShadowScripts1
    Telegram: https://t.me/shadowscripters
        {Style.RESET_ALL}"""
    arg = argparse.ArgumentParser()
    arg.add_argument(
        "--data",
        "-D",
        default=data_file,
        help=f"Perform custom input for data files (default: {data_file})",
    )
    arg.add_argument(
        "--proxy",
        "-P",
        default=proxy_file,
        help=f"Perform custom input for proxy files (default : {proxy_file})",
    )
    arg.add_argument(
        "--action",
        "-A",
        help="Function to directly enter the menu without displaying input",
    )
    arg.add_argument(
        "--worker",
        "-W",
        help="Total workers or number of threads to be used (default : cpu core / 2)",
    )
    arg.add_argument("--marin", action="store_true")
    args = arg.parse_args()
    await init_db()
    if not await aiofiles.ospath.exists(args.data):
        async with aiofiles.open(args.data, "a") as w:
            pass
    if not await aiofiles.ospath.exists(args.proxy):
        async with aiofiles.open(args.proxy, "a") as w:
            pass
    if not await aiofiles.ospath.exists(config_file):
        async with aiofiles.open(config_file, "w") as w:
            _config = {
                "auto_claim": True,
                "auto_task": True,
                "auto_game": True,
                "low": 200,
                "high": 250,
                "clow": 30,
                "chigh": 60,
            }
            await w.write(json.dumps(_config, indent=4))
    while True:
        if not args.marin:
            os.system("cls" if os.name == "nt" else "clear")
        print(banner)
        async with aiofiles.open(config_file) as r:
            read = await r.read()
            cfg = json.loads(read)
            config = Config(
                auto_task=cfg.get("auto_task"),
                auto_game=cfg.get("auto_game"),
                auto_claim=cfg.get("auto_claim"),
                low=int(cfg.get("low", 180)),
                high=int(cfg.get("high", 250)),
                clow=int(cfg.get("clow", 30)),
                chigh=int(cfg.get("chigh", 60)),
            )
        datas, proxies = await get_data(data_file=args.data, proxy_file=args.proxy)
        menu = f"""
{white}data file :{green} {args.data}
{white}proxy file :{green} {args.proxy}
{green}total data :{white} {len(datas)}
{green}total proxy :{white} {len(proxies)}

    {green}1{white}.{green}) {white}set on/off auto claim ({(green + "active" if config.auto_claim else red + "non-active")})
    {green}2{white}.{green}) {white}set on/off auto solve task ({(green + "active" if config.auto_task else red + "non-active")})
    {green}3{white}.{green}) {white}set on/off auto play game ({(green + "active" if config.auto_game else red + "non-active")})
    {green}4{white}.{green}) {white}set game point {green}({config.low}-{config.high})
    {green}5{white}.{green}) {white}set wait time before start {green}({config.clow}-{config.chigh})
    {green}6{white}.{green}) {white}start bot (multiprocessing)
    {green}7{white}.{green}) {white}start bot (sync mode)
        """
        opt = None
        if args.action:
            opt = args.action
        else:
            print(menu)
            opt = input(f"{green}input number : {white}")
            print(f"{white}~" * 50)
        if opt == "1":
            cfg["auto_claim"] = False if config.auto_claim else True
            async with aiofiles.open(config_file, "w") as w:
                await w.write(json.dumps(cfg, indent=4))
            print(f"{green}success update auto claim config")
            input(f"{blue}press enter to continue")
            opt = None
            continue
        if opt == "2":
            cfg["auto_task"] = False if config.auto_task else True
            async with aiofiles.open(config_file, "w") as w:
                await w.write(json.dumps(cfg, indent=4))
            print(f"{green}success update auto task config !")
            input(f"{blue}press enter to continue")
            opt = None
            continue
        if opt == "3":
            cfg["auto_game"] = False if config.auto_game else True
            async with aiofiles.open(config_file, "w") as w:
                await w.write(json.dumps(cfg, indent=4))
            print(f"{green}success update auto game config !")
            input(f"{blue}press enter to continue")
            opt = None
            continue
        if opt == "4":
            low = input(f"{green}input low game point : {white}") or 240
            high = input(f"{green}input high game point : {white}") or 250
            cfg["low"] = low
            cfg["high"] = high
            async with aiofiles.open(config_file, "w") as w:
                await w.write(json.dumps(cfg, indent=4))
            print(f"{green}success update game point !")
            input(f"{blue}press enter to continue")
            opt = None
            continue
        if opt == "6":
            if not args.worker:
                worker = max(1, int(os.cpu_count() / 2))
            else:
                worker = int(args.worker)
            sema = asyncio.Semaphore(worker)

            async def bound(sem, params):
                async with sem:
                    return await BlumTod(*params).start()

            while True:
                datas, proxies = await get_data(args.data, args.proxy)
                tasks = [
                    asyncio.create_task(bound(sema, (no, data, proxies, config)))
                    for no, data in enumerate(datas)
                ]
                result = await asyncio.gather(*tasks)
                end = int(datetime.now().timestamp())
                total = min(result) - end
                await random_sleep(total, total + 60)
        if opt == "7":
            while True:
                datas, proxies = await get_data(args.data, args.proxy)
                result = []
                for no, data in enumerate(datas):
                    res = await BlumTod(
                        id=no, query=data, proxies=proxies, config=config
                    ).start()
                    result.append(res)
                end = int(datetime.now().timestamp())
                total = min(result) - end
                await random_sleep(total, total + 60)
        if opt == "5":
            low = input(f"{green}input low wait time : {white}") or 30
            high = input(f"{green}input high wait time : {white}") or 60
            cfg["clow"] = low
            cfg["chigh"] = high
            async with aiofiles.open(config_file, "w") as w:
                await w.write(json.dumps(cfg, indent=4))
            print(f"{green}success update wait time !")
            input(f"{blue}press enter to continue")
            opt = None
            continue

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        exit()