import sys
import sqlite3
import datetime
import csv
import os
import darkdetect

from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineDownloadRequest, QWebEngineProfile
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QToolBar,
    QLineEdit,
    QTableWidget,
    QPushButton,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QFileDialog,
    QLabel,
    QHBoxLayout,
    QTabWidget,
    QMenuBar,
    QMenu,
    QDialog,
    QTabWidget
)
from PyQt6.QtCore import QUrl, QTimer, QFileInfo, Qt
from PyQt6.QtGui import QAction, QKeySequence, QPixmap, QImage

import qdarktheme


class WebTab(QWidget):
    def __init__(self, url):
        super().__init__()
        self.web_view = QWebEngineView(self)
        self.web_view.load(QUrl(url))
        
        layout = QVBoxLayout()
        layout.addWidget(self.web_view)
        self.setLayout(layout)

    
class PaperBrowser(QMainWindow):
    def __init__(self, is_incognito=False):
        super().__init__()

        self.app_theme = darkdetect.theme().lower()

        self.is_incognito = is_incognito

        # Подключаемся к существующей базе данных
        self.history_conn = sqlite3.connect("databases/history.sqlite")

        if self.is_incognito:
            self.profile = QWebEngineProfile("incognito", self)
            self.profile.setPersistentStoragePath("")
            self.profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
            )
            self.profile.setHttpCacheType(
                QWebEngineProfile.HttpCacheType.MemoryHttpCache
            )
            self.setWindowTitle("🕶️ Инкогнито")
        else:
            self.profile = QWebEngineProfile.defaultProfile()
            self.setWindowTitle("Paper Browser")

        self.progress_bar = QProgressBar()

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Paper Browser")
        self.setGeometry(100, 100, 1024, 768)

        qdarktheme.setup_theme(self.app_theme)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.menubar = self.menuBar()
        self.menu = self.menubar.addMenu('Меню')

        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.create_new_tab("https://google.com")

        # Добавляем progress_bar в layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.tabs)

        self.progress_bar.setVisible(False)

        self.create_actions()
        self.create_toolbar()

        self.init_database()

    def init_database(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_dir = os.path.join(base_dir, "databases")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "history.sqlite")
    
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS downloads_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT NOT NULL,
            path TEXT NOT NULL,
            time TIMESTAMP NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            visit_time TIMESTAMP
        );
        """)
        conn.commit()


    def create_actions(self):
        # Создать вкладку
        self.create_tab_action = QAction("+ Создать новую вкладку", self)
        self.create_tab_action.setShortcut(QKeySequence("F1"))
        self.create_tab_action.triggered.connect(lambda: self.create_new_tab("https://google.com"))
        # Действие "Назад"
        self.back_action = QAction("← Назад", self)
        self.back_action.setShortcut(QKeySequence("Alt+Left"))
        self.back_action.triggered.connect(lambda: self.get_current_webview().back() if self.get_current_webview() else None)
        self.back_action.setEnabled(False)

        self.forward_action = QAction("Вперед →", self)
        self.forward_action.setShortcut(QKeySequence("Alt+Right"))
        self.forward_action.triggered.connect(lambda: self.get_current_webview().forward() if self.get_current_webview() else None)
        self.forward_action.setEnabled(False)

        self.reload_action = QAction("Обновить ⟳", self)
        self.reload_action.setShortcut(QKeySequence("F5"))
        self.reload_action.triggered.connect(lambda: self.get_current_webview().reload() if self.get_current_webview() else None)

        self.home_action = QAction("Домой ⌂", self)
        self.home_action.setShortcut(QKeySequence("Ctrl+H"))
        self.home_action.triggered.connect(self.go_home)

        self.history_action = QAction("История", self)
        self.history_action.setShortcut(QKeySequence("Shift+X"))
        self.history_action.triggered.connect(self.history_open)

        self.about_project = QAction("О проекте", self)
        self.about_project.triggered.connect(self.aboutProject)
        self.menu.addAction(self.about_project)

        self.incognito = QAction("Инкогнито")
        self.incognito.triggered.connect(self.open_incognito)
        self.menu.addAction(self.incognito)

        self.new_window = QAction("Новое окно")
        self.new_window.triggered.connect(self.create_new_window)
        self.menu.addAction(self.new_window)

        self.theme_submenu = self.menu.addMenu("Тема")

        self.light_theme = QAction("Светлая")
        self.light_theme.triggered.connect(self.light)
        self.theme_submenu.addAction(self.light_theme)

        self.dark_theme = QAction("Темная")
        self.dark_theme.triggered.connect(self.dark)
        self.theme_submenu.addAction(self.dark_theme)

    def create_toolbar(self):
        self.toolbar.addAction(self.create_tab_action)
        self.toolbar.addAction(self.back_action)
        self.toolbar.addAction(self.forward_action)
        self.toolbar.addAction(self.reload_action)
        self.toolbar.addAction(self.home_action)
        self.toolbar.addAction(self.history_action)

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Введите адрес сайта...")
        self.address_bar.returnPressed.connect(self.navigate_to_url)
        self.toolbar.addWidget(self.address_bar)

        self.time = QLabel(self)
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_time)
        self.timer.start()
        self.update_time()
        self.toolbar.addWidget(self.time)

    def update_time(self):
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.time.setText(current_time)

    def aboutProject(self):
        window = AboutProjectWindow()
        window.exec()

    def navigate_to_url(self):
        url = self.address_bar.text().strip()
        if not url:
            return

        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.load_url(url)

    def create_new_tab(self, url):
        tab = WebTab(url)
        index = self.tabs.addTab(tab, "Новая вкладка")
        self.tabs.setCurrentIndex(index)
        
        web_view = tab.web_view
        web_view.loadStarted.connect(lambda: self.on_load_started(web_view))
        web_view.loadProgress.connect(self.on_load_progress)
        web_view.loadFinished.connect(lambda: self.on_load_finished(web_view))
        web_view.urlChanged.connect(lambda url: self.on_url_changed(url, web_view))
        web_view.titleChanged.connect(lambda title: self.on_title_changed(title, web_view))
        web_view.page().profile().downloadRequested.connect(self.on_download_requested)
        
        return tab
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            QMessageBox.information(self, "Информация", "Нельзя закрыть последнюю вкладку")

    def get_current_webview(self):
        current_index = self.tabs.currentIndex()
        if current_index >= 0:
            tab = self.tabs.widget(current_index)
            if tab:
                return tab.web_view
        return None
    
    def load_url(self, url): 
        web_view = self.get_current_webview()
        if web_view:
            web_view.load(QUrl(url))

    def go_home(self):
        web_view = self.get_current_webview()
        if web_view:
            web_view.load(QUrl('https://google.com'))

    def on_load_started(self, tab):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.update_navigation_buttons(tab)

    def on_load_progress(self, progress):
        self.progress_bar.setValue(progress)

    def on_load_finished(self, tab):
        self.progress_bar.setVisible(False)
        self.update_navigation_buttons(tab)
        # Добавляем страницу в историю после загрузки
        current_url = tab.url().toString()
        self.add_to_history(current_url)

    def on_url_changed(self, url, tab):
        self.address_bar.setText(url.toString())
        self.update_navigation_buttons(tab)

    def on_title_changed(self, title, tab):
        if self.is_incognito:
            self.setWindowTitle(f"{title} - Paper Browser (Инкогнито)")
        self.setWindowTitle(f"{title} - Paper Browser")
        # Обновляем название вкладки
        index = self.tabs.currentIndex()
        if index >= 0:
            tab_title = title if title else "Новая вкладка"
            self.tabs.setTabText(index, tab_title[:30])

    def update_navigation_buttons(self, tab):
        history = tab.history()
        self.back_action.setEnabled(history.canGoBack())
        self.forward_action.setEnabled(history.canGoForward())

    def on_download_requested(self, download):
        """Обрабатывает запрос на загрузку файла с автоматическим сохранением"""
        # Получаем оригинальное имя файла из URL
        url_path = download.url().path()
        original_file_name = QFileInfo(url_path).fileName()

        # Если имя файла пустое, генерируем имя на основе текущего времени
        if not original_file_name or original_file_name == "/":
            original_file_name = (
                f"download_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

        # Получаем расширение файла
        suffix = QFileInfo(original_file_name).suffix()

        # Если расширения нет, пытаемся определить его из MIME-типа
        if not suffix:
            mime_type = download.mimeType()
            if mime_type:
                # Сопоставляем MIME-типы с расширениями
                mime_to_extension = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/gif": "gif",
                    "image/webp": "webp",
                    "image/bmp": "bmp",
                    "image/tiff": "tiff",
                    "application/pdf": "pdf",
                    "text/plain": "txt",
                    "text/html": "html",
                    "text/css": "css",
                    "text/x-python": "py",
                    "text/rtf": "rtf",
                    "text/xml": "xml",
                    "text/csv": "csv",
                    "application/zip": "zip",
                    "application/x-rar-compressed": "rar",
                    "application/x-7z-compressed": "7z",
                    "application/gzip": "gz",
                    "application/tar+gzip": "tar.gz",
                    "application/msword": "doc",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                    "application/vnd.ms-excel": "xls",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
                    "application/vnd.ms-powerpoint": "ppt",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
                    "application/vnd.android.package-archive": "apk",
                    "application/x-sqlite3": "sqlite",
                    "audio/mp3": "mp3",
                    "audio/wav": "wav",
                    "audio/mp4": "mp4",
                    "audio/mpeg": "mpeg",
                    "video/mpeg": "mpeg",
                    "video/mp4": "mp4",
                    "video/avi": "avi",
                    "video/webp": "webp",
                    "video/h264": "h264",
                    "video/h265": "h265",
                }
                suffix = mime_to_extension.get(mime_type, "")

            # Если все еще нет расширения, используем 'bin'
            if not suffix:
                suffix = "bin"

            original_file_name = f"{original_file_name}.{suffix}"

        # Выбираем папку для загрузок (можно изменить на нужную)
        download_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для загрузки",
            "",  # Начальная директория (пустая = домашняя папка)
        )

        if download_dir:
            # Формируем полный путь
            save_path = os.path.join(download_dir, original_file_name)

            # Если файл уже существует, добавляем номер
            counter = 1
            base_name = original_file_name
            while os.path.exists(save_path):
                name_part = os.path.splitext(base_name)[0]
                ext_part = os.path.splitext(base_name)[1]
                save_path = os.path.join(
                    download_dir, f"{name_part}_{counter}{ext_part}"
                )
                counter += 1

            # Устанавливаем параметры загрузки
            download.setDownloadDirectory(download_dir)
            download.setDownloadFileName(os.path.basename(save_path))
            download.accept()

            # Добавляем в историю загрузок
            self.add_to_downloads(
                download.url().toString(),
                os.path.basename(save_path),
            )
        else:
            download.cancel()

    def add_to_history(self, url):
        # Проверяет не в режиме инкогнито ли окно
        if self.is_incognito:
            return
        
        """Добавляет страницу в историю с системным временем"""
        try:
            cursor = self.history_conn.cursor()
            # Используем текущее системное время
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO visit_history (url, visit_time) VALUES (?, ?)",
                [url, current_time],
            )
            self.history_conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении в историю: {e}")

    def add_to_downloads(self, file_name, save_path):
        if self.is_incognito:
            return

        """Добавляет загрузку в историю"""
        try:
            cursor = self.history_conn.cursor()
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO downloads_history (file, path, time) 
                VALUES (?, ?, ?)
            """,
                [file_name, save_path, current_time],
            )
            self.history_conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении в историю загрузок: {e}")

    def history_open(self):
        """Открывает окно истории"""
        try:
            self.history_window = BrowserHistory()
            self.history_window.show()
        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось открыть историю: {str(e)}"
            )

    def closeEvent(self, event):
        try:
            self.history_conn.close()
        except:
            pass
        event.accept()

    def open_incognito(self):
        self.incognito_window = PaperBrowser(is_incognito=True)
        self.incognito_window.show()
    
    def create_new_window(self):
        self.win = PaperBrowser()
        self.win.show()
    
    def light(self):
        self.app_theme = "light"
        qdarktheme.setup_theme(self.app_theme)

    def dark(self):
        self.app_theme = "dark"
        qdarktheme.setup_theme(self.app_theme)

class BrowserHistory(QMainWindow):
    """Окно для просмотра истории браузера и загрузок"""
    def __init__(self):
        super().__init__()
        # Используем ту же базу данных, что и основной браузер
        self.history_conn = sqlite3.connect("databases/history.sqlite")
        self.initUI()
        self.load_history()

    def initUI(self):
        self.setGeometry(100, 100, 900, 700)
        self.setWindowTitle("История браузера")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Создаем вкладки
        self.tabs = QTabWidget()

        # Вкладка истории посещений
        self.history_tab = QWidget()
        self.history_layout = QVBoxLayout(self.history_tab)
        self.setup_history_tab()

        # Вкладка истории скачиваний
        self.downloads_tab = QWidget()
        self.downloads_layout = QVBoxLayout(self.downloads_tab)
        self.setup_downloads_tab()

        self.tabs.addTab(self.history_tab, "История посещений")
        self.tabs.addTab(self.downloads_tab, "История загрузок")

        layout.addWidget(self.tabs)

        # Кнопки управления
        self.setup_buttons(layout)

    def setup_history_tab(self):
        """Настраивает вкладку истории посещений"""
        # Таблица истории посещений
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(2)
        self.history_table.setHorizontalHeaderLabels(["Время посещения", "Сайт"])
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.history_layout.addWidget(self.history_table)

    def setup_downloads_tab(self):
        """Настраивает вкладку истории скачиваний"""
        # Таблица истории скачиваний
        self.downloads_table = QTableWidget()
        self.downloads_table.setColumnCount(3)
        self.downloads_table.setHorizontalHeaderLabels(
            ["Файл", "Путь сохранения", "Время загрузки"]
        )
        self.downloads_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.downloads_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.downloads_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.downloads_layout.addWidget(self.downloads_table)

    def setup_buttons(self, layout):
        """Настраивает кнопки управления"""
        button_layout = QHBoxLayout()

        # Кнопки для истории посещений
        self.clear_history_btn = QPushButton("Очистить историю посещений")
        self.clear_history_btn.clicked.connect(self.clear_history)
        button_layout.addWidget(self.clear_history_btn)

        # Кнопки для истории загрузок
        self.clear_downloads_btn = QPushButton("Очистить историю загрузок")
        self.clear_downloads_btn.clicked.connect(self.clear_downloads)
        button_layout.addWidget(self.clear_downloads_btn)

        self.save_history_btn = QPushButton("Сохранить историю в CSV")
        self.save_history_btn.clicked.connect(self.save_history_as_csv)
        button_layout.addWidget(self.save_history_btn)

        self.save_downloads_btn = QPushButton("Сохранить загрузки в CSV")
        self.save_downloads_btn.clicked.connect(self.save_downloads_as_csv)
        button_layout.addWidget(self.save_downloads_btn)

        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.load_history)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

    def load_history(self):
        """Загружает обе истории"""
        self.load_visit_history()
        self.load_downloads_history()

    def load_visit_history(self):
        """Загружает историю посещений"""
        try:
            cursor = self.history_conn.cursor()
            cursor.execute(
                "SELECT visit_time, url FROM visit_history ORDER BY visit_time DESC"
            )
            history_data = cursor.fetchall()

            self.history_table.setRowCount(len(history_data))

            for row, (visit_time, url) in enumerate(history_data):
                time_display = str(visit_time) if visit_time else "Неизвестно"
                self.history_table.setItem(row, 0, QTableWidgetItem(time_display))
                self.history_table.setItem(row, 1, QTableWidgetItem(url))

        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить историю посещений: {str(e)}"
            )

    def load_downloads_history(self):
        """Загружает историю скачиваний"""
        try:
            cursor = self.history_conn.cursor()
            cursor.execute(
                """
                SELECT file, path, time 
                FROM downloads_history ORDER BY time DESC
            """
            )
            downloads_data = cursor.fetchall()

            self.downloads_table.setRowCount(len(downloads_data))

            for row, (file_name, save_path, download_time) in enumerate(downloads_data):
                # Имя файла
                self.downloads_table.setItem(row, 0, QTableWidgetItem(file_name))

                # Путь сохранения
                self.downloads_table.setItem(row, 1, QTableWidgetItem(save_path))

                # Время
                time_display = str(download_time) if download_time else "Неизвестно"
                self.downloads_table.setItem(row, 2, QTableWidgetItem(time_display))

        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить историю загрузок: {str(e)}"
            )

    def clear_history(self):
        """Очищает историю посещений"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите очистить историю посещений?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.history_conn.cursor()
                cursor.execute("DELETE FROM visit_history")
                self.history_conn.commit()
                self.history_table.setRowCount(0)
                QMessageBox.information(self, "Успех", "История посещений очищена")
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", f"Ошибка при очистке истории: {str(e)}"
                )

    def clear_downloads(self):
        """Очищает историю загрузок"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите очистить историю загрузок?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.history_conn.cursor()
                cursor.execute("DELETE FROM downloads_history")
                self.history_conn.commit()
                self.downloads_table.setRowCount(0)
                QMessageBox.information(self, "Успех", "История загрузок очищена")
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", f"Ошибка при очистке истории загрузок: {str(e)}"
                )

    def save_history_as_csv(self):
        """Экспорт истории посещений в CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт истории посещений",
            "browser_history.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        try:
            cursor = self.history_conn.cursor()
            cursor.execute("SELECT visit_time, url FROM visit_history")
            rows = cursor.fetchall()

            with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["Visit Time", "URL"])
                writer.writerows(rows)

            QMessageBox.information(
                self,
                "Успех",
                f"История посещений экспортирована:\n{file_path}\n\nЗаписей: {len(rows)}",
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось экспортировать историю посещений:\n{str(e)}",
            )

    def save_downloads_as_csv(self):
        """Экспорт истории загрузок в CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт истории загрузок",
            "downloads_history.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        try:
            cursor = self.history_conn.cursor()
            cursor.execute("SELECT file, path, time FROM downloads")
            rows = cursor.fetchall()

            with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["File Name", "Save Path", "Download Time"])
                writer.writerows(rows)

            QMessageBox.information(
                self,
                "Успех",
                f"История загрузок экспортирована:\n{file_path}\n\nЗаписей: {len(rows)}",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось экспортировать историю загрузок:\n{str(e)}"
            )

    def closeEvent(self, event):
        """Закрывает соединение с базой данных при закрытии окна"""
        self.history_conn.close()
        event.accept()


class AboutProjectWindow(QDialog):
    """Окно с информацией о проекте"""
    def __init__(self):
        super().__init__()
        self.count = 0
        self.initUI()

    def initUI(self):
        self.setFixedSize(800, 600)
        self.setWindowTitle("О проекте")

        central_widget = QWidget()

        self.mystery_button = QPushButton('Нажми меня', self)
        self.mystery_button.clicked.connect(self.mystery)
        self.text = QLabel("""
Суть проекта сделать простой веб-браузер для серфинга по просторам интернета.
Браузер реализован на фреймворке PyQt6-WebEngine, который основан на движке Chromium.
В браузере есть панель для управления вкладками и историей, реализована панель через QToolBar.
История реализована через SQlite базу данных, запись данных и очистка истории реализована через SQL-запросы.
Открывается история в отдельном окне в виде таблицы.
В истории записывается время посещения сайта и URL-адрес.
Время записывается с помощью модуля datetime.
Также имеется функция сохранить историю посещений в виде csv-таблицы.
Можно открыть окно в режиме инкогнито.
        """)
        self.text.setWordWrap(True)

        self.ok = QPushButton("ok", self)
        self.ok.clicked.connect(self.close)

        # layout для информации
        layout = QHBoxLayout(central_widget)
        layout.addWidget(self.text)

        # Основной layout для всего окна
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.mystery_button)  # добавляем кнопку
        main_layout.addWidget(central_widget)
        main_layout.addWidget(self.ok)

        self.setLayout(main_layout)

    def mystery(self):
        # Нажимаешь 4 раза кнопку и появляется пасхалка
        self.count += 1
        if self.count >= 4:
            self.close()
            window = EasterEgg()
            window.exec()


class EasterEgg(QDialog):
    """Небольшая пасхалочка)"""
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setFixedSize(800, 600)
        self.setWindowTitle("Внезапный кот")

        # Кот-абьюзер - горе в семье
        self.text = QLabel("Этот пушистик держит в рабстве разработчика, чтобы тот его кормил и гладил.")
        self.text.setWordWrap(True)

        self.picture = QLabel()
        self.pixmap = QPixmap('pictures/kot.jpg')

        self.picture.setPixmap(self.pixmap)

        self.ok = QPushButton("Ok")
        self.ok.clicked.connect(self.close)

        # layout для всего окна
        layout = QVBoxLayout()

        # layout для информации в окне
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.text)
        content_layout.addWidget(self.picture)

        layout.addLayout(content_layout)
        layout.addWidget(self.ok)

        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    browser = PaperBrowser()
    browser.show()

    sys.exit(app.exec())
