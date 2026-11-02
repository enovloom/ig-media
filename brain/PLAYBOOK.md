# 毎日の運用手順（自動で動く「頭脳」用）

毎朝 1 回、Claude Code の定期タスクがこの手順どおりに動きます。
人が読んで直してもよいファイルです。書き換えると、次の回から動き方が変わります。

## 置き場所
| 場所 | 公開 | 中身 |
|---|---|---|
| `enovloom/ig-media` | 公開 | 予約投稿（`queue/`）、動画（`media/`）、動画の生成（`studio/`）、この手順書とルール（`brain/`）、暗号化した数字（`insights/`） |
| `enovloom/notes` | **非公開であること** | 復号の鍵（`brain/keys/insights.pem`）、数字の履歴、学び、実験の記録、日報 |

`notes` が公開になっていたら、数字・鍵・日報は書かずに日報の冒頭で知らせて、そこで止まる。

## 0. 準備
1. `enovloom/ig-media` と `enovloom/notes` を用意する（無ければ `add_repo` で追加して clone）。どちらも `main` で作業する。
2. `notes` が非公開か確認する（`list_repos` の visibility）。
3. `brain/settings.json`・`brain/brand.md`・`brain/format.md` と、`notes` の `brain/learnings.md`・`brain/experiments.md`・直近 3 日分の `brain/reports/` を読む。

## 1. 測る
1. `bash brain/tools/decrypt.sh <notesの>/brain/keys/insights.pem /tmp/ins` で最新の数字を開く。
   - 取得から 30 時間以上たっていたら、GitHub の `insights` ワークフローを `workflow_dispatch` で動かし、数分待ってから `git pull` してやり直す。
2. `python3 brain/tools/snapshot.py --data /tmp/ins --repo . --csv <notes>/brain/metrics/posts.csv --json /tmp/rows.json` で表を作り、履歴に追記する。
3. `queue/state.json` と各 `queue/*/render.json` を見て、前日に作った投稿が動画になり、投稿されたかを確かめる。失敗していたら原因を直す（台本の修正など）。

## 2. 分析する
- 見るのは**投稿から 24 時間以上たったもの**。それより新しいものは「途中経過」として扱う。
- 漏斗の順に、いちばん詰まっている所を 1 つ決める:
  1. 届く: 1 本あたりの再生・リーチ
  2. 止まる: 3 秒以内の離脱（`skip_rate`）
  3. 見続ける: 平均視聴 ÷ 長さ（`watch_ratio`）
  4. 反応する: 保存・シェア・コメント ÷ リーチ
  5. フォローする: フォロー数、プロフィールのアクセス、リンクのタップ
- 進行中の実験（`experiments.md`）を判定する。目安は各パターン 3 本以上、24 時間後の数字で比べる。差が小さい・本数が足りないときは「継続」にする。たまたまの 1 本で結論を出さない。
- 分かったことを `learnings.md` に書く。根拠の数字と投稿名を必ず添える。前の学びと食い違ったら、どちらが正しそうかも書く。

## 3. 次の手を考える
- 詰まっている所を改善する仮説を 1〜2 個立てる。**1 回の実験で変えるのは 1 つだけ**（見出しの型、話題、最初の 2 往復の作り、長さ、投稿時刻、呼びかけ、など）。
- 新しい実験は `experiments.md` に「ID・仮説・変えるもの・比べる相手・判定の基準・開始日」を書いてから始める。
- うまくいった型は「勝ちパターン」として次の投稿に使い、残りの枠で新しいことを試す（目安は 7:3）。

## 4. 作る
`settings.json` の `paused` が `true` なら、この章は飛ばす。

1. 予約を作る日と枠を決める:
   - 今日から `planDaysAhead` 日先まで、`slots` の時刻のうち、まだ予約が無い枠
   - 1 日の本数は `postsPerDay` まで（手で作った予約も数に含める）
   - 今から `minHoursBeforePublish` 時間以内の枠には作らない
   - `touchManualPosts` が `false` なら、人が作った予約（`post.json` に `brain` が無いもの）は変えない
2. 話題を選ぶ: `brain/ideas.md` のネタ帳と学びから選ぶ。直近 14 日の投稿（`queue/` のキャプションと台本）と話題が重ならないようにする。使ったネタは `ideas.md` で「使用済み（日付）」にし、思いついたネタは書き足す。
3. 1 本ごとに `queue/<YYYY-MM-DD-HHMM>_<ローマ字の短い名前>/` を作り、`scenes.json`・`caption.txt`・`post.json` を `brain/format.md` どおりに書く。
   - `post.json` は `"approved": false, "autoApprove": true` にする。`brain` に theme・hookType・experiment・variant・hypothesis を必ず入れる
   - `brain/brand.md` のルールを守る（使ってよい事実以外の実績・数字を作らない、など）
4. 確かめる:
   - `node studio/check.mjs queue/<フォルダ>/scenes.json` が OK になるまで直す
   - `node studio/render.mjs queue/<フォルダ>/scenes.json /tmp/<フォルダ>.mp4` で試しに動画にして、0 秒・1.6 秒・中盤・最後の画面を画像で見る。文字のはみ出し、読みにくさ、不自然な日本語があれば直す。この試しの動画はコミットしない（本番の動画は GitHub が作る）
   - キャプションを声に出したつもりで読み、不自然な所を直す

## 5. 保存する
1. `ig-media`: 新しい `queue/` のフォルダと、変えた `brain/ideas.md` などを `main` にコミットしてプッシュする（プッシュで動画づくりが自動で始まる）。プッシュが失敗したら `git pull --rebase` してやり直す。
2. `notes`: `brain/metrics/`・`learnings.md`・`experiments.md`・日報をコミットしてプッシュする。

## 6. 日報を書く
`notes` の `brain/reports/YYYY-MM-DD.md` に、スマホで 1 分で読める長さで書く:
1. 昨日の結果（数字は 3〜5 個まで）
2. 分かったこと（1〜3 行）
3. 今日変えたこと・試すこと
4. 予約した投稿（時刻・見出し・ねらい）
5. 困っていること・人に判断してほしいこと（無ければ書かない）

## やってはいけないこと
- 投稿済み・投稿中の予約（`state.json` が published / publishing）を触る
- `queue/state.json`・`cloud/`・`.github/` を変える（仕組みの修正が必要なら、日報で提案するだけにする）
- 鍵や数字を公開リポジトリ（`ig-media`）に置く
- 1 日の上限を超えて予約する
- `brain/brand.md` の「やらないこと」を破る
