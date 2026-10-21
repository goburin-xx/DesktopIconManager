import ctypes
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
import winreg


# 🚀 タスクバーに自社アプリとして正しく認識させる（タスクバーアイコン対策）
if sys.platform == "win32":
  try:
    myappid = "dt.icon.manager.for.windows.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
  except Exception:
    pass


# 📁 exe化時の一時展開先から正しいアイコンパスを取得する関数
def get_resource_path(relative_path):
  if hasattr(sys, "_MEIPASS"):
    return os.path.join(sys._MEIPASS, relative_path)
  return os.path.join(os.path.abspath("."), relative_path)


def is_admin():
  """現在の実行環境が管理者権限を持っているかチェックする。"""
  try:
    return ctypes.windll.shell32.IsUserAnAdmin()
  except Exception:
    return False


def run_as_admin():
  """管理者権限がない場合、管理者権限で自分自身を再起動する（UAC昇格）。"""
  if not is_admin():
    try:
      script = os.path.abspath(sys.argv[0])
      params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
      result = ctypes.windll.shell32.ShellExecuteW(
          None, "runas", sys.executable, f'"{script}" {params}', None, 1
      )
      if result <= 32:
        print(f"UAC昇格がキャンセルされたか失敗しました (code: {result})")
    except Exception as e:
      messagebox.showerror(
          "起動エラー", f"管理者権限への昇格に失敗しました。\n{e}"
      )
    sys.exit()


run_as_admin()

APP_TITLE = "🖥️ DTアイコン 1発管理 for Windows"
APP_SUBTITLE = "〜 配信・画面共有で「見せたいアイコン」だけ残す選択非表示ツール 〜"

SYSTEM_ICONS = [
    ("PC", "{20D04FE0-3AEA-1069-A2D8-08002B30309D}"),
    ("ごみ箱", "{645FF040-5081-101B-9F08-00AA002F954E}"),
    ("コントロール パネル", "{5399E694-6CE5-4D6C-8FCE-1D8870FDCBA0}"),
    ("ネットワーク", "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}"),
    ("ユーザーのファイル", "{59031A47-3F72-44A7-89C5-5595FE6B30EE}"),
]
HIDE_ICONS_KEYS = [
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons\NewStartPanel",
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons\Explorer",
]
DESKTOP_ICON_VISIBILITY_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
)
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4


def get_actual_desktop():
  """WindowsのUser Shell Foldersに登録された実際のデスクトップを取得。"""
  try:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
    ) as key:
      value, _ = winreg.QueryValueEx(key, "Desktop")
      path = Path(os.path.expandvars(value))
      if path.is_dir():
        return path
  except OSError:
    pass

  candidates = [
      Path.home() / "Desktop",
      Path.home() / "OneDrive" / "デスクトップ",
      Path.home() / "OneDrive" / "Desktop",
      Path.home() / "デスクトップ",
  ]
  for path in candidates:
    if path.is_dir():
      return path
  return Path.home() / "Desktop"


def get_desktop_locations():
  personal = get_actual_desktop()
  public = Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"
  result = [("個人用", personal)]
  if public.is_dir() and str(public).casefold() != str(personal).casefold():
    result.append(("共通", public))
  return result


def get_system_visibility(clsid):
  """レジストリからシステムアイコンの表示状態を取得する（0=表示, 1=非表示）。"""
  for path in HIDE_ICONS_KEYS:
    try:
      with winreg.OpenKey(
          winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ
      ) as key:
        value, _ = winreg.QueryValueEx(key, clsid)
        if value == 1:
          return "非表示"
        elif value == 0:
          return "表示"
    except (FileNotFoundError, OSError):
      continue
  return "表示（既定）"


def set_system_visibility(clsid, hide):
  """レジストリを直接書き換えてシステムアイコンの表示・非表示を切り替える。"""
  val = 1 if hide else 0
  for path in HIDE_ICONS_KEYS:
    try:
      with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, clsid, 0, winreg.REG_DWORD, val)
    except OSError as e:
      raise OSError(f"レジストリの書き込みに失敗しました ({path}): {e}")

  try:
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
  except Exception:
    pass


def get_general_items():
  items = []
  seen = set()
  for scope, folder in get_desktop_locations():
    try:
      children = list(folder.iterdir())
    except OSError:
      continue

    for path in children:
      if path.name.casefold() == "desktop.ini":
        continue
      try:
        resolved = str(path.resolve()).casefold()
      except OSError:
        resolved = str(path).casefold()
      if resolved in seen:
        continue
      seen.add(resolved)

      try:
        attrs = path.stat().st_file_attributes
        hidden = bool(attrs & FILE_ATTRIBUTE_HIDDEN)
        system = bool(attrs & FILE_ATTRIBUTE_SYSTEM)
      except (OSError, AttributeError):
        hidden = False
        system = False

      if path.is_dir():
        kind = "フォルダー"
      elif path.suffix.casefold() == ".lnk":
        kind = "ショートカット"
      else:
        kind = "ファイル"

      flags = []
      if hidden:
        flags.append("非表示（隠し属性）")
      if system:
        flags.append("システム属性あり")
      state = "、".join(flags) if flags else "通常表示"
      items.append({
          "name": path.name,
          "kind": kind,
          "state": state,
          "scope": scope,
          "path": str(path),
          "hidden": hidden,
          "system": system,
          "tag": "hidden" if hidden or system else "normal",
      })
  return sorted(items, key=lambda x: (x["scope"], x["name"].casefold()))


def set_hidden_attribute(path_text, hide):
  """Windowsの隠し属性だけを変更。他の属性は保持する。"""
  path = Path(path_text)
  if not path.exists():
    raise FileNotFoundError(f"対象が見つかりません: {path}")
  attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
  invalid = 0xFFFFFFFF
  if attrs == invalid:
    raise OSError(f"ファイル属性を取得できません: {path}")
  if hide:
    new_attrs = attrs | FILE_ATTRIBUTE_HIDDEN
  else:
    new_attrs = attrs & ~FILE_ATTRIBUTE_HIDDEN
  if not ctypes.windll.kernel32.SetFileAttributesW(str(path), new_attrs):
    raise OSError(f"ファイル属性を変更できません: {path}")


def get_all_desktop_icons_hidden():
  """デスクトップ全アイコン表示の設定値。0=表示、1=非表示。"""
  try:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, DESKTOP_ICON_VISIBILITY_KEY
    ) as key:
      value, _ = winreg.QueryValueEx(key, "HideIcons")
    return bool(value)
  except OSError:
    return None


def set_all_desktop_icons_hidden(hide):
  """ExplorerのHideIcons設定を更新し、SysListView32のShowWindowで確実かつ即座に反映させる。"""
  with winreg.CreateKey(
      winreg.HKEY_CURRENT_USER, DESKTOP_ICON_VISIBILITY_KEY
  ) as key:
    winreg.SetValueEx(key, "HideIcons", 0, winreg.REG_DWORD, 1 if hide else 0)

  hwnd = ctypes.windll.user32.FindWindowW("Progman", None)
  hwnd = ctypes.windll.user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
  if not hwnd:
    hwnd = 0
    while True:
      hwnd = ctypes.windll.user32.FindWindowExW(0, hwnd, "WorkerW", None)
      if not hwnd:
        break
      s_hwnd = ctypes.windll.user32.FindWindowExW(
          hwnd, 0, "SHELLDLL_DefView", None
      )
      if s_hwnd:
        hwnd = s_hwnd
        break

  if hwnd:
    l_hwnd = ctypes.windll.user32.FindWindowExW(hwnd, 0, "SysListView32", None)
    if l_hwnd:
      cmd = 0 if hide else 5
      ctypes.windll.user32.ShowWindow(l_hwnd, cmd)

  try:
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced",
        SMTO_ABORTIFHUNG,
        2000,
        None,
    )
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
  except Exception:
    pass


root = tk.Tk()
root.title(APP_TITLE)
root.geometry("1220x720")
root.minsize(850, 480)

# 🖼️ タイトルバーおよびタスクバーのアイコン設定
try:
  icon_path = get_resource_path("dt_icon_manager.ico")
  if os.path.exists(icon_path):
    try:
      # iconphotoを使用することでタスクバーとタイトルバーの両方に反映されます
      icon_img = tk.PhotoImage(file=icon_path)
      root.iconphoto(True, icon_img)
    except Exception:
      root.iconbitmap(default=icon_path)
except Exception as e:
  print(f"アイコンの設定に失敗しました: {e}")

main = ttk.Frame(root, padding=12)
main.pack(fill="both", expand=True)

# アプリタイトル・サブタイトル表記
ttk.Label(main, text=APP_TITLE, font=("", 16, "bold")).pack(anchor="w")
ttk.Label(main, text=APP_SUBTITLE, font=("", 10)).pack(anchor="w", pady=(2, 6))

# 操作説明＆ヒント表示
ttk.Label(
    main,
    text=(
        "※ DT = Desktop の略です。\n"
        "・行をクリックするだけでチェックボックスをON/OFFできます（複数選択可能）。\n"
        "💡 非表示にしたアイコンが半透明で残る場合は、エクスプローラーの設定で「隠しファイルを表示しない」に設定してください。"
    ),
    wraplength=1160,
    foreground="#444444"
).pack(anchor="w", pady=(0, 10))

# 全アイコン表示
global_frame = ttk.LabelFrame(main, text="デスクトップ全体", padding=8)
global_frame.pack(fill="x", pady=(0, 8))
global_state = tk.StringVar()
ttk.Label(global_frame, textvariable=global_state).pack(
    side="left", padx=(0, 12)
)
global_button = ttk.Button(global_frame, text="全アイコンを非表示")
global_button.pack(side="left")
ttk.Label(
    global_frame,
    text="⚠️ 全非表示時に迷子にならないよう、本アプリはタスクバー等へのピン留めを推奨します。",
    foreground="#d9534f"
).pack(side="left", padx=12)

notebook = ttk.Notebook(main)
notebook.pack(fill="both", expand=True)

# 一般アイコンタブ
general_tab = ttk.Frame(notebook, padding=8)
notebook.add(general_tab, text="一般のデスクトップアイコン")
general_columns = ("check", "name", "kind", "state", "scope", "path")
general_tree = ttk.Treeview(
    general_tab, columns=general_columns, show="headings", selectmode="browse"
)
for col, heading, width in [
    ("check", "選択", 60),
    ("name", "名前", 210),
    ("kind", "種類", 110),
    ("state", "状態", 150),
    ("scope", "場所", 70),
    ("path", "実際のパス", 420),
]:
  general_tree.heading(col, text=heading)
  general_tree.column(
      col, width=width, anchor="w" if col != "check" else "center"
  )

general_scroll = ttk.Scrollbar(
    general_tab, orient="vertical", command=general_tree.yview
)
general_tree.configure(yscrollcommand=general_scroll.set)
general_tree.pack(side="top", fill="both", expand=True)
general_scroll.pack(side="right", fill="y")
general_tree.tag_configure("hidden", foreground="#999999")
general_tree.tag_configure("system", foreground="#245b91")

# 一般アイコン用の一括アクションボタン
general_actions = ttk.Frame(general_tab)
general_actions.pack(side="bottom", fill="x", pady=(8, 0))
ttk.Button(
    general_actions,
    text="チェックした項目を非表示にする",
    command=lambda: batch_change_hidden(True),
).pack(side="left")
ttk.Button(
    general_actions,
    text="チェックした項目を再表示する",
    command=lambda: batch_change_hidden(False),
).pack(side="left", padx=8)

ttk.Button(
    general_actions,
    text="すべてチェック",
    command=lambda: toggle_all_checks(True),
).pack(side="left", padx=20)
ttk.Button(
    general_actions,
    text="チェックをすべて外す",
    command=lambda: toggle_all_checks(False),
).pack(side="left")

ttk.Button(
    general_actions, text="一覧を更新", command=lambda: refresh_general()
).pack(side="right")


# システムアイコンタブ
system_tab = ttk.Frame(notebook, padding=8)
notebook.add(system_tab, text="システムアイコン")
system_columns = ("check", "name", "state", "scope", "path")
system_tree = ttk.Treeview(
    system_tab, columns=system_columns, show="headings", selectmode="browse"
)
for col, heading, width in [
    ("check", "選択", 60),
    ("name", "システムアイコン", 200),
    ("state", "現在の状態", 200),
    ("scope", "管理場所", 120),
    ("path", "識別情報（CLSID）", 420),
]:
  system_tree.heading(col, text=heading)
  system_tree.column(
      col, width=width, anchor="w" if col != "check" else "center"
  )

system_scroll = ttk.Scrollbar(
    system_tab, orient="vertical", command=system_tree.yview
)
system_tree.configure(yscrollcommand=system_scroll.set)
system_tree.pack(side="top", fill="both", expand=True)
system_scroll.pack(side="right", fill="y")
system_tree.tag_configure("system", foreground="#245b91")
system_tree.tag_configure("hidden", foreground="#999999")

system_actions = ttk.Frame(system_tab)
system_actions.pack(side="bottom", fill="x", pady=(8, 0))
ttk.Button(
    system_actions,
    text="チェックしたシステムを非表示にする",
    command=lambda: batch_change_system_hidden(True),
).pack(side="left")
ttk.Button(
    system_actions,
    text="チェックしたシステムを表示する",
    command=lambda: batch_change_system_hidden(False),
).pack(side="left", padx=8)

ttk.Button(
    system_actions,
    text="すべてチェック",
    command=lambda: toggle_all_system_checks(True),
).pack(side="left", padx=20)
ttk.Button(
    system_actions,
    text="チェックをすべて外す",
    command=lambda: toggle_all_system_checks(False),
).pack(side="left")

ttk.Button(
    system_actions, text="一覧を更新", command=lambda: refresh_system()
).pack(side="right")

# ステータス
status = tk.StringVar()
ttk.Label(main, textvariable=status, anchor="w").pack(fill="x", pady=(8, 0))


def refresh_global():
  hidden = get_all_desktop_icons_hidden()
  if hidden is None:
    global_state.set("全アイコン表示設定：未取得")
    global_button.configure(text="全アイコンを非表示")
  elif hidden:
    global_state.set("全アイコン表示設定：非表示")
    global_button.configure(text="全アイコンを再表示")
  else:
    global_state.set("全アイコン表示設定：表示")
    global_button.configure(text="全アイコンを非表示")


def toggle_global():
  hidden = get_all_desktop_icons_hidden()
  target = not hidden if hidden is not None else True
  try:
    set_all_desktop_icons_hidden(target)
    refresh_global()
    status.set("Windowsのデスクトップ全体の設定を更新しました。")
  except OSError as exc:
    messagebox.showerror("設定変更エラー", str(exc))


def refresh_general():
  general_tree.delete(*general_tree.get_children())
  items = get_general_items()
  for item in items:
    general_tree.insert(
        "",
        "end",
        values=(
            "□",
            item["name"],
            item["kind"],
            item["state"],
            item["scope"],
            item["path"],
        ),
        tags=(item["tag"],),
    )
  status.set(
      f"一般アイコン：{len(items)} 件。行をクリックするとチェックをON/OFFできます。"
  )


def refresh_system():
  system_tree.delete(*system_tree.get_children())
  for name, clsid in SYSTEM_ICONS:
    state = get_system_visibility(clsid)
    system_tree.insert(
        "",
        "end",
        values=("□", name, state, "レジストリ直接制御", f"::{clsid}"),
        tags=("hidden" if state == "非表示" else "system",),
    )
  status.set(
      "システムアイコン：行をクリックするとチェックをON/OFFできます。"
  )


# 行のどこをクリックしてもチェックボックスを反転させる関数
def on_tree_click(event, tree):
  region = tree.identify("region", event.x, event.y)
  if region == "cell":
    item_id = tree.identify_row(event.y)
    if item_id:
      current_values = list(tree.item(item_id, "values"))
      if current_values[0] == "□":
        current_values[0] = "☑"
      else:
        current_values[0] = "□"
      tree.item(item_id, values=current_values)


general_tree.bind("<Button-1>", lambda e: on_tree_click(e, general_tree))
system_tree.bind("<Button-1>", lambda e: on_tree_click(e, system_tree))


def toggle_all_checks(check):
  for item_id in general_tree.get_children():
    vals = list(general_tree.item(item_id, "values"))
    vals[0] = "☑" if check else "□"
    general_tree.item(item_id, values=vals)


def toggle_all_system_checks(check):
  for item_id in system_tree.get_children():
    vals = list(system_tree.item(item_id, "values"))
    vals[0] = "☑" if check else "□"
    system_tree.item(item_id, values=vals)


def batch_change_hidden(hide):
  selected_items = []
  for item_id in general_tree.get_children():
    vals = general_tree.item(item_id, "values")
    if vals[0] == "☑":
      selected_items.append((item_id, vals[1], vals[5]))

  if not selected_items:
    messagebox.showinfo("未選択", "チェックが入っている項目がありません。")
    return

  action = "非表示" if hide else "再表示"
  if not messagebox.askyesno(
      f"一括{action}の確認",
      f"選択された {len(selected_items)} 件の項目を{action}にします。続行しますか？",
  ):
    return

  success_count = 0
  err_messages = []
  for item_id, name, path_text in selected_items:
    try:
      set_hidden_attribute(path_text, hide)
      success_count += 1
    except Exception as e:
      err_messages.append(f"{name}: {e}")

  refresh_general()
  if err_messages:
    messagebox.showwarning(
        "一部エラー",
        f"{success_count} 件成功しましたが、以下の項目でエラーが発生しました:\n"
        + "\n".join(err_messages),
    )
  else:
    status.set(f"{success_count} 件の項目を{action}にしました。")


def batch_change_system_hidden(hide):
  selected_items = []
  for item_id in system_tree.get_children():
    vals = system_tree.item(item_id, "values")
    if vals[0] == "☑":
      selected_items.append((vals[1], vals[4].replace("::", "")))

  if not selected_items:
    messagebox.showinfo(
        "未選択", "チェックが入っているシステムアイコンがありません。"
    )
    return

  action = "非表示" if hide else "表示"
  success_count = 0
  err_messages = []
  for name, clsid in selected_items:
    try:
      set_system_visibility(clsid, hide)
      success_count += 1
    except Exception as e:
      err_messages.append(f"{name}: {e}")

  refresh_system()
  if err_messages:
    messagebox.showwarning(
        "一部エラー",
        f"{success_count} 件成功しましたが、以下の項目でエラーが発生しました:\n"
        + "\n".join(err_messages),
    )
  else:
    status.set(
        f"システムアイコン {success_count} 件を{action}に設定しました。"
    )


global_button.configure(command=toggle_global)
notebook.bind(
    "<<NotebookTabChanged>>",
    lambda _e: (
        refresh_system()
        if notebook.index(notebook.select()) == 1
        else refresh_general()
    ),
)

refresh_global()
refresh_general()
refresh_system()
root.mainloop()