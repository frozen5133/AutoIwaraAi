import os
import urllib.parse
from datetime import datetime


def init_playlist_files(output_dir: str) -> tuple[str, str]:
    """プレイリストファイルを最初に1回だけ生成する（ファイル名を返す）"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    base_name = timestamp

    # MPCPL形式（Media Player Classic用）
    mpcpl_path = os.path.join(output_dir, f"{base_name}.mpcpl")
    try:
        with open(mpcpl_path, 'w', encoding='utf-8') as f:
            f.write("MPCPLAYLIST\n")
        print(f"MPCPLプレイリストを初期化しました: {mpcpl_path}")
    except Exception as e:
        print(f"MPCPLプレイリストの初期化に失敗しました: {e}")
        mpcpl_path = ""

    # XSPF形式（VLC等用）
    xspf_path = os.path.join(output_dir, f"{base_name}.xspf")
    try:
        with open(xspf_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<playlist version="1" xmlns="http://xspf.org/ns/0/">\n')
            f.write('  <title>Downloaded Videos</title>\n')
            f.write('  <trackList>\n')
        print(f"XSPFプレイリストを初期化しました: {xspf_path}")
    except Exception as e:
        print(f"XSPFプレイリストの初期化に失敗しました: {e}")
        xspf_path = ""

    return mpcpl_path, xspf_path


def append_playlist_entry(mpcpl_path: str, xspf_path: str, video_file: str) -> None:
    """プレイリストファイルに1件ずつ追記する"""
    # 絶対パスに変換
    abs_path = os.path.abspath(video_file)

    # MPCPL形式
    if mpcpl_path:
        try:
            # 現在のエントリ数をカウント
            entry_count = 0
            with open(mpcpl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(str(entry_count + 1)) and 'filename,' in line:
                        entry_count += 1
            entry_count += 1
            with open(mpcpl_path, 'a', encoding='utf-8') as f:
                f.write(f"{entry_count},type,0\n{entry_count},filename,{abs_path}\n")
        except Exception as e:
            print(f"MPCPLプレイリストへの追記に失敗しました: {e}")

    # XSPF形式
    if xspf_path:
        try:
            uri_path = abs_path.replace('\\', '/')
            encoded_path = urllib.parse.quote(uri_path, safe='/')
            with open(xspf_path, 'a', encoding='utf-8') as f:
                f.write('    <track>\n')
                f.write(f'      <location>file:///{encoded_path}</location>\n')
                f.write('    </track>\n')
        except Exception as e:
            print(f"XSPFプレイリストへの追記に失敗しました: {e}")


def finalize_playlist(xspf_path: str) -> None:
    """XSPFプレイリストファイルを完成させる（XMLを閉じる）"""
    if xspf_path and os.path.exists(xspf_path):
        try:
            with open(xspf_path, 'a', encoding='utf-8') as f:
                f.write('  </trackList>\n')
                f.write('</playlist>\n')
            print(f"XSPFプレイリストを完成しました: {xspf_path}")
        except Exception as e:
            print(f"XSPFプレイリストの完成に失敗しました: {e}")


def generate_playlist_from_history(history_path: str, output_dir: str) -> None:
    """ダウンロード履歴ファイルからプレイリストを生成する"""
    if not os.path.exists(history_path):
        print(f"履歴ファイルが存在しません: {history_path}")
        return

    video_files = []
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 形式: "timestamp | page: url | source: url | output: path"
                if 'output:' in line:
                    parts = line.split('output:')
                    if len(parts) > 1:
                        output_path = parts[1].strip()
                        if os.path.exists(output_path):
                            video_files.append(output_path)
    except Exception as e:
        print(f"履歴ファイルの読み込みに失敗しました: {e}")
        return

    if not video_files:
        print("履歴ファイルから動画ファイルを取得できませんでした。")
        return

    print(f"履歴から {len(video_files)} 件の動画ファイルを検出しました。")

    # 年月日時分秒でファイル名生成
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    base_name = f"history_{timestamp}"

    # MPCPL形式
    mpcpl_path = os.path.join(output_dir, f"{base_name}.mpcpl")
    try:
        with open(mpcpl_path, 'w', encoding='utf-8') as f:
            f.write("MPCPLAYLIST\n")
            for i, video_file in enumerate(video_files, 1):
                abs_path = os.path.abspath(video_file)
                f.write(f"{i},type,0\n{i},filename,{abs_path}\n")
        print(f"MPCPLプレイリストを生成しました: {mpcpl_path}")
    except Exception as e:
        print(f"MPCPLプレイリストの生成に失敗しました: {e}")

    # XSPF形式
    xspf_path = os.path.join(output_dir, f"{base_name}.xspf")
    try:
        with open(xspf_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<playlist version="1" xmlns="http://xspf.org/ns/0/">\n')
            f.write('  <title>Downloaded Videos (from history)</title>\n')
            f.write('  <trackList>\n')
            for video_file in video_files:
                abs_path = os.path.abspath(video_file)
                uri_path = abs_path.replace('\\', '/')
                encoded_path = urllib.parse.quote(uri_path, safe='/')
                f.write('    <track>\n')
                f.write(f'      <location>file:///{encoded_path}</location>\n')
                f.write('    </track>\n')
            f.write('  </trackList>\n')
            f.write('</playlist>\n')
        print(f"XSPFプレイリストを生成しました: {xspf_path}")
    except Exception as e:
        print(f"XSPFプレイリストの生成に失敗しました: {e}")