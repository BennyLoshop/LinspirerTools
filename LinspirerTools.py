#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests
from Crypto.Cipher import AES
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QGridLayout,
    QMessageBox
)
from PyQt6.QtGui import QPixmap, QColor, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QProgressDialog
from apiUtils import bind_device, get_all_apps, get_app
from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtCore import QTimer
from updateUtils import checkUpdate
from PyQt6 import QtCore
import os

# ================= AES 配置 =================
def resource_path(relative_path):
    # Nuitka 打包后资源会在 sys._MEIPASS 下
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


MAIN_QSS = """/* ================= 全局 ================= */
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", Arial;
    font-size: 13px;
    color: #333;
    background-color: #f5f7fa;
}

/* ================= 输入框 ================= */
QLineEdit {
    height: 32px;
    padding: 0 8px;
    border-radius: 6px;
    border: 1px solid #dcdfe6;
    background: #ffffff;
}

QLineEdit:focus {
    border: 1px solid #409eff;
}

/* ================= 普通按钮 ================= */
QPushButton {
    height: 34px;
    border-radius: 6px;
    border: none;
    background-color: #409eff;
    color: white;
    padding: 0 16px;
}

QPushButton:hover {
    background-color: #66b1ff;
}

QPushButton:pressed {
    background-color: #337ecc;
}

QPushButton:disabled {
    background-color: #c0c4cc;
    color: #ffffff;
}

/* ================= 卡片按钮（下载） ================= */
QFrame QPushButton {
    height: 30px;
    border-radius: 6px;
    background-color: #67c23a;
}

QFrame QPushButton:hover {
    background-color: #85ce61;
}

QFrame QPushButton:pressed {
    background-color: #5daf34;
}

/* ================= 卡片 Frame ================= */
QFrame {
    background: #ffffff;
    border-radius: 10px;
    border: 1px solid #ebeef5;
}

/* ================= 应用名 ================= */
QFrame QLabel {
    background: transparent;
}

/* ================= ScrollArea ================= */
QScrollArea {
    border: none;
}

/* ================= 滚动条 ================= */
QScrollBar:vertical {
    width: 8px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background: #c0c4cc;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #909399;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

/* ================= 日志 Label ================= */
QLabel {
    color: #606266;
}

#content {
    background: #f5f7fa;
    border-radius: 8px;
}
"""
PROGRESS_QSS = """/* ================= 下载进度对话框 ================= */
QProgressDialog {
    background-color: #ffffff;
    border-radius: 10px;
    border: 1px solid #ebeef5;
    min-width: 380px;
}

/* 文本 */
QProgressDialog QLabel {
    color: #303133;
    font-size: 13px;
}

/* 进度条 */
QProgressBar {
    height: 14px;
    border-radius: 7px;
    background: #ebeef5;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 7px;
    background-color: #409eff;
}

/* 取消按钮 */
QProgressDialog QPushButton {
    height: 30px;
    min-width: 80px;
    border-radius: 6px;
    background-color: #f56c6c;
    color: white;
}

QProgressDialog QPushButton:hover {
    background-color: #f78989;
}

QProgressDialog QPushButton:pressed {
    background-color: #dd6161;
}
"""

class UpdateThread(QThread):
    message = pyqtSignal(str)
    finished = pyqtSignal()

    def run(self):
        try:
            self.message.emit("正在检查更新…")
            checkUpdate()
            self.message.emit("启动中…")
        except Exception:
            self.message.emit("更新检查失败")
        self.finished.emit()


class TitleBar(QWidget):
    def __init__(self, parent, title=""):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(36)

        self.setStyleSheet(
            """
        QWidget {
            background: #2b2f3a;
        }
        QLabel {
            color: white;
            font-size: 13px;
        }
        QPushButton {
            border: none;
            width: 36px;
            height: 36px;
            color: white;
            font-size: 14px;
        }
        QPushButton:hover {
            background: #3c404c;
        }
        QPushButton#closeBtn:hover {
            background: #e81123;
        }
        """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)

        self.title_label = QLabel(title)
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.min_btn = QPushButton("—")
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")

        self.min_btn.clicked.connect(self.parent.showMinimized)
        self.close_btn.clicked.connect(self.parent.close)

        layout.addWidget(self.min_btn)
        layout.addWidget(self.close_btn)

        self._drag_pos = None

    # ===== 拖动窗口 =====
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.parent.move(self.parent.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class DownloadThread(QThread):
    progress = pyqtSignal(int)  # 发射下载进度
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, save_path, cancel_flag):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.cancel_flag = cancel_flag  # 外部传入取消状态

    def run(self):
        try:
            r = requests.get(self.url, stream=True, timeout=10)
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            with open(self.save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 50):
                    if self.cancel_flag["cancel"]:
                        print("用户取消下载")
                        break
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = int(downloaded * 100 / total)
                            self.progress.emit(percent)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()


class FetchAppDetailThread(QThread):
    finished = pyqtSignal(dict)  # 发射 detail

    def __init__(self, swdid, email, model, appid):
        super().__init__()
        self.swdid = swdid
        self.email = email
        self.model = model
        self.appid = appid

    def run(self):
        try:
            detail = get_app(self.swdid, self.email, self.model, self.appid)["data"]
            self.finished.emit(detail)
        except Exception as e:
            print("获取详细信息失败:", e)
            self.finished.emit({})


# ================= 卡片控件 =================
class AppCardWidget(QFrame):
    def __init__(self, app_data: dict, swdid: str, email: str, model: str):
        super().__init__()
        self.swdid = swdid
        self.email = email
        self.model = model
        self.app = app_data
        self.apk_url = ""

        bg_color = "#eaf3ff" if app_data.get("_source") == "策略应用" else "#fef6e4"
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {bg_color};
                border-radius: 10px;
                border: 1px solid #ddd;
            }}
        """
        )

        main = QHBoxLayout(self)
        main.setSpacing(15)

        # 图标
        self.icon_label = QLabel("加载中...")
        self.icon_label.setFixedSize(72, 72)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.icon_label)

        # 信息布局
        info = QVBoxLayout()
        self.name_label = QLabel(self.app.get("name", ""))
        self.name_label.setStyleSheet("font-size:16px;font-weight:bold;")
        info.addWidget(self.name_label)
        info.addWidget(QLabel(f"包名：{self.app.get('packagename','')}"))
        info.addWidget(
            QLabel(
                f"版本：{self.app.get('versionname','')} ({self.app.get('versioncode','')})"
            )
        )
        main.addLayout(info, 1)

        # 下载按钮
        action = QVBoxLayout()
        self.btn = QPushButton("下载")
        self.btn.setFixedWidth(120)
        self.btn.clicked.connect(self.download)
        action.addStretch()
        action.addWidget(self.btn)
        action.addStretch()
        main.addLayout(action)

        # **异步获取详细信息和图标**
        self.thread = FetchAppDetailThread(
            self.swdid, self.email, self.model, self.app["id"]
        )
        self.thread.finished.connect(self.update_detail)
        self.thread.start()

    def update_detail(self, detail):
        if not detail:
            self.icon_label.setText("No\nIcon")
            return
        icon_url = detail.get("iconpath", "")
        if icon_url:
            self.load_icon(self.icon_label, icon_url)
        self.apk_url = detail.get("path", "") + self.swdid

    def load_icon(self, label, url):
        try:
            r = requests.get(url, timeout=10)
            pix = QPixmap()
            pix.loadFromData(r.content)
            label.setPixmap(
                pix.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except Exception:
            label.setText("No\nIcon")

    def download(self):
        if not self.apk_url:
            print("APK 链接不存在")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存 APK", f"{self.name_label.text()}.apk", "APK Files (*.apk)"
        )
        if not save_path:
            return

        # 使用 dict 作为取消标志
        cancel_flag = {"cancel": False}

        progress_dialog = QProgressDialog(
            f"正在下载 {self.name_label.text()}...", "取消", 0, 100, self
        )
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setWindowTitle("下载应用")
        progress_dialog.setWindowIcon(QIcon(resource_path("icon.ico"))) 
        progress_dialog.canceled.connect(lambda: cancel_flag.update({"cancel": True}))
        progress_dialog.show()

        self.thread = DownloadThread(self.apk_url, save_path, cancel_flag)
        self.thread.progress.connect(progress_dialog.setValue)
        self.thread.finished.connect(progress_dialog.close)
        self.thread.start()


# ================= 清空布局工具 =================
def clear_layout(layout):
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)


# ================= 工作线程 =================
class Worker(QThread):
    log = pyqtSignal(str)
    apps_loaded = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, swdid, email, model):
        super().__init__()
        self.swdid = swdid
        self.email = email
        self.model = model

    def run(self):
        try:
            bind_device(self.swdid, self.email, self.model)
        

            apps = get_all_apps(self.swdid, self.email, self.model)
            self.apps_loaded.emit(apps)

        except Exception as e:
            print("绑定设备失败:", e)
            self.error_signal.emit("信息有误，绑定失败！请检查设备ID、机型和账号是否正确。")

# ================= 主窗口 =================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Linspirer App 获取工具")
        self.resize(800, 600)

        # 去系统标题栏
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setStyleSheet(MAIN_QSS)

        # ===== 根布局（VBox）=====
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(1, 1, 1, 1)

        # ===== 自定义标题栏 =====
        self.titlebar = TitleBar(self, "Linspirer App 获取工具")
        root.addWidget(self.titlebar)

        # ===== 内容区域（包一层 QWidget）=====
        content = QWidget()
        content.setObjectName("content")
        root.addWidget(content)

        # ===== 你原来的 GridLayout 放这里 =====
        layout = QGridLayout(content)

        self.swdid = QLineEdit()
        self.email = QLineEdit()
        self.model = QLineEdit()
        self.btn = QPushButton("登录")

        layout.addWidget(QLabel("设备号"), 0, 0)
        layout.addWidget(self.swdid, 0, 1)
        layout.addWidget(QLabel("账号"), 1, 0)
        layout.addWidget(self.email, 1, 1)
        layout.addWidget(QLabel("设备型号"), 2, 0)
        layout.addWidget(self.model, 2, 1)
        layout.addWidget(self.btn, 3, 0, 1, 2)

        # ===== ScrollArea =====
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setSpacing(12)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 5, 0, 1, 2)

        self.btn.clicked.connect(self.start)

    def start(self):
        clear_layout(self.vbox)  # 清空原卡片

        self.worker = Worker(
            self.swdid.text().strip(),
            self.email.text().strip(),
            self.model.text().strip(),
        )
        self.worker.error_signal.connect(lambda msg: QMessageBox.warning(self, "错误", msg))
        self.worker.apps_loaded.connect(self.show_apps)
        self.worker.start()

    def show_apps(self, apps):
        for app in apps:
            card = AppCardWidget(
                app,
                self.swdid.text().strip(),
                self.email.text().strip(),
                self.model.text().strip(),
            )
            self.vbox.addWidget(card)
        self.vbox.addStretch()


# ================= 入口 =================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # ===== Splash =====
    splash_pix = QPixmap(resource_path("launch.png"))
    splash = QSplashScreen(
        splash_pix,
        Qt.WindowType.WindowStaysOnTopHint,
    )
    
    splash.setEnabled(False)  #

    splash.show()

    # 初始文字（左下角）
    splash.showMessage(
        "正在检查更新",
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        Qt.GlobalColor.white,
    )

    app.processEvents()  # ★ 非常重要

    # ===== 主窗口（先创建，不显示）=====
    w = MainWindow()

    # ===== 更新线程 =====
    update_thread = UpdateThread()

    # 更新 splash 文本
    update_thread.message.connect(
        lambda msg: splash.showMessage(
            msg,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            QColor("#333333"),
        )
    )

    # 更新完成 → 显示主窗口
    def finish_startup():
        w.show()
        splash.finish(w)

    update_thread.finished.connect(finish_startup)
    update_thread.start()

    sys.exit(app.exec())
