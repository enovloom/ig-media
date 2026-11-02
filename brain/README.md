# 自動運用のしくみ

毎日、人の手もPCも使わずに次のサイクルが回ります。

```
 04:40  数字を取る（GitHub Actions: insights）… 暗号化して insights/ に保存
   ↓
 06:10  頭脳が考える（Claude Code の定期タスク）
          測る → 分析 → 課題をしぼる → 仮説 → 台本とキャプションを書く → 予約に入れる → 日報
   ↓
 すぐ  動画を作る（GitHub Actions: render）… scenes.json から auto/media/…/video.mp4
   ↓
 予約時刻  投稿する（GitHub Actions: autopost）
   ↓
 翌朝  また数字を取る …
```

## スマホ・PCでできること（GitHub のアプリやサイトで）
| やりたいこと | 触るファイル |
|---|---|
| 今日の日報を読む | `enovloom/notes` → `brain/reports/` |
| 自動投稿を一時停止 | `brain/settings.json` の `"paused"` を `true` |
| 1日の本数・時刻を変える | `brain/settings.json` の `postsPerDay`・`slots` |
| 話し方・ルールを変える | `brain/brand.md` |
| ネタを足す | `brain/ideas.md` |
| 予約中の投稿を直す | `auto/queue/<フォルダ>/scenes.json`（動画が自動で作り直される）・`caption.txt` |
| 予約中の投稿を止める | `auto/hold.json` の `hold` にフォルダ名を足す（`queue/` と `auto/queue/` のどちらでも効く） |
| 頭脳の動き方を変える | `brain/PLAYBOOK.md` |

`queue/` と `media/` はPCから同期される場所です。PCにないファイルは消されるので、自動で作る予約は `auto/` に置いています。

## 中身
- `brain/PLAYBOOK.md` … 頭脳が毎日従う手順
- `brain/brand.md` … ブランド・話し方・やらないこと
- `brain/format.md` … 予約投稿と台本の書き方
- `brain/ideas.md` … ネタ帳
- `brain/tools/` … 数字の復号と集計
- `studio/` … 台本から動画を作るしくみ
- `cloud/` … 投稿と数字の取得

## トークンの作り直し（およそ 90 日に 1 回）
Instagram のトークンは、Meta の「データアクセスの期限」（今は 2027-01-31 ごろ）を過ぎると止まります。期限の 3 週間前になると、日報のいちばん上で知らせます。
1. https://developers.facebook.com/tools/explorer/ で Meta App「enovloom autopost」（App ID `2087779492103579`）を選ぶ
2. Permissions に `pages_show_list` `business_management` `instagram_basic` `instagram_content_publish` `pages_read_engagement` `instagram_manage_insights` を入れて「Generate Access Token」
3. https://developers.facebook.com/tools/debug/accesstoken/ に貼って「アクセストークンを延長」
4. Explorer に延長したトークンを入れて `me/accounts` を実行し、ページの `access_token`（EAA…）をコピー
5. https://github.com/enovloom/ig-media/settings/secrets/actions の `IG_PAGE_TOKEN` を更新
