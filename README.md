# Iwara.ai Video Downloader

このプログラムは、iwara.aiの動画ページURLからvideoタグ内の動画ソースを探し出し、ダウンロードするPythonスクリプトです。

## 機能

- 指定したURL内のvideoタグを解析
- BeautifulSoupで静的HTMLを解析
- Seleniumで動的コンテンツを解析（JavaScriptがロードされた後）
- 見つかった動画ソースを表示
- 動画をダウンロード（オプション）

## インストール

1. Python仮想環境を設定
2. 必要なライブラリをインストール

```bash
pip install requests beautifulsoup4 selenium webdriver-manager
```

## 使用方法

1. スクリプトを実行
2. 動画URLを指定
3. プログラムがvideoタグ内の動画ソースを探す

## 注意

- iwara.aiのコンテンツは成人向けです。適切な使用をお願いします。
- ダウンロードは著作権に注意してください。

## プレイリスト生成

ダウンロード履歴ファイルからプレイリスト（mpcpl/xspf）を生成できます。

### 方法1: iwara_download.py から実行

```bash
python iwara_download.py --playlist-from-history R:\iwara.ai\download_history.txt [--min-files N]
```

オプション:
- `--min-files N`: 1つのプレイリストの最低ファイル数（デフォルト: 30）
  - 指定数に達しない場合は次の日付の動画も統合されます
  - 例: `--min-files 20`

### 方法2: playlist.py を直接実行

```bash
python playlist.py --from-history R:\iwara.ai\download_history.txt [--min-files N]
```

### 日付ごとのグループ化

source URLのクエリパラメータ `path` から日付を抽出し、日付ごとにプレイリストを生成します。
例: `path=2026%2F04%2F18` → `2026-04-18` のグループ

出力は履歴ファイルと同じディレクトリに生成されます：
- `history_YYYY-MM-DD_NNN_YYYYMMDDHHMMSS.mpcpl`（Media Player Classic用）
- `history_YYYY-MM-DD_NNN_YYYYMMDDHHMMSS.xspf`（VLC等用）

※ `NNN` は含まれるファイル数（3桁ゼロ埋め）
例: `history_2026-04-18_030_20260422103045.mpcpl`（30ファイル）

## コード例

```python
from iwara_download import find_video_sources, find_video_sources_selenium

# URLを指定
url = "https://www.iwara.ai/video/example"

# ソースを探す
sources = find_video_sources(url)
if not sources:
    sources = find_video_sources_selenium(url)

print(sources)
```