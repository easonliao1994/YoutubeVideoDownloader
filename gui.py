import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yt_dlp
import threading
import os
import sys

class YoutubeDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("600x500")
        
        # Variables
        self.url_var = tk.StringVar()
        # Default to user's Downloads folder
        default_download_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        self.path_var = tk.StringVar(value=default_download_path)
        self.status_var = tk.StringVar(value="Ready")
        self.video_info = None
        self.resolutions = []
        
        # Create UI
        self.create_widgets()
        
        # Ensure download directory exists
        if not os.path.exists(self.path_var.get()):
            try:
                os.makedirs(self.path_var.get())
            except OSError:
                pass

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL Section
        url_frame = ttk.LabelFrame(main_frame, text="Video URL", padding="10")
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        entry_url = ttk.Entry(url_frame, textvariable=self.url_var)
        entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        btn_analyze = ttk.Button(url_frame, text="Analyze", command=self.start_analysis)
        btn_analyze.pack(side=tk.RIGHT)
        
        # Video Info Section
        self.info_frame = ttk.LabelFrame(main_frame, text="Video Info", padding="10")
        self.info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.lbl_title = ttk.Label(self.info_frame, text="Please enter URL and click Analyze...", wraplength=500)
        self.lbl_title.pack(anchor=tk.W, pady=(0, 10))
        
        # Resolution Selection
        res_frame = ttk.Frame(self.info_frame)
        res_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(res_frame, text="Select Resolution:").pack(side=tk.LEFT, padx=(0, 10))
        self.combo_res = ttk.Combobox(res_frame, state="readonly")
        self.combo_res.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Download Path Section
        path_frame = ttk.LabelFrame(main_frame, text="Download Location", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        entry_path = ttk.Entry(path_frame, textvariable=self.path_var)
        entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        btn_browse = ttk.Button(path_frame, text="Browse...", command=self.browse_directory)
        btn_browse.pack(side=tk.RIGHT)
        
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
        
        self.btn_download = ttk.Button(btn_frame, text="Start Download", command=self.start_download, state=tk.DISABLED)
        self.btn_download.pack(fill=tk.X, ipady=5)

    def browse_directory(self):
        directory = filedialog.askdirectory(initialdir=self.path_var.get())
        if directory:
            self.path_var.set(directory)

    def start_analysis(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter video URL")
            return
            
        self.status_var.set("Analyzing video info...")
        self.root.update_idletasks()
        
        # Run in thread
        threading.Thread(target=self.analyze_video, args=(url,), daemon=True).start()

    def analyze_video(self, url):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Process formats
                formats = info.get('formats', [])
                seen_heights = set()
                self.resolutions = []
                
                # Sort formats by height descending
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
                
                # Update UI in main thread
                self.root.after(0, self.update_ui_after_analysis, info)
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Analysis failed"))

    def update_ui_after_analysis(self, info):
        self.video_info = info
        self.lbl_title.config(text=info.get('title', 'Unknown Title'))
        
        # Populate combobox
        values = []
        for res in self.resolutions:
            size_str = ""
            if res['filesize']:
                size_mb = res['filesize'] / 1024 / 1024
                size_str = f" - approx. {size_mb:.1f}MB"
            values.append(f"{res['height']}p ({res['ext']}){size_str}")
        
        values.append("Best Quality (Auto)")
        self.combo_res['values'] = values
        if values:
            self.combo_res.current(0)
            self.btn_download['state'] = tk.NORMAL
            
        self.status_var.set("Analysis complete. Select resolution and download.")

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
                messagebox.showerror("Error", f"Cannot create directory: {str(e)}")
                return

        self.btn_download['state'] = tk.DISABLED
        self.status_var.set("Preparing download...")
        self.progress['value'] = 0
        
        # Determine format
        if selection_idx < len(self.resolutions):
            target_height = self.resolutions[selection_idx]['height']
            format_str = f'bestvideo[height={target_height}]+bestaudio/best[height={target_height}]'
        else:
            format_str = 'bestvideo+bestaudio/best'
            
        threading.Thread(target=self.download_process, args=(download_path, format_str), daemon=True).start()

    def download_process(self, download_path, format_str):
        ydl_opts = {
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'format': format_str,
            'progress_hooks': [self.progress_hook],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url_var.get()])
            
            self.root.after(0, self.download_finished)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Download failed"))
            self.root.after(0, lambda: self.btn_download.config(state=tk.NORMAL))

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                p = d.get('_percent_str', '0%').replace('%', '')
                value = float(p)
                self.root.after(0, lambda: self.progress.configure(value=value))
                self.root.after(0, lambda: self.status_var.set(f"Downloading... {d.get('_percent_str')}"))
            except:
                pass
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.status_var.set("Download complete, processing merge..."))

    def download_finished(self):
        self.status_var.set("Download Complete!")
        self.progress['value'] = 100
        self.btn_download['state'] = tk.NORMAL
        messagebox.showinfo("Success", "Video download completed!")

if __name__ == "__main__":
    root = tk.Tk()
    # Set icon if available, otherwise skip
    # root.iconbitmap('icon.ico') 
    app = YoutubeDownloaderGUI(root)
    root.mainloop()
