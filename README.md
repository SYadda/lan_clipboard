# LAN Clipboard · 局域网剪贴板

[中文](#中文) · [English](#english)

## 中文

在同一局域网内，用手机和电脑共享一段纯文本。网页可切换中英文。

1. 安装 Python 3，然后在项目目录运行 `python lan_clipboard.py`。项目只用 Python 标准库。
2. 在电脑上打开 [http://localhost:8000](http://localhost:8000)。
3. 手机连上同一局域网的 Wi-Fi，在浏览器输入 `http://<电脑的局域网 IPv4 地址>:8000`。Windows 上可用 `ipconfig` 查看地址。
4. 在一台设备上输入文字并点「保存」，在另一台设备上点「刷新内容」。

文字保存在脚本旁的 `clipboard.txt`。能打开网页的设备都可以读写，请在可信的局域网内使用。

## English

Share a single plain-text clipboard between a phone and a computer on the same local network. The interface is available in English and Chinese.

1. With Python 3 installed, run `python lan_clipboard.py` from the project folder. It uses only the Python standard library.
2. Open [http://localhost:8000](http://localhost:8000) on your computer.
3. Connect your phone to Wi-Fi on the same local network and open `http://<computer LAN IPv4 address>:8000`. On Windows, run `ipconfig` to find the address.
4. Enter text and select **Save** on one device, then select **Refresh** on the other.

The text is stored in `clipboard.txt` next to the script. Any device that can open the page can read and edit it, so use it on a trusted local network.
