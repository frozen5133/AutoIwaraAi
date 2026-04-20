import os
import re
import urllib.parse
import urllib.request
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from playlist import init_playlist_files, append_playlist_entry, finalize_playlist, generate_playlist_from_history

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
DOWNLOAD_DELAY = 10  # ダウンロード間隔（秒）
TARGET_URLS_LIST_FILE_PATH = 'R:\\target_urls.txt'  # 動画URLを記録するファイルのパス
FAILURE_URLS_LIST_FILE_PATH = 'R:\\failure_urls.txt'  # ダウンロード失敗したURLを記録するファイルのパス

def sanitize_filename(name: str) -> str:
    """ファイル名に使えない文字を置換する"""
    if not name:
        return 'unknown'
    name = name.strip()
    name = re.sub(r'[\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def extract_video_id(video_url: str) -> str:
    """動画URLから/video/の後の動画IDを抽出する"""
    parts = video_url.split('/')
    for i, part in enumerate(parts):
        if part == 'video' and i + 1 < len(parts):
            return parts[i + 1].split('?')[0]  # クエリストリングを除外
    return ''


def get_source_filename(source_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(source_url)
    query = urllib.parse.parse_qs(parsed.query)
    filename = query.get('filename', [None])[0]
    if filename:
        name, ext = os.path.splitext(filename)
        return name, ext.lstrip('.')
    path_filename = os.path.basename(parsed.path)
    if path_filename:
        name, ext = os.path.splitext(path_filename)
        return name, ext.lstrip('.')
    return 'video', 'mp4'


def is_preview_source(source_url: str) -> bool:
    name, _ = get_source_filename(source_url)
    return name.upper().endswith('_PREVIEW')


def get_url_content_length(url: str) -> int:
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=15)
        if response.status_code == 200:
            length = response.headers.get('Content-Length')
            return int(length) if length and length.isdigit() else 0
    except Exception:
        pass
    return 0


def select_largest_source(sources: list[str]) -> str | None:
    if not sources:
        return None
    best = None
    best_size = -1
    for src in sources:
        if is_preview_source(src):
            print(f"プレビュー動画を除外: {src}")
            continue
        size = get_url_content_length(src)
        print(f"{src} のサイズ: {size}")
        if size > best_size:
            best_size = size
            best = src
    return best


def extract_page_info(video_url: str) -> tuple[str, str, list[str]]:
    """Seleniumで動画ページをレンダリングし、username/title/video sourceを取得する"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(video_url)
        time.sleep(6)

        title = driver.title or ''
        title = title.split(' | ')[0].strip()

        username = 'unknown'
        profile_links = [
            a for a in driver.find_elements('tag name', 'a')
            if (href := a.get_attribute('href')) and '/profile/' in href
        ]
        for a in profile_links:
            text = a.text.strip()
            if text:
                username = text
                break

        video_sources = []
        for video in driver.find_elements('tag name', 'video'):
            src = video.get_attribute('src')
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                video_sources.append(src)

        return username, title, video_sources
    except Exception as e:
        print(f"ページ情報の取得に失敗しました: {e}")
        return 'unknown', 'unknown', []
    finally:
        driver.quit()


def download_video(source_url: str, output_path: str) -> None:
    print(f"ダウンロード中: {source_url}")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            urllib.request.urlretrieve(source_url, output_path)
            print(f"ダウンロード完了: {output_path}")
            return
        except Exception as e:
            print(f"ダウンロード失敗 (試行 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("リトライします...")
                time.sleep(2)  # リトライ間隔
            else:
                print("最大リトライ回数に達しました。このファイルのダウンロードをキャンセルします。")
                raise  # 例外を再送して上位で処理


def get_unique_output_path(original_path: str) -> str:
    base, ext = os.path.splitext(original_path)
    counter = 1
    candidate = f"{base}_{counter}{ext}"
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{base}_{counter}{ext}"
    return candidate


def append_history(user_dir: str, video_url: str, source_url: str, output_path: str) -> None:
    history_path = os.path.join(user_dir, 'download_history.txt')
    history_path2 = os.path.join(BASE_OUTPUT_DIR, 'download_history.txt')
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"{timestamp} | page: {video_url} | source: {source_url} | output: {output_path}\n"
    try:
        with open(history_path, 'a', encoding='utf-8') as history_file:
            history_file.write(entry)
        with open(history_path2, 'a', encoding='utf-8') as history_file2:
            history_file2.write(entry)
    except Exception as e:
        print(f"履歴ファイルへの追記に失敗しました: {e}")


def append_failure_url(video_url: str) -> None:
    """ダウンロード失敗したURLをFAILURE_URLS_LIST_FILE_PATHに追記する"""
    try:
        with open(FAILURE_URLS_LIST_FILE_PATH, 'a', encoding='utf-8') as failure_file:
            failure_file.write(f"{video_url}\n")
        print(f"失敗URLを記録しました: {video_url}")
    except Exception as e:
        print(f"失敗URLの記録に失敗しました: {e}")


def increment_page_param(url: str) -> str | None:
    """URLのpageクエリを増加させる。pageパラメータがない場合は1を追加する（0スタート）。"""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if 'page' in query and query['page']:
        try:
            current_page = int(query['page'][0])
        except ValueError:
            return None
        query['page'][0] = str(current_page + 1)
    else:
        query['page'] = ['1']
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def get_video_urls_from_list_page(list_url: str) -> list[str]:
    """リストページから全ページの動画URLを取得（ページング対応）"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    video_urls = []

    try:
        current_url = list_url
        page_index = 0
        
        while current_url and page_index < 100:  # 無限ループ対策
            print(f"\n--- ページ {page_index} を取得中: {current_url} ---")
            driver.get(current_url)
            time.sleep(7)

            # 複数のセレクタを試す
            selectors = ['.videoTeaser__thumbnail', 'a[href*="/video/"]']
            teasers = []
            for selector in selectors:
                teasers = driver.find_elements('css selector', selector)
                if teasers:
                    print(f"セレクタ '{selector}' で {len(teasers)} 件見つかりました。")
                    break
                else:
                    print(f"セレクタ '{selector}' では見つかりませんでした。")

            page_video_count = 0
            for teaser in teasers:
                href = teaser.get_attribute('href')
                if href and href.startswith(COMPARE_BASE_URL):
                    video_urls.append(href)
                    page_video_count += 1

            if page_video_count == 0:
                print(f"ページ {page_index} から動画URLを1件も取得できませんでした。ページングを終了します。")
                break

            # ページングがあるかどうかを確認し、page=を増加させる
            next_page_url = None
            pagination_detected = False
            try:
                pagination_elements = driver.find_elements('css selector', '.pagination, .pagination__item, a[rel="next"], a[aria-label="Next"], a[href*="page="]')
                pagination_detected = bool(pagination_elements)
            except Exception:
                pagination_detected = False

            if pagination_detected:
                incremented = increment_page_param(current_url)
                if incremented and incremented != current_url:
                    next_page_url = incremented
                    print(f"ページングを検出しました。pageパラメータを増加します: {next_page_url}")
                else:
                    print("ページングを検出しましたが、pageパラメータの増加に失敗しました。通常のリンク探索にフォールバックします。")

            current_url = next_page_url
            page_index += 1

        print(f"\n全ページ取得完了: 計 {len(video_urls)} 件の動画URLを取得しました。")
        return video_urls
    except Exception as e:
        print(f"リストページの取得に失敗しました: {e}")
        return video_urls
    finally:
        driver.quit()


if __name__ == '__main__':
    import sys

    # コマンドライン引数の処理
    # 例: python iwara_download.py --playlist-from-history R:\iwara.ai\download_history.txt
    if len(sys.argv) >= 3 and sys.argv[1] == '--playlist-from-history':
        history_path = sys.argv[2]
        # 履歴ファイルと同じディレクトリに出力
        output_dir = os.path.dirname(history_path) or '.'
        print(f"履歴ファイルからプレイリストを生成します: {history_path}")
        generate_playlist_from_history(history_path, output_dir)
    else:
        # 通常のダウンロードモード
        while True:
            # TARGET_URLS_LIST_FILE_PATH からURLリストを読み込む
            target_urls = []
            if os.path.exists(TARGET_URLS_LIST_FILE_PATH):
                try:
                    with open(TARGET_URLS_LIST_FILE_PATH, 'r', encoding='utf-8') as f:
                        target_urls = [line.strip() for line in f if line.strip()]
                    # ファイルを空にする
                    with open(TARGET_URLS_LIST_FILE_PATH, 'w', encoding='utf-8') as f:
                        f.write('')
                    print(f'{TARGET_URLS_LIST_FILE_PATH} から {len(target_urls)} 件のURLを読み込みました。')
                except Exception as e:
                    print(f'URLリストファイルの読み込みに失敗しました: {e}')
                    target_urls = []

            # URLリストがある場合はそれを使用、ない場合は手動入力
            if target_urls:
                url_list = target_urls
            else:
                url_list = []
                while True:
                    list_url = input('iwara.aiのリストページURLを入力してください（終了するにはEnterのみ）: ').strip()
                    if not list_url:
                        break
                    url_list.append(list_url)
                
                # 手動入力でURLが一つも入力されなかった場合はプログラム終了
                if not url_list:
                    print('終了します。')
                    break

            # すべてのURLから動画URLを収集
            all_video_urls = []
            for list_url in url_list:
                if not list_url:
                    continue

                print(f'\n=== URL処理開始: {list_url} ===')

                # URLに基づいて定数を設定
                parsed = urllib.parse.urlparse(list_url)
                domain = parsed.netloc
                if 'iwara.ai' in domain:
                    BASE_OUTPUT_DIR = r"R:\iwara.ai"
                    COMPARE_BASE_URL = 'https://www.iwara.ai/video/'
                elif 'iwara.tv' in domain:
                    BASE_OUTPUT_DIR = r"R:\iwara.tv"
                    COMPARE_BASE_URL = 'https://www.iwara.tv/video/'
                else:
                    print("サポートされていないドメインです。スキップします。")
                    continue

                os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

                # list_url が動画ページのURLの場合、直接そのURLを使用
                if list_url.startswith(COMPARE_BASE_URL) and list_url != COMPARE_BASE_URL:
                    video_urls = [list_url]
                    print(f'動画ページのURLが指定されました: {list_url}')
                else:
                    video_urls = get_video_urls_from_list_page(list_url)
                    print(f'見つかった動画URL: {len(video_urls)} 件')

                # 動画URLにメタデータを付与して保存
                for video_url in video_urls:
                    all_video_urls.append({
                        'url': video_url,
                        'base_output_dir': BASE_OUTPUT_DIR,
                        'compare_base_url': COMPARE_BASE_URL
                    })

                print(f'=== URL処理完了: {list_url} ===\n')

            print(f'\n全URLから {len(all_video_urls)} 件の動画URLを収集しました。')

            # ダウンロードしたファイルのリスト
            downloaded_files = []

            # プレイリストファイルを初期化（ループ内で1回だけ）
            mpcpl_path, xspf_path = init_playlist_files(BASE_OUTPUT_DIR)

            # 収集したすべての動画をダウンロード
            for i, video_info in enumerate(all_video_urls, 1):
                video_url = video_info['url']
                BASE_OUTPUT_DIR = video_info['base_output_dir']
                COMPARE_BASE_URL = video_info['compare_base_url']

                print(f'\n--- 動画 {i}/{len(all_video_urls)}: {video_url} ---')

                username, title, sources = extract_page_info(video_url)
                print(f'username={username}, title={title}, sources={sources}')

                # ページ情報取得に失敗した場合
                if username == 'unknown' and title == 'unknown' and not sources:
                    print('ページ情報の取得に失敗しました。スキップします。')
                    append_failure_url(video_url)
                    continue

                selected_source = select_largest_source(sources)
                if not selected_source:
                    print('動画ソースが見つかりませんでした。スキップします。')
                    append_failure_url(video_url)
                    continue
                original_filename, ext = get_source_filename(selected_source)
                video_id = extract_video_id(video_url)
                output_filename = f"{sanitize_filename(username)}_{sanitize_filename(video_id)}_{sanitize_filename(title)}.{ext}"
                user_dir = os.path.join(BASE_OUTPUT_DIR, sanitize_filename(username))
                os.makedirs(user_dir, exist_ok=True)
                output_path = os.path.join(user_dir, output_filename)

                overwrite_small_file = False
                if os.path.exists(output_path):
                    existing_size = os.path.getsize(output_path)
                    if existing_size > 1024:
                        print(f"ファイルが既に存在します: {output_path}。サイズが1KBを超えるため処理を終了します。")
                        break
                    print(f"ファイルが既に存在します: {output_path}。サイズが1KB以下なので上書きします。")
                    overwrite_small_file = True

                try:
                    download_video(selected_source, output_path)
                    append_history(user_dir, video_url, selected_source, output_path)
                    downloaded_files.append(output_path)
                    # プレイリストに今すぐ追記
                    append_playlist_entry(mpcpl_path, xspf_path, output_path)
                except Exception as e:
                    if overwrite_small_file:
                        fallback_path = get_unique_output_path(output_path)
                        print(f"上書きに失敗したため、代わりに {fallback_path} を使用します。")
                        try:
                            download_video(selected_source, fallback_path)
                            append_history(user_dir, video_url, selected_source, fallback_path)
                            downloaded_files.append(fallback_path)
                            # プレイリストに今すぐ追記
                            append_playlist_entry(mpcpl_path, xspf_path, fallback_path)
                        except Exception as e2:
                            print(f"動画 {video_url} のダウンロードをスキップします: {e2}")
                            append_failure_url(video_url)
                            continue
                    else:
                        print(f"動画 {video_url} のダウンロードをスキップします: {e}")
                        append_failure_url(video_url)
                        continue

                # ダウンロード間隔を開ける（最後の動画以外）
                if i < len(all_video_urls):
                    print(f'次のダウンロードまで {DOWNLOAD_DELAY} 秒待機...')
                    time.sleep(DOWNLOAD_DELAY)

            # XSPFプレイリストファイルを完成させる
            if xspf_path:
                finalize_playlist(xspf_path)

            print('\nすべてのダウンロードが完了しました。\n')
