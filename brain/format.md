# 予約投稿の作り方（自動・手動どちらも同じ）

1 本の投稿 = `auto/queue/<日時>_studio_<短い名前>/` のフォルダ 1 つ。例: `auto/queue/2026-11-05-2100_studio_kotowarareta/`

（`queue/` は PC から同期される場所なので、ここには作らない。PC 由来の予約を止めるときは `auto/hold.json` にフォルダ名を書く）

| ファイル | 中身 |
|---|---|
| `scenes.json` | 動画の台本。GitHub に入ると自動で動画になる（`auto/media/<同じ名前>/video.mp4`） |
| `caption.txt` | キャプション |
| `post.json` | 投稿の設定 |
| `render.json` | 動画を作った記録（自動で作られる。触らない） |

スマホの GitHub で `scenes.json` を直すと、動画も自動で作り直されます（投稿済みのものは変わりません）。

## post.json
```json
{
  "type": "reel",
  "template": "studio_chat",
  "publishAt": "2026-11-05T21:00:00+09:00",
  "approved": false,
  "autoApprove": true,
  "media": ["video.mp4"],
  "thumbOffsetMs": 1550,
  "captionFile": "caption.txt",
  "brain": {
    "theme": "任せ方",
    "hookType": "意外な結果",
    "experiment": "E001",
    "variant": "A",
    "hypothesis": "結果が意外な見出しは、3秒以内の離脱が減る"
  }
}
```
- `approved` は動画ができた時点で自動で `true` になる（`autoApprove: true` のとき）。止めたいときは `autoApprove` を `false` にする
- `brain` は分析用のメモ。手で作るときは省略してよい

## scenes.json（動画の台本）
```json
{
  "brand": "enovloom｜店長の任せ方",
  "hook": ["次の店長に誘ったら", "*即答で断られた*"],
  "chat": {
    "title": "ミサキ（スタッフ）",
    "problem": [
      { "who": "me", "text": "ミサキさん、来月から\n次の店長やってみない？" },
      { "who": "them", "text": "やりたくないです" },
      { "who": "me", "text": "えっ、絶対向いてるよ！\nみんな期待してるし…" },
      { "who": "them", "text": "…考えておきます" }
    ],
    "ng": "説得して終わり",
    "ngAfter": 2,
    "fixLabel": "こう聞く",
    "fix": [
      { "who": "me", "text": "そっか。じゃあ一つだけ\n聞かせて" },
      { "who": "me", "text": "今の仕事で、これからも\n大事にしたいことは何？" },
      { "who": "them", "text": "お客様と話す時間は\n減らしたくないです" }
    ]
  },
  "outro": {
    "title": ["説得の前に", "*大事にしたいこと*", "を聞く"],
    "question": "店長さん、あなたならどう返しますか？\nコメントで教えてください👇",
    "cta": "プロフィールのリンクから →",
    "save": "保存して、次の面談で使う"
  }
}
```
- `hook`: 画面上の見出し。1〜3 行、1 行 13 文字まで。`*〜*` で囲んだ部分が黄色になる（必ず 1 か所入れる）
- `chat.problem`: よくあるダメなやりとり（2〜5 個）。**1 個目は 0 秒目から、2 個目は 0.5 秒目に出る**。この 2 つで「あるある」が伝わるようにする
- `chat.ng`: 赤い ✕ のラベル（12 文字まで）。`ngAfter` 個目のあと、1.1〜1.5 秒目に出る
- `chat.fix`: よい返し方（1〜4 個）。`fixLabel` は緑のラベル（「こう返す」「こう聞く」など）
- `who`: `me` = 店長（右・オレンジ）、`them` = 相手（左・白）、`divider` = 「次の日」などの区切り
- 吹き出しは 1 行 14 文字・4 行まで。`\n` で改行（15 文字だと最後の 1〜2 文字だけ次の行に落ちる）
- 絵文字は 👍 👇 😊 のような絵文字専用の文字を使う。✋ ✕ ◯ などの記号系は日本語フォントの字形が優先されて、動画で消えることがある（2026-11-04 に ✋ が消えた）
- `outro`: 最後のまとめ。`title` は 1 行 12 文字まで。`question` は 1 行 20 文字までにして、長いときは `\n` で区切る（21 文字以上だと最後の文字だけ次の行に落ちる）
- 確認コマンド: `node studio/check.mjs auto/queue/<フォルダ>/scenes.json`
- 試しに動画にする: `node studio/render.mjs auto/queue/<フォルダ>/scenes.json /tmp/test.mp4`
