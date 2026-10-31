import customtkinter as ctk
from customtkinter import filedialog
import yt_dlp
import threading
import os
import sys
import json
import webbrowser
import requests
from io import BytesIO
from pathlib import Path
from PIL import Image

APP_VERSION = "v1.0"
GITHUB_REPO = "Kexborn/YouTube-Downloader"

SETTINGS_FILE = "settings.json"
DEFAULT_DOWNLOADS = str(Path.home() / "Downloads")

stop_flag = False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_path():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("download_path", DEFAULT_DOWNLOADS)
        except: pass
    return DEFAULT_DOWNLOADS

def save_path(path):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"download_path": path}, f)

def check_updates():
    status_label.configure(text="Поиск обновлений...", text_color="yellow")
    def run_check():
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                latest_version = response.json().get("tag_name", "")
                if latest_version and latest_version != APP_VERSION:
                    app.after(0, lambda: status_label.configure(text=f"Доступна новая версия: {latest_version}! Открываю браузер...", text_color="green"))
                    app.after(1500, lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest"))
                else:
                    app.after(0, lambda: status_label.configure(text="У вас установлена последняя версия.", text_color="green"))
            else:
                app.after(0, lambda: status_label.configure(text="Нет данных об обновлениях (проверьте имя репозитория).", text_color="red"))
        except Exception:
            app.after(0, lambda: status_label.configure(text="Ошибка соединения с сервером.", text_color="red"))
    threading.Thread(target=run_check, daemon=True).start()

def add_recent_download(url, title, img_data):
    row = ctk.CTkFrame(recent_frame, fg_color="#333333", corner_radius=5, height=55)
    row.pack(fill="x", pady=2, padx=5)
    row.pack_propagate(False) 
    
    if img_data:
        try:
            ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(80, 45))
            img_lbl = ctk.CTkLabel(row, image=ctk_img, text="")
            img_lbl.pack(side="left", padx=5, pady=5)
        except: pass
        
    text_frame = ctk.CTkFrame(row, fg_color="transparent")
    text_frame.pack(side="left", fill="both", expand=True, padx=5, pady=2)
    
    short_title = title[:45] + "..." if len(title) > 45 else title
    title_lbl = ctk.CTkLabel(text_frame, text=short_title, font=("Arial", 12, "bold"), text_color="white", anchor="w")
    title_lbl.pack(anchor="w", fill="x")
    
    short_url = url[:55] + "..." if len(url) > 55 else url
    url_lbl = ctk.CTkLabel(text_frame, text=short_url, font=("Arial", 10), text_color="#1976D2", anchor="w", cursor="hand2")
    url_lbl.pack(anchor="w", fill="x")
    url_lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

def stop_action():
    global stop_flag
    stop_flag = True
    status_label.configure(text="Остановка процессов...", text_color="red")
    download_btn.configure(state="normal")
    progress_bar.set(0)

def download_media():
    global stop_flag
    stop_flag = False
    
    url = url_entry.get()
    if not url:
        status_label.configure(text="Введите ссылку!", text_color="red")
        return
    
    choice = format_var.get()
    save_dir = current_path.get()
    
    status_label.configure(text="Начинаю скачивание...", text_color="yellow")
    download_btn.configure(state="disabled")
    progress_bar.set(0)
    
    def run_download():
        global stop_flag
        
        if "list=" in url or "/playlist" in url:
            out_tmpl = os.path.join(save_dir, '%(playlist_title)s', '%(title)s.%(ext)s')
        else:
            out_tmpl = os.path.join(save_dir, '%(title)s.%(ext)s')
            
        def my_match_filter(info, *args, **kwargs):
            if stop_flag:
                return "Остановлено пользователем"
            return None
        
        def progress_hook(d):
            if stop_flag:
                raise ValueError("Остановлено")
                
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = downloaded / total
                    app.after(0, lambda p=percent: progress_bar.set(p))
                    app.after(0, lambda p=percent: status_label.configure(text=f"Загрузка: {p*100:.1f}%", text_color="yellow"))
            elif d['status'] == 'finished':
                app.after(0, lambda: progress_bar.set(1.0))
                app.after(0, lambda: status_label.configure(text="Конвертация файла...", text_color="yellow"))

        ydl_opts = {
            'outtmpl': out_tmpl,
            'noplaylist': False,
            'match_filter': my_match_filter,
            'progress_hooks': [progress_hook],
            'ignoreerrors': True
        }

        if choice == "MP3 (Аудио)":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            })
        else:
            if choice == "Видео (Лучшее)": format_str = 'bestvideo+bestaudio/best'
            elif choice == "Видео (1080p)": format_str = 'bestvideo[height<=1080]+bestaudio/best'
            elif choice == "Видео (720p)": format_str = 'bestvideo[height<=720]+bestaudio/best'
            else: format_str = 'bestvideo[height<=480]+bestaudio/best'
            
            ydl_opts.update({'format': format_str, 'merge_output_format': 'mp4'})
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if info and not stop_flag:
                    if 'entries' in info:
                        title = info.get('title', 'Плейлист')
                        web_url = info.get('original_url', url)
                        thumb_url = info['entries'][0].get('thumbnail', '') if info.get('entries') else ''
                    else:
                        title = info.get('title', 'Без названия')
                        web_url = info.get('original_url', url)
                        thumb_url = info.get('thumbnail', '')
                    
                    img_data = None
                    if thumb_url:
                        try:
                            resp = requests.get(thumb_url, timeout=5)
                            if resp.status_code == 200:
                                img_data = Image.open(BytesIO(resp.content))
                        except: pass
                        
                    app.after(0, lambda u=web_url, t=title, img=img_data: add_recent_download(u, t, img))
                    
            if not stop_flag:
                app.after(0, lambda: progress_bar.set(1.0))
                app.after(0, lambda: status_label.configure(text="Успешно скачано!", text_color="green"))
        except Exception:
            if not stop_flag:
                app.after(0, lambda: status_label.configure(text="Ошибка загрузки. Проверьте ссылку.", text_color="red"))
        finally:
            if not stop_flag:
                app.after(0, lambda: download_btn.configure(state="normal"))
                app.after(0, lambda: url_entry.delete(0, 'end'))

    threading.Thread(target=run_download, daemon=True).start()

def paste_text(event=None):
    try:
        url_entry.delete(0, 'end')
        url_entry.insert(0, app.clipboard_get())
    except ctk.tkinter.TclError: pass

def on_key(event):
    if (event.state & 4) and getattr(event, 'keycode', 0) == 86:
        paste_text()

def choose_directory():
    new_path = filedialog.askdirectory(initialdir=current_path.get())
    if new_path:
        new_path = os.path.normpath(new_path)
        current_path.set(new_path)
        save_path(new_path)
        path_label.configure(text=new_path)

def set_default_directory():
    current_path.set(DEFAULT_DOWNLOADS)
    save_path(DEFAULT_DOWNLOADS)
    path_label.configure(text=DEFAULT_DOWNLOADS)

def open_current_folder():
    try: os.startfile(current_path.get())
    except: pass

def open_boosty(event=None):
    webbrowser.open("https://boosty.to/kexborn")

app = ctk.CTk()
app.geometry("540x850")
app.title("Kexborn - YouTube Downloader")
ctk.set_appearance_mode("dark")

try:
    app.iconbitmap(resource_path("RedGift.ico"))
except: pass

current_path = ctk.StringVar(value=load_path())

input_frame = ctk.CTkFrame(app, fg_color="transparent")
input_frame.pack(pady=(15, 5))
url_entry = ctk.CTkEntry(input_frame, placeholder_text="URL видео...", width=340, height=35)
url_entry.pack(side="left", padx=(0, 10))
paste_btn = ctk.CTkButton(input_frame, text="Вставить", width=70, height=35, fg_color="#616161", hover_color="#757575", command=paste_text)
paste_btn.pack(side="right")
app.bind('<Key>', on_key)

action_frame = ctk.CTkFrame(app, fg_color="transparent")
action_frame.pack(pady=5)
format_var = ctk.StringVar(value="MP3 (Аудио)")
format_menu = ctk.CTkOptionMenu(action_frame, variable=format_var, values=["MP3 (Аудио)", "Видео (Лучшее)", "Видео (1080p)", "Видео (720p)", "Видео (480p)"], fg_color="#424242", button_color="#616161")
format_menu.pack(side="left", padx=(0, 15))

download_btn = ctk.CTkButton(action_frame, text="Скачать", fg_color="#e53935", hover_color="#b71c1c", command=download_media, width=130, height=35)
download_btn.pack(side="left", padx=(0, 10))

stop_btn = ctk.CTkButton(action_frame, text="Стоп", fg_color="#616161", hover_color="#757575", command=stop_action, width=60, height=35)
stop_btn.pack(side="left")

progress_bar = ctk.CTkProgressBar(app, width=400)
progress_bar.set(0)
progress_bar.pack(pady=(10, 0))
status_label = ctk.CTkLabel(app, text="")
status_label.pack(pady=2)

dir_frame = ctk.CTkFrame(app, fg_color="#2b2b2b", corner_radius=8)
dir_frame.pack(pady=5, padx=20, fill="x")
title_label = ctk.CTkLabel(dir_frame, text="Папка назначения", font=("Arial", 14, "bold"))
title_label.pack(anchor="w", padx=15, pady=(10, 5))
path_label = ctk.CTkLabel(dir_frame, text=current_path.get(), font=("Arial", 13, "bold"), text_color="white")
path_label.pack(anchor="w", padx=15, pady=(0, 10))

btn_frame = ctk.CTkFrame(dir_frame, fg_color="transparent")
btn_frame.pack(anchor="w", padx=15, pady=(0, 15))
open_folder_btn = ctk.CTkButton(btn_frame, text="Открыть папку", fg_color="#1976D2", hover_color="#1565C0", command=open_current_folder, width=120)
open_folder_btn.pack(side="left", padx=(0, 10))
browse_btn = ctk.CTkButton(btn_frame, text="Обзор", fg_color="#424242", hover_color="#616161", command=choose_directory, width=100)
browse_btn.pack(side="left", padx=(0, 10))
default_btn = ctk.CTkButton(btn_frame, text="По умолчанию", fg_color="#424242", hover_color="#616161", command=set_default_directory, width=130)
default_btn.pack(side="left")

recent_lbl = ctk.CTkLabel(app, text="Недавно скачанные файлы", font=("Arial", 13, "bold"))
recent_lbl.pack(pady=(10, 0))
recent_frame = ctk.CTkScrollableFrame(app, height=140)
recent_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

bottom_frame = ctk.CTkFrame(app, fg_color="transparent")
bottom_frame.pack(side="bottom", fill="x", pady=10)

try:
    img_data = Image.open(resource_path("The situation in the world.jpg"))
    ratio = 500 / img_data.width
    new_height = int(img_data.height * ratio)
    ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(500, new_height))
    img_label = ctk.CTkLabel(bottom_frame, image=ctk_img, text="", cursor="hand2")
    img_label.pack()
    img_label.bind("<Button-1>", open_boosty)
except Exception: pass

update_btn = ctk.CTkButton(bottom_frame, text=f"Версия {APP_VERSION} | Проверить обновления", fg_color="transparent", text_color="gray", hover_color="#333333", command=check_updates)
update_btn.pack(pady=(5, 0))

if __name__ == "__main__":
    app.mainloop()