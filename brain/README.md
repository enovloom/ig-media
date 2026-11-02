# 自動運用のしくみ

毎日、人の手もPCも使わずに次のサイクルが回ります。

```
 04:40  数字を取る（GitHub Actions: insights）… 暗号化して insights/ に保存
   ↓
 06:10  頭脳が考える（Claude Code の定期タスク）
          測る → 分析 → 課題をしぼる → 仮説 → 台本とキャプションを書く → 予約に入れる → 日報
   ↓
 すぐ  動画を作る（GitHub Actions: render）… scenes.json から media/…/video.mp4
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
| 予約中の投稿を直す | `queue/<フォルダ>/scenes.json`（動画が自動で作り直される）・`caption.txt` |
| 予約中の投稿を止める | `queue/<フォルダ>/post.json` の `"approved"` を `false`、`"autoApprove"` も `false` |
| 頭脳の動き方を変える | `brain/PLAYBOOK.md` |

## 中身
- `brain/PLAYBOOK.md` … 頭脳が毎日従う手順
- `brain/brand.md` … ブランド・話し方・やらないこと
- `brain/format.md` … 予約投稿と台本の書き方
- `brain/ideas.md` … ネタ帳
- `brain/tools/` … 数字の復号と集計
- `studio/` … 台本から動画を作るしくみ
- `cloud/` … 投稿と数字の取得
