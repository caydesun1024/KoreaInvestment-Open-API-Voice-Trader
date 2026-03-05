# -*- coding: utf-8 -*-
# ====|  (REST) 접근 토큰 / (Websocket) 웹소켓 접속키 발급 에 필요한 API 호출 샘플 아래 참고하시기 바랍니다.  |=====================
# ====|  API 호출 공통 함수 포함                                  |=====================

import asyncio
import copy
import json
import logging
import os
import time
from base64 import b64decode
from collections import namedtuple
from collections.abc import Callable
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
import websockets
import yaml
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

clearConsole = lambda: os.system("cls" if os.name in ("nt", "dos") else "clear")

key_bytes = 32
config_root = os.path.join(os.path.expanduser("~"), "KIS", "config")

# 앱키, 앱시크리트, 토큰, 계좌번호 등 저장관리
with open(os.path.join(config_root, "kis_devlp.yaml"), encoding="UTF-8") as f:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)

_TRENV = tuple()
_last_auth_time = datetime.now()
_autoReAuth = False
_DEBUG = False
_isPaper = False
_smartSleep = 0.1

# 기본 헤더값 정의
_base_headers = {
    "Content-Type": "application/json",
    "Accept": "text/plain",
    "charset": "UTF-8",
    "User-Agent": _cfg["my_agent"],
}

# --- 토큰 관리 로직 (svr 구분 추가) ---

def save_token(my_token, my_expired, svr="prod"):
    valid_date = datetime.strptime(my_expired, "%Y-%m-%d %H:%M:%S")
    token_file = os.path.join(config_root, f"KIS_{svr}_{datetime.today().strftime('%Y%m%d')}")
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(f"token: {my_token}\n")
        f.write(f"valid-date: {valid_date}\n")

def read_token(svr="prod"):
    try:
        token_file = os.path.join(config_root, f"KIS_{svr}_{datetime.today().strftime('%Y%m%d')}")
        if not os.path.exists(token_file):
            return None
            
        with open(token_file, encoding="UTF-8") as f:
            tkg_tmp = yaml.load(f, Loader=yaml.FullLoader)

        exp_dt = tkg_tmp["valid-date"]
        now_dt = datetime.now()

        from datetime import timedelta
        if exp_dt > (now_dt + timedelta(hours=1)):
            return tkg_tmp["token"]
        return None
    except Exception:
        return None

def _getBaseHeader():
    if _autoReAuth:
        reAuth()
    return copy.deepcopy(_base_headers)

def _setTRENV(cfg):
    nt1 = namedtuple(
        "KISEnv",
        ["my_app", "my_sec", "my_acct", "my_prod", "my_htsid", "my_token", "my_url", "my_url_ws"],
    )
    d = {
        "my_app": cfg["my_app"],
        "my_sec": cfg["my_sec"],
        "my_acct": cfg["my_acct"],
        "my_prod": cfg["my_prod"],
        "my_htsid": cfg["my_htsid"],
        "my_token": cfg["my_token"],
        "my_url": cfg["my_url"],
        "my_url_ws": cfg["my_url_ws"],
    }
    global _TRENV
    _TRENV = nt1(**d)

def isPaperTrading():
    return _isPaper

def changeTREnv(token_key, svr="prod", product=_cfg["my_prod"]):
    cfg = dict()
    global _isPaper, _smartSleep
    
    if svr == "prod":
        ak1, ak2 = "my_app", "my_sec"
        _isPaper, _smartSleep = False, 0.05
    else:
        ak1, ak2 = "paper_app", "paper_sec"
        _isPaper, _smartSleep = True, 0.5

    cfg["my_app"] = _cfg[ak1]
    cfg["my_sec"] = _cfg[ak2]

    if svr == "prod":
        cfg["my_acct"] = _cfg["my_acct_stock"] if product in ["01", "22", "29"] else _cfg["my_acct_future"]
    else:
        cfg["my_acct"] = _cfg["my_paper_stock"] if product == "01" else _cfg["my_paper_future"]

    cfg["my_prod"] = product
    cfg["my_htsid"] = _cfg["my_htsid"]
    cfg["my_url"] = _cfg[svr]
    cfg["my_token"] = token_key
    cfg["my_url_ws"] = _cfg["ops" if svr == "prod" else "vops"]

    _setTRENV(cfg)

def auth(svr="prod", product=_cfg["my_prod"], url=None, force=False):
    p = {"grant_type": "client_credentials"}
    ak1 = "my_app" if svr == "prod" else "paper_app"
    ak2 = "my_sec" if svr == "prod" else "paper_sec"

    p["appkey"] = _cfg[ak1]
    p["appsecret"] = _cfg[ak2]

    saved_token = None if force else read_token(svr=svr)
    
    if saved_token is None:
        url = f"{_cfg[svr]}/oauth2/tokenP"
        res = requests.post(url, data=json.dumps(p), headers=_getBaseHeader())
        if res.status_code == 200:
            res_data = res.json()
            print(f"\nDEBUG - Token Response ({svr}): {res_data}")
            my_token = res_data["access_token"]
            my_expired = res_data["access_token_token_expired"]
            save_token(my_token, my_expired, svr=svr)
        else:
            print(f"❌ Get Auth token fail ({svr})!")
            return
    else:
        my_token = saved_token

    changeTREnv(my_token, svr, product)
    _base_headers.update({
        "authorization": f"Bearer {my_token}",
        "appkey": _TRENV.my_app,
        "appsecret": _TRENV.my_sec
    })
    
    global _last_auth_time
    _last_auth_time = datetime.now()

def reAuth(svr="prod", product=_cfg["my_prod"]):
    if (datetime.now() - _last_auth_time).seconds >= 86400:
        auth(svr, product)

def getEnv(): return _cfg
def smart_sleep(): time.sleep(_smartSleep)
def getTREnv(): return _TRENV

# --- HashKey 생성 함수 추가 ---
def set_order_hash_key(h, p):
    url = f"{getTREnv().my_url}/uapi/hashkey"
    res = requests.post(url, data=json.dumps(p), headers=h)
    if res.status_code == 200:
        h["hashkey"] = res.json()["HASH"]
    else:
        print("Error getting HashKey:", res.status_code)

# --- API 응답 클래스 ---

class APIResp:
    def __init__(self, resp):
        self._rescode = resp.status_code
        self._resp = resp
        body_data = resp.json()
        self._body = namedtuple("body", body_data.keys())(**body_data)
        self._err_code = getattr(self._body, "msg_cd", "")
        self._err_message = getattr(self._body, "msg1", "")

    def isOK(self):
        try: return self._body.rt_cd == "0"
        except: return False
    
    def getResCode(self): return self._rescode
    def getBody(self): return self._body
    def getErrorCode(self): return self._err_code
    def getErrorMessage(self): return self._err_message
    
    def printError(self, url):
        print(f"--- Error [{self._rescode}] url={url} ---")
        print(f"rt_cd: {getattr(self._body, 'rt_cd', '?')} | msg_cd: {self._err_code} | msg1: {self._err_message}")

class APIRespError:
    def __init__(self, code, text):
        self.code, self.text = code, text
    def isOK(self): return False
    def getErrorCode(self): return str(self.code)
    def getErrorMessage(self): return self.text
    def printError(self, url=""): print(f"❌ Error {self.code}: {self.text}")

def _url_fetch(api_url, ptr_id, tr_cont, params, appendHeaders=None, postFlag=False, retry_count=0):
    url = f"{getTREnv().my_url}{api_url}"
    headers = _getBaseHeader()
    
    tr_id = ptr_id
    if ptr_id[0] in ("T", "J", "C") and isPaperTrading():
        tr_id = "V" + ptr_id[1:]

    headers.update({
        "tr_id": tr_id,
        "custtype": "P",
        "tr_cont": tr_cont
    })
    if appendHeaders: headers.update(appendHeaders)

    if postFlag:
        set_order_hash_key(headers, params)
        res = requests.post(url, headers=headers, data=json.dumps(params))
    else:
        res = requests.get(url, headers=headers, params=params)

    if res.status_code == 200:
        return APIResp(res)
    
    res_json = res.json() if res.text else {}
    if (res.status_code in [401, 500]) and (res_json.get("msg_cd") in ["EGW00121", "EGW00123"]) and retry_count == 0:
        print(f"⚠️ 토큰 만료 감지. 재발급 후 재시도...")
        auth(svr="vps" if isPaperTrading() else "prod", product=getTREnv().my_prod, force=True)
        return _url_fetch(api_url, ptr_id, tr_cont, params, appendHeaders, postFlag, retry_count + 1)
    
    return APIRespError(res.status_code, res.text)

# --- WebSocket 관련 ---

_base_headers_ws = {"content-type": "utf-8"}

def auth_ws(svr="prod", product=_cfg["my_prod"]):
    ak1 = "my_app" if svr == "prod" else "paper_app"
    ak2 = "my_sec" if svr == "prod" else "paper_sec"
    p = {"grant_type": "client_credentials", "appkey": _cfg[ak1], "secretkey": _cfg[ak2]}
    
    url = f"{_cfg[svr]}/oauth2/Approval"
    res = requests.post(url, data=json.dumps(p), headers=_getBaseHeader())
    if res.status_code == 200:
        _base_headers_ws["approval_key"] = res.json()["approval_key"]
        changeTREnv(None, svr, product)
    else:
        print("❌ Get WebSocket Approval Key fail!")

def data_fetch(tr_id, tr_type, params, appendHeaders=None) -> dict:
    headers = copy.deepcopy(_base_headers_ws)
    headers.update({"tr_type": tr_type, "custtype": "P"})
    if appendHeaders: headers.update(appendHeaders)
    return {"header": headers, "body": {"input": {"tr_id": tr_id, **params}}}

def system_resp(data):
    rdic = json.loads(data)
    tr_id = rdic["header"]["tr_id"]
    is_ping = (tr_id == "PINGPONG")
    
    iv, ekey, encrypt = None, None, rdic["header"].get("encrypt", "N")
    if "body" in rdic:
        iv = rdic["body"].get("output", {}).get("iv")
        ekey = rdic["body"].get("output", {}).get("key")
        
    nt = namedtuple("SysMsg", ["isOk", "tr_id", "tr_key", "isUnSub", "isPingPong", "tr_msg", "iv", "ekey", "encrypt"])
    return nt(
        isOk=(rdic.get("body", {}).get("rt_cd") == "0"),
        tr_id=tr_id,
        tr_key=rdic["header"].get("tr_key"),
        isUnSub=("body" in rdic and rdic["body"].get("msg1", "").startswith("UNSUB")),
        isPingPong=is_ping,
        tr_msg=rdic.get("body", {}).get("msg1"),
        iv=iv, ekey=ekey, encrypt=encrypt
    )

def aes_cbc_base64_dec(key, iv, cipher_text):
    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))

# --- WebSocket Loop Class ---

open_map = {}
data_map = {}

def add_open_map(name, request, data, kwargs=None):
    if name not in open_map: open_map[name] = {"func": request, "items": [], "kwargs": kwargs}
    if isinstance(data, list): open_map[name]["items"] += data
    else: open_map[name]["items"].append(data)

def add_data_map(tr_id, columns=None, encrypt=None, key=None, iv=None):
    if tr_id not in data_map: data_map[tr_id] = {"columns": [], "encrypt": "N", "key": None, "iv": None}
    if columns: data_map[tr_id]["columns"] = columns
    if encrypt: data_map[tr_id]["encrypt"] = encrypt
    if key: data_map[tr_id]["key"] = key
    if iv: data_map[tr_id]["iv"] = iv

class KISWebSocket:
    def __init__(self, api_url, max_retries=3):
        self.api_url, self.max_retries = api_url, max_retries
        self.retry_count = 0

    async def __subscriber(self, ws):
        async for raw in ws:
            if raw[0] in ["0", "1"]:
                d1 = raw.split("|")
                tr_id = d1[1]
                dm = data_map[tr_id]
                data = d1[3]
                if dm["encrypt"] == "Y": data = aes_cbc_base64_dec(dm["key"], dm["iv"], data)
                df = pd.read_csv(StringIO(data), header=None, sep="^", names=dm["columns"], dtype=object)
                if self.on_result: self.on_result(ws, tr_id, df, dm)
            else:
                rsp = system_resp(raw)
                add_data_map(rsp.tr_id, encrypt=rsp.encrypt, key=rsp.ekey, iv=rsp.iv)
                if rsp.isPingPong: await ws.pong(raw)
                if self.on_result: self.on_result(ws, rsp.tr_id, pd.DataFrame(), data_map[rsp.tr_id])

    async def __runner(self):
        url = f"{getTREnv().my_url_ws}{self.api_url}"
        while self.retry_count < self.max_retries:
            try:
                async with websockets.connect(url) as ws:
                    for name, obj in open_map.items():
                        for item in obj["items"]:
                            msg, cols = obj["func"]("1", item, **(obj["kwargs"] or {}))
                            add_data_map(msg["body"]["input"]["tr_id"], columns=cols)
                            await ws.send(json.dumps(msg))
                    await self.__subscriber(ws)
            except Exception as e:
                print(f"WebSocket Error: {e}")
                self.retry_count += 1
                await asyncio.sleep(1)

    def subscribe(self, request, data, kwargs=None):
        add_open_map(request.__name__, request, data, kwargs)

    def start(self, on_result):
        self.on_result = on_result
        try: asyncio.run(self.__runner())
        except KeyboardInterrupt: pass
