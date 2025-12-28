import requests
import json
import webbrowser

VER = "0.0.3"
updateUrl = "https://data.jsdelivr.com/v1/packages/gh/bennyloshop/LinspirerTools"

def checkUpdate():
    try:
        response = requests.get(updateUrl)
        data = response.json()

        # 获取第一个版本
        version = data["versions"][0]["version"]
        print(version)
        if version == VER:
            return False
        
        url = f"https://github.com/BennyLoshop/LinspirerTools/releases/tag/v{version}"
        
        try:
            # 发起 HEAD 请求，不下载内容，提高速度
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                webbrowser.open(url)
        except requests.RequestException:
            pass
    except Exception as e:
        return False
