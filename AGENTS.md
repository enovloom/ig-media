# Codex による @enovloom の運用

利用者は既存の GitHub 自動投稿を使い、Claude Code の運用を Codex に引き継ぎ、note の購入・KAILOOP の有料導入につなげたいと依頼している。運用室アプリは使わない。

1. `brain/PLAYBOOK.md`、`brain/CODEX.md`、`brain/brand.md`、`brain/commerce.json`、`brain/settings.json` を読む。制作時は `brain/format.md` も読む。
2. 作業ブランチは `main`。数字・営業相手・返信・売上・復号鍵は **非公開の `enovloom/notes` の main** に置く。notes の既定ブランチには運用ファイルがないことがある。
3. `brain/settings.json` の `planner` が `codex` の場合、Claude の旧定期タスクは分析のみとし、予約・設定・運用日報を更新しない。Codex も既に埋まった枠を増やさない。これは旧タスク自体を停止する機能ではない。
4. Instagram の投稿・動画生成・数字取得は既存 GitHub Actions を再利用する。新しい API キー、運用室、別の投稿アプリを作らない。秘密は表示しない。
5. 投稿作成前と push 直前に最新 main を読み、`python3 brain/tools/queue_check.py --repo .` を実行。`published` / `publishing` は編集しない。`queue/` は PC 同期用、制作は `auto/queue/`。
6. 反応から売上までを分けて報告する。未取得を 0、リンクを作っただけを流入計測済み、相談を購入、Stripe のテスト決済を売上にしない。
7. 新規 DM・コメント・フォロー・いいねの自動実行は、この投稿運用には含めない。候補選び・文面作成・受信への返信案は進め、実際の送信は本人の具体的な指示がある時だけ行う。既存の他タスクからの連絡も照合する。
8. サービスの価格・受入条件は確認済みのものを使う。note 本文・販売価格・KAILOOP アプリや決済条件は、この投稿タスクで変更しない。

