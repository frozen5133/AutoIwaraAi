import os
import urllib.parse
from datetime import datetime

# プレイリストの最低ファイル数（デフォルト）
DEFAULT_MIN_PLAYLIST_FILES = 30

# ネットワークパス置換設定
NETWORK_DRIVE_MAPPING = {
    'R:': '\\\\192.168.1.251\\RDrv'
}


def convert_to_network_path(file_path: str) -> str:
    """ローカルパスをネットワークパスに変換する"""
    result = file_path
    for drive, network_path in NETWORK_DRIVE_MAPPING.items():
        if result.startswith(drive):
            result = result.replace(drive, network_path, 1)
            break
    return result


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
                f.write(f'      <location>file:{encoded_path}</location>\n')
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


def extract_page_date_from_source(source_url: str) -> str:
    """source URLのクエリpathパラメータから日付を抽出する（例: path=2026%2F04%2F18）"""
    try:
        parsed = urllib.parse.urlparse(source_url)
        query = urllib.parse.parse_qs(parsed.query)
        path_value = query.get('path', [None])[0]
        if path_value:
            # URLデコードしてパスを取得
            decoded_path = urllib.parse.unquote(path_value)
            # pathが YYYY/MM/DD 形式かチェック
            parts = decoded_path.split('/')
            if len(parts) >= 3:
                year, month, day = parts[0], parts[1], parts[2]
                if year.isdigit() and month.isdigit() and day.isdigit():
                    # 年/月/日 を 年-月-日 形式で返す
                    return f"{year}-{month}-{day}"
    except Exception:
        pass
    return 'unknown'


def generate_playlist_from_history(history_path: str, output_dir: str, min_files: int = DEFAULT_MIN_PLAYLIST_FILES) -> None:
    """ダウンロード履歴ファイルからプレイリストを生成する（page日付ごとにグループ化）
    
    Args:
        history_path: 履歴ファイルのパス
        output_dir: プレイリスト出力ディレクトリ
        min_files: 1つのプレイリストの最低ファイル数（デフォルト: 10）
    """
    if not os.path.exists(history_path):
        print(f"履歴ファイルが存在しません: {history_path}")
        return

    # 日付ごとに動画ファイルをグループ化
    date_groups: dict[str, list[tuple[str, str]]] = {}  # date -> [(output_path, source_url), ...]

    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 形式: "timestamp | page: url | source: url | output: path"
                if 'output:' in line and 'source:' in line:
                    parts = line.split('source:')
                    if len(parts) > 1:
                        source_part = parts[1]
                        # output部分を抽出
                        output_parts = source_part.split('output:')
                        if len(output_parts) > 1:
                            source_url = output_parts[0].strip()
                            output_path = output_parts[1].strip()

                            if os.path.exists(output_path):
                                # source URLからpage日付を抽出
                                page_date = extract_page_date_from_source(source_url)
                                if page_date not in date_groups:
                                    date_groups[page_date] = []
                                date_groups[page_date].append((output_path, source_url))
    except Exception as e:
        print(f"履歴ファイルの読み込みに失敗しました: {e}")
        return

    if not date_groups:
        print("履歴ファイルから動画ファイルを取得できませんでした。")
        return

    print(f"履歴から {len(date_groups)} 件の日付グループ、合計 {sum(len(v) for v in date_groups.values())} 件の動画ファイルを検出しました。")

    # 日付ごとにソート
    sorted_dates = sorted(date_groups.keys())

    # 日付ごとにプレイリストを生成（10ファイル未満の場合は次の日付も統合）
    playlist_count = 0
    current_videos: list[tuple[str, str]] = []

    for i, date in enumerate(sorted_dates):
        videos = date_groups[date]
        current_videos.extend(videos)
        print(f"日付 {date}: {len(videos)} ファイル（累計: {len(current_videos)}）")

        # min_files以上、または最後の日付の場合はプレイリストを生成
        if len(current_videos) >= min_files or i == len(sorted_dates) - 1:
            if current_videos:
                playlist_count += 1
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                # 3桁ゼロ埋めファイル数を追加
                file_count = len(current_videos)
                base_name = f"history_{date}_{file_count:03d}_{timestamp}"

                # MPCPL形式
                mpcpl_path = os.path.join(output_dir, f"{base_name}.mpcpl")
                try:
                    with open(mpcpl_path, 'w', encoding='utf-8') as f:
                        f.write("MPCPLAYLIST\n")
                        for j, (video_file, _) in enumerate(current_videos, 1):
                            abs_path = os.path.abspath(video_file)
                            # R: をネットワークパスに変換
                            network_path = convert_to_network_path(abs_path)
                            f.write(f"{j},type,0\n{j},filename,{network_path}\n")
                    print(f"MPCPLプレイリストを生成しました: {mpcpl_path} ({len(current_videos)} ファイル)")
                except Exception as e:
                    print(f"MPCPLプレイリストの生成に失敗しました: {e}")

                # XSPF形式（逐次的に閉じタグを出力 - 中断しても有効）
                xspf_path = os.path.join(output_dir, f"{base_name}.xspf")
                try:
                    with open(xspf_path, 'w', encoding='utf-8') as f:
                        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                        f.write('<playlist version="1" xmlns="http://xspf.org/ns/0/">\n')
                        f.write(f'  <title>Downloaded Videos ({date})</title>\n')
                        f.write('  <trackList>\n')
                        for video_file, _ in current_videos:
                            abs_path = os.path.abspath(video_file)
                            # R: をネットワークパスに変換
                            network_path = convert_to_network_path(abs_path)
                            uri_path = network_path.replace('\\', '/')
                            encoded_path = urllib.parse.quote(uri_path, safe='/')
                            f.write('    <track>\n')
                            f.write(f'      <location>file:{encoded_path}</location>\n')
                            f.write('    </track>\n')
                        # 逐次的に閉じタグを出力（中断してもその時点までのファイルが有効）
                        f.write('  </trackList>\n')
                        f.write('</playlist>\n')
                        f.flush()
                    print(f"XSPFプレイリストを生成しました: {xspf_path}")
                except Exception as e:
                    print(f"XSPFプレイリストの生成に失敗しました: {e}")

                # 次のプレイリスト用にリセット
                current_videos = []

    print(f"合計 {playlist_count} 個のプレイリストを生成しました。")