import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from download_engine import ComponentManager, DownloadEngine
import threading
import os
import sys
import subprocess
import winreg
import locale
import webbrowser
import time
import json


class YoutubeDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("600x600")

        # Localization
        self.current_lang = 'en'
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang and sys_lang.startswith('zh'):
                self.current_lang = 'zh'
        except:
            pass

        self.texts = {
            'en': {
                'title': "YouTube Video Downloader",
                'url_label': "Video URL",
                'analyze_btn': "Analyze",
                'info_label': "Video Info",
                'info_placeholder': "Please enter URL and click Analyze...",
                'res_label': "Select Resolution:",
                'path_label': "Download Location",
                'browse_btn': "Browse...",
                'open_btn': "Open Folder",
                'download_btn': "Start Download",
                'ready': "Ready",
                'analyzing': "Analyzing video info...",
                'analysis_failed': "Analysis failed",
                'analysis_complete': "Analysis complete. Select resolution and download.",
                'preparing': "Preparing download...",
                'downloading': "Downloading...",
                'processing': "Download complete, processing merge...",
                'complete': "Download Complete!",
                'success_title': "Success",
                'success_msg': "Video download completed!",
                'error_title': "Error",
                'warning_title': "Warning",
                'url_empty': "Please enter video URL",
                'path_error': "Cannot create directory",
                'download_failed': "Download failed",
                'best_quality': "Best Quality (Auto)",
                'approx': "approx.",
                'lang_btn': "中文",
                'ffmpeg_btn': "Add FFmpeg to PATH",
                'ffmpeg_success': "FFmpeg added to PATH successfully!",
                'ffmpeg_not_found': "FFmpeg folder not found in application directory.\nPlease ensure 'ffmpeg' folder exists.",
                'ffmpeg_exists': "FFmpeg is already in your PATH.",
                'ffmpeg_error': "Failed to add FFmpeg to PATH: ",
                'tab_download': "Downloader",
                'tab_history': "History",
                'pause_btn': "Pause",
                'resume_btn': "Resume",
                'stop_btn': "Stop",
                'col_id': "No.",
                'col_name': "Name",
                'col_url': "URL",
                'col_path': "Path",
                'col_res': "Resolution",
                'stopped': "Download Stopped",
                'stopped_msg': "Download has been stopped by user.",
                'clear_btn': "Clear History",
                'cleared_msg': "History cleared.",
                'paste_btn': "Paste",
            },
            'zh': {
                'title': "YouTube 影片下載器",
                'url_label': "影片網址",
                'analyze_btn': "分析影片",
                'info_label': "影片資訊",
                'info_placeholder': "請輸入網址並點擊分析...",
                'res_label': "選擇解析度:",
                'path_label': "下載位置",
                'browse_btn': "瀏覽...",
                'open_btn': "開啟資料夾",
                'download_btn': "開始下載",
                'ready': "就緒",
                'analyzing': "正在分析影片資訊...",
                'analysis_failed': "分析失敗",
                'analysis_complete': "分析完成，請選擇解析度並下載",
                'preparing': "準備下載...",
                'downloading': "下載中...",
                'processing': "下載完成，正在處理合併...",
                'complete': "下載完成！",
                'success_title': "成功",
                'success_msg': "影片下載完成！",
                'error_title': "錯誤",
                'warning_title': "警告",
                'url_empty': "請輸入影片網址",
                'path_error': "無法建立資料夾",
                'download_failed': "下載失敗",
                'best_quality': "最高畫質 (自動選擇)",
                'approx': "約",
                'lang_btn': "English",
                'ffmpeg_btn': "加入 FFmpeg 到環境變數",
                'ffmpeg_success': "成功將 FFmpeg 加入環境變數！",
                'ffmpeg_not_found': "在程式目錄下找不到 'ffmpeg' 資料夾。\n請確認 'ffmpeg' 資料夾是否存在。",
                'ffmpeg_exists': "FFmpeg 已經在您的環境變數中了。",
                'ffmpeg_error': "加入 FFmpeg 失敗: ",
                'tab_download': "下載",
                'tab_history': "歷史紀錄",
                'pause_btn': "暫停",
                'resume_btn': "繼續",
                'stop_btn': "停止",
                'col_id': "編號",
                'col_name': "影片名稱",
                'col_url': "下載網址",
                'col_path': "下載位置",
                'col_res': "解析度",
                'stopped': "下載已停止",
                'stopped_msg': "使用者已停止下載。",
                'clear_btn': "清除歷史紀錄",
                'cleared_msg': "歷史紀錄已清除。",
                'paste_btn': "貼上",
            }
        }

        # Variables
        self.url_var = tk.StringVar()
        default_download_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        self.path_var = tk.StringVar(value=default_download_path)
        self.status_var = tk.StringVar(value=self.get_text('ready'))
        self.video_info = None
        self.resolutions = []
        self.components = ComponentManager()
        self.engine = DownloadEngine(self.components)
        self.component_status = tk.StringVar()
        self.update_running = False
        self.download_running = False

        # Control flags
        self.is_paused = False
        self.is_stopped = False
        self.temp_files = set()

        # Determine path for history file (handle PyInstaller path)
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))

        self.history_file = os.path.join(application_path, 'history.json')
        self.load_history()

        # Create UI
        self.create_widgets()

        # Ensure download directory exists
        if not os.path.exists(self.path_var.get()):
            try:
                os.makedirs(self.path_var.get())
            except OSError:
                pass

        # Auto add ffmpeg to PATH
        self.auto_add_ffmpeg_path()
        self.root.protocol('WM_DELETE_WINDOW', self.close_application)
        self.root.after(300, self.start_component_update)

    def close_application(self):
        self.is_stopped = True
        self.engine.cancel()
        self.root.destroy()

    def start_component_update(self, manual=False):
        if self.update_running:
            return
        self.update_running = True
        self.btn_update.config(state=tk.DISABLED)
        self.component_status.set('正在檢查下載元件…' if self.current_lang == 'zh' else 'Checking download engine...')
        threading.Thread(target=self.update_components, args=(manual,), daemon=True).start()

    def update_components(self, manual):
        try:
            result = self.components.update(force=manual)
        except Exception as error:
            result = {'status': 'failed', 'version': '', 'error': str(error)}
        self.root.after(0, self.component_update_finished, result)

    def component_update_finished(self, result):
        self.update_running = False
        self.btn_update.config(state=tk.NORMAL)
        text = f"yt-dlp {result['version']}"
        if result['error']:
            text += '｜更新未完成，保留現有版本' if self.current_lang == 'zh' else ' | Update unavailable; existing version kept'
        else:
            text += '｜已更新' if self.current_lang == 'zh' else ' | Up to date'
        self.component_status.set(text)

    def get_text(self, key):
        return self.texts[self.current_lang].get(key, key)

    def toggle_language(self):
        prev_lang = self.current_lang
        self.current_lang = 'zh' if self.current_lang == 'en' else 'en'

        # Try to translate current status
        current_status = self.status_var.get()
        found_key = None
        for key, value in self.texts[prev_lang].items():
            if value == current_status:
                found_key = key
                break

        if found_key:
            self.status_var.set(self.get_text(found_key))

        self.update_ui_text()

    def update_ui_text(self):
        self.root.title(self.get_text('title'))
        # Update Tabs
        if hasattr(self, 'notebook'):
            self.notebook.tab(self.tab_download, text=self.get_text('tab_download'))
            self.notebook.tab(self.tab_history, text=self.get_text('tab_history'))

        self.url_frame.config(text=self.get_text('url_label'))
        self.btn_analyze.config(text=self.get_text('analyze_btn'))
        if hasattr(self, 'btn_paste'):
            self.btn_paste.config(text=self.get_text('paste_btn'))
        self.info_frame.config(text=self.get_text('info_label'))
        if not self.video_info:
            self.lbl_title.config(text=self.get_text('info_placeholder'))
        self.lbl_res.config(text=self.get_text('res_label'))
        self.path_frame.config(text=self.get_text('path_label'))
        self.btn_browse.config(text=self.get_text('browse_btn'))
        self.btn_open.config(text=self.get_text('open_btn'))
        self.btn_download.config(text=self.get_text('download_btn'))
        self.btn_lang.config(text=self.get_text('lang_btn'))
        self.btn_update.config(text='立即更新' if self.current_lang == 'zh' else 'Update Engine')

        # Update control buttons
        if hasattr(self, 'btn_pause'):
            pause_text = self.get_text('resume_btn') if self.is_paused else self.get_text('pause_btn')
            self.btn_pause.config(text=pause_text)
            self.btn_stop.config(text=self.get_text('stop_btn'))

        # Update History UI
        if hasattr(self, 'tree'):
            self.tree.heading('id', text=self.get_text('col_id'))
            self.tree.heading('name', text=self.get_text('col_name'))
            self.tree.heading('url', text=self.get_text('col_url'))
            self.tree.heading('path', text=self.get_text('col_path'))
            self.tree.heading('res', text=self.get_text('col_res'))

        if hasattr(self, 'btn_clear'):
            self.btn_clear.config(text=self.get_text('clear_btn'))

        # Update status if it's a static message
        current_status = self.status_var.get()
        # Simple check if status matches one of our static keys
        for key in ['ready', 'analyzing', 'analysis_failed', 'analysis_complete', 'preparing', 'complete']:
            # This is a bit tricky because status changes dynamically.
            # For now, just reset to ready if it was ready, or leave it.
            pass

        # Update combobox if populated
        if self.resolutions:
            current_idx = self.combo_res.current()
            self.update_combobox_values()
            if current_idx >= 0:
                self.combo_res.current(current_idx)

    def update_combobox_values(self):
        values = []
        approx_text = self.get_text('approx')
        for res in self.resolutions:
            size_str = ""
            if res['filesize']:
                size_mb = res['filesize'] / 1024 / 1024
                size_str = f" - {approx_text} {size_mb:.1f}MB"
            values.append(f"{res['height']}p ({res['ext']}){size_str}")

        values.append(self.get_text('best_quality'))
        self.combo_res['values'] = values

    def load_history(self):
        self.history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except:
                self.history = []

    def save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def insert_into_tree(self, item):
        # Truncate for display
        name = item['name']
        url = item['url']
        path = item['path']
        res = item['res']
        idx = item['id']

        display_name = name if len(name) <= 20 else name[:20] + "..."
        display_url = url if len(url) <= 20 else url[:20] + "..."
        display_path = path if len(path) <= 20 else path[:20] + "..."

        self.tree.insert('', 0, values=(idx, display_name, display_url, display_path, res))

    def create_widgets(self):
        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1
        self.tab_download = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_download, text=self.get_text('tab_download'))

        # Tab 2
        self.tab_history = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_history, text=self.get_text('tab_history'))

        self.create_download_ui(self.tab_download)
        self.create_history_ui(self.tab_history)

    def create_history_ui(self, parent):
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        self.btn_clear = ttk.Button(toolbar, text=self.get_text('clear_btn'), command=self.clear_history)
        self.btn_clear.pack(side=tk.RIGHT)

        # Treeview
        columns = ('id', 'name', 'url', 'path', 'res')
        self.tree = ttk.Treeview(parent, columns=columns, show='headings')

        self.tree.heading('id', text=self.get_text('col_id'))
        self.tree.heading('name', text=self.get_text('col_name'))
        self.tree.heading('url', text=self.get_text('col_url'))
        self.tree.heading('path', text=self.get_text('col_path'))
        self.tree.heading('res', text=self.get_text('col_res'))

        self.tree.column('id', width=40, anchor='center')
        self.tree.column('name', width=150)
        self.tree.column('url', width=120)
        self.tree.column('path', width=120)
        self.tree.column('res', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', self.on_history_click)

        # Populate existing history
        for item in self.history:
            self.insert_into_tree(item)

    def clear_history(self):
        if not self.history:
            return
        if messagebox.askyesno(self.get_text('warning_title'), "Are you sure you want to clear history?"):
            self.history = []
            self.save_history()
            for item in self.tree.get_children():
                self.tree.delete(item)
            messagebox.showinfo(self.get_text('success_title'), self.get_text('cleared_msg'))

    def create_download_ui(self, parent):
        main_frame = parent

        # Top Bar (Language)
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_lang = ttk.Button(top_frame, text=self.get_text('lang_btn'), command=self.toggle_language)
        self.btn_lang.pack(side=tk.RIGHT)
        self.btn_update = ttk.Button(top_frame, text='立即更新' if self.current_lang == 'zh' else 'Update Engine',
                                     command=lambda: self.start_component_update(manual=True))
        self.btn_update.pack(side=tk.LEFT)
        ttk.Label(top_frame, textvariable=self.component_status, wraplength=380).pack(side=tk.LEFT, padx=8)

        # URL Section
        self.url_frame = ttk.LabelFrame(main_frame, text=self.get_text('url_label'), padding="10")
        self.url_frame.pack(fill=tk.X, pady=(0, 10))

        entry_url = ttk.Entry(self.url_frame, textvariable=self.url_var)
        entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_analyze = ttk.Button(self.url_frame, text=self.get_text('analyze_btn'), command=self.start_analysis)
        self.btn_analyze.pack(side=tk.RIGHT)

        self.btn_paste = ttk.Button(self.url_frame, text=self.get_text('paste_btn'), command=self.paste_url)
        self.btn_paste.pack(side=tk.RIGHT, padx=(0, 5))

        # Video Info Section
        self.info_frame = ttk.LabelFrame(main_frame, text=self.get_text('info_label'), padding="10")
        self.info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.lbl_title = ttk.Label(self.info_frame, text=self.get_text('info_placeholder'), wraplength=500)
        self.lbl_title.pack(anchor=tk.W, pady=(0, 10))

        # Resolution Selection
        res_frame = ttk.Frame(self.info_frame)
        res_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_res = ttk.Label(res_frame, text=self.get_text('res_label'))
        self.lbl_res.pack(side=tk.LEFT, padx=(0, 10))
        self.combo_res = ttk.Combobox(res_frame, state="readonly")
        self.combo_res.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Download Path Section
        self.path_frame = ttk.LabelFrame(main_frame, text=self.get_text('path_label'), padding="10")
        self.path_frame.pack(fill=tk.X, pady=(0, 10))

        entry_path = ttk.Entry(self.path_frame, textvariable=self.path_var)
        entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_browse = ttk.Button(self.path_frame, text=self.get_text('browse_btn'), command=self.browse_directory)
        self.btn_browse.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_open = ttk.Button(self.path_frame, text=self.get_text('open_btn'), command=self.open_download_folder)
        self.btn_open.pack(side=tk.LEFT)

        # Progress Section
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 5))

        self.lbl_status = ttk.Label(progress_frame, textvariable=self.status_var)
        self.lbl_status.pack(anchor=tk.W)

        # Action Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        self.btn_download = ttk.Button(btn_frame, text=self.get_text('download_btn'), command=self.start_download, state=tk.DISABLED)
        self.btn_download.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_pause = ttk.Button(btn_frame, text=self.get_text('pause_btn'), command=self.toggle_pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_stop = ttk.Button(btn_frame, text=self.get_text('stop_btn'), command=self.stop_download, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)

    def paste_url(self):
        try:
            clipboard_content = self.root.clipboard_get()
            self.url_var.set(clipboard_content)
        except:
            pass

    def browse_directory(self):
        directory = filedialog.askdirectory(initialdir=self.path_var.get())
        if directory:
            self.path_var.set(directory)

    def open_download_folder(self):
        path = self.path_var.get()
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showerror(self.get_text('error_title'), str(e))
        else:
            messagebox.showwarning(self.get_text('warning_title'), self.get_text('path_error'))

    def auto_add_ffmpeg_path(self):
        # Look for ffmpeg folder in current directory
        cwd = os.getcwd()
        ffmpeg_dir = os.path.join(cwd, 'ffmpeg')
        ffmpeg_bin = os.path.join(ffmpeg_dir, 'bin')

        target_path = None
        if os.path.exists(ffmpeg_bin):
            target_path = ffmpeg_bin
        elif os.path.exists(ffmpeg_dir):
            target_path = ffmpeg_dir

        if not target_path:
            return

        # Check if already in PATH (current process)
        current_path = os.environ.get('PATH', '')
        if target_path.lower() in current_path.lower():
            return

        try:
            # Add to current process PATH
            os.environ['PATH'] = target_path + os.pathsep + current_path

            # Add to User PATH permanently using registry
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_ALL_ACCESS)
            try:
                user_path, _ = winreg.QueryValueEx(key, 'Path')
            except WindowsError:
                user_path = ''

            if target_path.lower() not in user_path.lower():
                new_path = target_path + os.pathsep + user_path
                winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)

            winreg.CloseKey(key)
        except Exception:
            pass

    def start_analysis(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(self.get_text('warning_title'), self.get_text('url_empty'))
            return

        self.status_var.set(self.get_text('analyzing'))
        self.root.update_idletasks()

        threading.Thread(target=self.analyze_video, args=(url,), daemon=True).start()

    def analyze_video(self, url):
        try:
            info = self.engine.extract_info(url)
            if info:

                formats = info.get('formats', [])
                seen_heights = set()
                self.resolutions = []

                formats.sort(key=lambda x: (x.get('height') or 0), reverse=True)

                for f in formats:
                    height = f.get('height')
                    if height and height not in seen_heights and f.get('vcodec') != 'none':
                        self.resolutions.append({
                            'height': height,
                            'format_id': f['format_id'],
                            'ext': f['ext'],
                            'filesize': f.get('filesize', 0)
                        })
                        seen_heights.add(height)

                self.root.after(0, self.update_ui_after_analysis, info)

        except Exception as e:
            self.root.after(0, lambda error=str(e): messagebox.showerror(self.get_text('error_title'), f"{self.get_text('analysis_failed')}: {error}"))
            self.root.after(0, lambda: self.status_var.set(self.get_text('analysis_failed')))

    def update_ui_after_analysis(self, info):
        self.video_info = info
        self.lbl_title.config(text=info.get('title', 'Unknown Title'))
        self.update_combobox_values()

        if self.resolutions:
            self.combo_res.current(0)
            self.btn_download['state'] = tk.NORMAL

        self.status_var.set(self.get_text('analysis_complete'))

    def on_history_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            # column = self.tree.identify_column(event.x) # This returns #1, #2 etc.
            item_id = self.tree.identify_row(event.y)
            if not item_id:
                return

            item = self.tree.item(item_id)
            # Get ID from first column (index 0)
            try:
                record_id = item['values'][0]
            except:
                return

            # Find full record
            record = next((r for r in self.history if r['id'] == record_id), None)
            if not record:
                return

            column = self.tree.identify_column(event.x)

            # Column #3 is URL
            if column == '#3':
                url = record['url']
                if url:
                    webbrowser.open(url)
            # Column #4 is Path
            elif column == '#4':
                path = record['path']
                if os.path.exists(path):
                    try:
                        if os.path.isfile(path):
                            subprocess.run(['explorer', '/select,', os.path.normpath(path)])
                        else:
                            os.startfile(os.path.dirname(path))
                    except:
                        pass

    def add_to_history(self, name, url, path, res):
        idx = len(self.history) + 1
        item = {
            'id': idx,
            'name': name,
            'url': url,
            'path': path,
            'res': res
        }
        self.history.append(item)
        self.save_history()
        self.insert_into_tree(item)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        pause_text = self.get_text('resume_btn') if self.is_paused else self.get_text('pause_btn')
        self.btn_pause.config(text=pause_text)
        if self.is_paused:
            self.status_var.set("Paused")
        else:
            self.status_var.set("Resumed")

    def stop_download(self):
        if messagebox.askyesno(self.get_text('warning_title'), "Are you sure you want to stop the download?"):
            self.is_stopped = True
            self.status_var.set(self.get_text('stopped'))

    def start_download(self):
        if not self.video_info:
            return

        selection_idx = self.combo_res.current()
        if selection_idx == -1:
            return

        download_path = self.path_var.get()
        if not os.path.exists(download_path):
            try:
                os.makedirs(download_path)
            except Exception as e:
                messagebox.showerror(self.get_text('error_title'), f"{self.get_text('path_error')}: {str(e)}")
                return

        self.btn_download['state'] = tk.DISABLED
        self.download_running = True
        self.download_url = self.video_info.get('webpage_url') or self.url_var.get().strip()
        self.btn_analyze.config(state=tk.DISABLED)
        self.btn_pause['state'] = tk.NORMAL
        self.btn_stop['state'] = tk.NORMAL
        self.status_var.set(self.get_text('preparing'))
        self.progress['value'] = 0

        # Reset flags
        self.is_paused = False
        self.is_stopped = False
        self.temp_files = set()

        # Determine format
        target_height = None
        if selection_idx < len(self.resolutions):
            target_height = self.resolutions[selection_idx]['height']
            format_str = f'bestvideo[height={target_height}]+bestaudio/best[height={target_height}]'
        else:
            format_str = 'bestvideo+bestaudio/best'
            target_height = "Best"

        threading.Thread(target=self.download_process, args=(download_path, format_str, target_height), daemon=True).start()

    def download_process(self, download_path, format_str, target_height):
        # Construct filename with resolution
        # If target_height is "Best", we might not know the exact height until download starts,
        # but we can append "-Best" or let yt-dlp handle it.
        # User requested: "VideoName-720p"

        suffix = f"-{target_height}p" if target_height != "Best" else "-BestQuality"
        outtmpl = os.path.join(download_path, f'%(title)s{suffix}.%(ext)s')

        try:
            final_path = self.engine.download(
                self.download_url, format_str, outtmpl, self.progress_hook,
                stopped=lambda: self.is_stopped, paused=lambda: self.is_paused,
            )

            # Success
            # Actually getting the real final filename is tricky without return from ydl.
            # But we can use the one we constructed if we assume mp4/mkv.
            # For history, let's just use the folder path or try to find the file.

            self.root.after(0, lambda: self.add_to_history(
                self.video_info.get('title', 'Unknown'),
                self.download_url,
                final_path,
                f"{target_height}p"
            ))
            self.root.after(0, self.download_finished)

        except Exception as e:
            if self.is_stopped:
                self.root.after(0, lambda: self.status_var.set(self.get_text('stopped_msg')))
                # Cleanup
                for f in self.temp_files:
                    if os.path.exists(f):
                        try: os.remove(f)
                        except: pass
                    # Also try .part
                    if os.path.exists(f + ".part"):
                        try: os.remove(f + ".part")
                        except: pass
            else:
                self.root.after(0, lambda error=str(e): messagebox.showerror(self.get_text('error_title'), f"{self.get_text('download_failed')}: {error}"))
                self.root.after(0, lambda: self.status_var.set(self.get_text('download_failed')))
        finally:
            self.root.after(0, self.reset_download_ui)

    def reset_download_ui(self):
        self.download_running = False
        self.btn_analyze.config(state=tk.NORMAL)
        self.btn_download.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED, text=self.get_text('pause_btn'))
        self.btn_stop.config(state=tk.DISABLED)
        self.is_paused = False

    def progress_hook(self, d):
        if self.is_stopped:
            raise Exception("Stopped by user")

        if d['status'] == 'downloading':
            filename = d.get('filename')
            if filename:
                self.temp_files.add(filename)

            try:
                p = d.get('_percent_str', '0%').replace('%', '')
                # If _percent_str contains ANSI codes, it might fail float conversion.
                # Try to calculate from bytes if available
                if d.get('total_bytes') and d.get('downloaded_bytes'):
                    value = (d['downloaded_bytes'] / d['total_bytes']) * 100
                elif d.get('total_bytes_estimate') and d.get('downloaded_bytes'):
                    value = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                else:
                    # Fallback to parsing string, stripping ANSI codes if any
                    import re
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    p_clean = ansi_escape.sub('', p)
                    value = float(p_clean)

                self.root.after(0, lambda: self.progress.configure(value=value))
                self.root.after(0, lambda: self.status_var.set(f"{self.get_text('downloading')} {value:.1f}%"))
            except:
                pass
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.status_var.set(self.get_text('processing')))

    def download_finished(self):
        self.status_var.set(self.get_text('complete'))
        self.progress['value'] = 100
        messagebox.showinfo(self.get_text('success_title'), self.get_text('success_msg'))

if __name__ == "__main__":
    root = tk.Tk()
    # Set icon if available, otherwise skip
    # root.iconbitmap('icon.ico')
    app = YoutubeDownloaderGUI(root)
    root.mainloop()
