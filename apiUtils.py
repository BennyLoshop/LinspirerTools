import json
import base64
import requests
from Crypto.Cipher import AES
from PyQt6.QtWidgets import QMessageBox

KEY = b"1191ADF18489D8DA"
IV = b"5E9B755A8B674394"

def pkcs7_pad(data: bytes) -> bytes:
    pad_len = 16 - len(data) % 16
    return data + bytes([pad_len] * pad_len)


def pkcs7_unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    return data[:-pad_len]


def aes_encrypt(text: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    enc = cipher.encrypt(pkcs7_pad(text.encode("utf-8")))
    return base64.b64encode(enc).decode("utf-8")


def aes_decrypt(b64text: str) -> str:
    enc = base64.b64decode(b64text)
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    dec = cipher.decrypt(enc)
    return pkcs7_unpad(dec).decode("utf-8", errors="replace")


def post_request(envelope, url="https://cloud.linspirer.com:883/public-interface.php"):
    resp = requests.post(url, json=envelope, timeout=20, verify=True)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    if envelope.get("is_encrypt"):
        return aes_decrypt(resp.text.strip())
    else:
        return resp.text.strip()


# ================= 接口函数 =================
def bind_device(swdid, account, model):
    print("正在绑定设备...")
    device_info = {
        "brand": "",
        "deviceid": "",
        "email": account,
        "isrooted": False,
        "model": model,
        "romavailablesize": 0,
        "romtotalsize": 0,
        "romversion": "",
        "simserialnumber": "unknown",
        "swdid": swdid,
        "systemversion": "",
        "token": "",
        "wifimacaddress": "",
    }
    envelope = {
        "id": 1,
        "!version": 6,
        "jsonrpc": "2.0",
        "is_encrypt": True,
        "client_version": "zhongyukejiao_hem_6.10.004.6",
        "method": "com.linspirer.device.setdevice",
        "params": aes_encrypt(json.dumps(device_info, ensure_ascii=False)),
    }
    print("绑定设备请求:", envelope)
    obj = json.loads(post_request(envelope))
    if obj.get("code") != 0:
        print("绑定设备响应:", obj)
        raise RuntimeError("绑定失败: " + json.dumps(obj, ensure_ascii=False))
    
    print("设备绑定成功")


def get_all_apps(swdid, account, model):
    inner = {
        "swdid": swdid,
        "email": account,
        "model": model,
        "launcher_version": "zhongyukejiao_hem_6.10.004.6",
    }
    envelope = {
        "id": 1,
        "!version": 6,
        "jsonrpc": "2.0",
        "is_encrypt": True,
        "client_version": "zhongyukejiao_hem_6.10.004.6",
        "method": "com.linspirer.tactics.gettactics",
        "params": aes_encrypt(json.dumps(inner, ensure_ascii=False)),
    }
    resp_text = post_request(envelope)
    obj = json.loads(resp_text)
    if obj.get("code") != 0:
        raise RuntimeError("gettactics 错误: " + resp_text)

    data = obj.get("data", {})
    apps1 = data.get("app_tactics", {}).get("applist", [])
    apps2 = data.get("interest_applist", [])

    # 添加来源标识
    for a in apps1:
        a["_source"] = "策略应用"
    for a in apps2:
        a["_source"] = "兴趣应用"
        
    print(f"获取应用列表成功，共 {len(apps1) + len(apps2)} 个应用")

    return apps1 + apps2  # 合并列表


def get_app(swdid, account, model, appid):
    inner = {
        "swdid": swdid,
        "email": account,
        "model": model,
        "launcher_version": "zhongyukejiao_hem_6.10.004.6",
        "appid": appid,
    }
    envelope = {
        "id": 1,
        "!version": 6,
        "jsonrpc": "2.0",
        "is_encrypt": True,
        "client_version": "zhongyukejiao_hem_6.10.004.6",
        "method": "com.linspirer.app.getdetail",
        "params": aes_encrypt(json.dumps(inner, ensure_ascii=False)),
    }
    resp_text = post_request(envelope)
    obj = json.loads(resp_text)
    if obj.get("code") != 0:
        raise RuntimeError("get_app 错误: " + resp_text)
    return obj
