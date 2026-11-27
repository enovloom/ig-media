# Codex による @enovloom の運用

利用者は既存の GitHub 自動投稿を使い、Claude Code の運用を Codex に引き継ぎ、note の購入・KAILOOP の有料導入につなげたいと依頼している。2026-11-27に「Claudeではなくこっちで」と担当をCodexに一本化する意向を確認。運用室アプリは使わない。

1. `brain/PLAYBOOK.md`、`brain/CODEX.md`、`brain/GROWTH.md`、`brain/brand.md`、`brain/commerce.json`、`brain/settings.json` を読む。制作時は `brain/format.md` も読む。本人の最新指示は、投稿の実改善を継続し、第一段階で収益化、第二段階で売上を拡大すること。金額目標・実績は非公開notesの `brain/sales/growth-plan.md` と `growth-state.json` を参照する。
2. 作業ブランチは `main`。数字・営業相手・返信・売上・復号鍵は **非公開の `enovloom/notes` の main** に置く。notes の既定ブランチには運用ファイルがないことがある。
3. `brain/settings.json` の `planner` が `codex` の場合、Claude の旧定期タスクは、この担当確認で直ちに終了する。分析・制作・送信・予約・設定変更・運用日報の更新を行わず、Codexへ再委任する別タスクも作らない。Codex も既に埋まった枠を増やさない。これは旧タスクの実行サービス側の予約を停止する機能ではなく、最新の手順を読むタスク向けの終了指示である。
4. Instagram の投稿・動画生成・数字取得は既存 GitHub Actions を再利用する。新しい API キー、運用室、別の投稿アプリを作らない。秘密は表示しない。
5. 投稿作成前と push 直前に最新 main を読み、`python3 brain/tools/queue_check.py --repo .` を実行。`published` / `publishing` は編集しない。`queue/` は PC 同期用、制作は `auto/queue/`。
6. 反応から売上までを分けて報告する。未取得を 0、リンクを作っただけを流入計測済み、相談を購入、Stripe のテスト決済を売上にしない。
7. 新規 DM・コメント・フォロー・いいねの自動実行は、この投稿運用には含めない。候補選び・文面作成・受信への返信案は進め、実際の送信は本人の具体的な指示がある時だけ行う。既存の他タスクからの連絡も照合する。
8. サービスの価格・受入条件は確認済みのものを使う。note 本文・販売価格・KAILOOP アプリや決済条件は、この投稿タスクで変更しない。

