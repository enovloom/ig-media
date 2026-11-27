# GitHub 自動投稿を使う Codex の販売運用

目的は再生数だけでなく、note の購入、KAILOOP の相談から本番の入金・利用開始まで進めること。既存の Instagram アカウント、GitHub Actions、販売先を使う。

本人が投稿の改善から収益化、その後の売上拡大まで依頼したため、`brain/GROWTH.md` と非公開notesの `brain/sales/growth-plan.md`・`growth-state.json` も読む。初回購入を確認しても定期改善を止めない。

## 毎回の入口

`enovloom/ig-media` と **非公開**の `enovloom/notes` の main を取得する。notes の `brain/reports/`、`brain/learnings.md`、`brain/experiments.md`、`brain/sales/` を読む。秘密・復号した数字・営業相手は ig-media にコミットしない。

```sh
umask 077
bash brain/tools/decrypt.sh /path/to/notes/brain/keys/insights.pem /tmp/ig-insights
python3 brain/tools/snapshot.py --data /tmp/ig-insights --repo . --json /tmp/ig-posts.json
python3 brain/tools/queue_check.py --repo .
python3 brain/tools/outreach.py --store /path/to/notes/brain/sales status
```

売上の入力元をまだ読めなければ「購入未確認」。記録された入金 0 件と、全体の売上 0 円は違う。

## 元の X 施策から何を移すか

| 工程 | Codex と既存 GitHub での進め方 |
|---|---|
| 候補を探す | `discover.json` の実投稿を読み、経営・育成を自分の経験で書く人を選ぶ。フォロワー500〜3万は目安。個人と事業者を分け、広告・同業・自分・既存客・既連絡を除く。件数を満たすために質を下げない |
| 受付・過去の接点を確かめる | Instagram のプロフィールと実際のDM会話、Addnessの既存営業記録を照合する。公開プロフィールや「DM可」だけで販売DMへの同意があるとは扱わない。APIで未確認なら `unknown` |
| 最初に価値を渡す | KAILOOPの公開デモ、または公開済みnoteの無料部分を、最初の文面に直接添える。返信を条件にしない。無料の理由は使い方・困る点を知るため。投稿・紹介を条件にしない |
| 人ごとの識別 | `outreach.py add` が相手IDを発行。`link` はUTM付きURLを作るだけで、クーポンや自動購入計測にはならない。noteで使えない割引コードを作らない |
| 文面を作る | 名前・読んだ投稿URL・案内先を本人に合わせる。長い褒め言葉や投稿の言い直しをしない。下記の型で個別の下書きを notes に置く |
| 送る | 既存APIは投稿・分析用。新規営業DMを送信する機能はない。本人が具体的な相手と文面の送信を指示した場合だけ、許可された接続で一人ずつ操作し、送信結果を記録する。送信不明は再送しない |
| フォロー・いいね | X用APIをInstagramに転用できない。自動の営業セットとしては実行しない。反応の水増しや件数稼ぎをしない |
| 記録 | notes の `brain/sales/` に候補・接点・返信・相談・条件提示・本番入金・返金を別イベントで残す。KAILOOPの本番案件は既存Addnessの04〜07を参照し、同じ人へ別経路から重ねて連絡しない |
| 翌日 | 公開投稿はActionsの数字で確認。DMはログイン済みの実会話を読めた場合のみ確認済み。APIに見えないだけで返事なしにしない。返事案を短く作り、辞退はお礼で終了 |
| 購入後 | noteは実購入を確認。KAILOOPは本番入金と利用開始を分け、実開始日＋7日で使われたか確認。テスト購入・自分の操作は実績に含めない |

## 文面の型（まだ送信しない）

初回の個別案内は、実際に選定根拠があり、既存客でも既連絡でもない相手向けにだけ作る。

> 〈名前〉さん、はじめまして。現役店長の北山です。
>
> こちらの投稿を拝見して、ご連絡しました。
> 〈実際に読んだ投稿URL〉
>
> スタッフと決めた行動を、その後の確認までつなぐKAILOOPを作っています。無料で見られるデモがあるので、よければお試しください。
> 〈デモURL〉
>
> 店舗で使うとしたら分かりにくい所・足りない所を一つでも教えていただけると助かります。投稿や紹介はお願いしていません。
>
> 北山

相手から相談が来たときの返信案:

> ありがとうございます。今、スタッフと決めた行動は、どのように確認していますか？自店での使い方を相談したい場合はこちらです。相談だけで料金はかかりません。
> https://kailoop-pilot-interest.enovloom-6805.chatgpt.site/consult

noteを探している人には、その悩みに合う場合だけ1,980円の教材URLと含まれるシートを短く案内する。同じ返信で二つの商品を売り込まない。

## 投稿から購入まで

- 2026-11-27の本人指示により、当日の次の投稿から未公開全投稿を改善対象とする。以後の制作も、冒頭0秒から具体策が読める見出し、実際に使える会話例、本文と一致する一つの次の行動を必須にする。既に反映した `contentRevision:2026-11-27-all-future-v1` を旧実験に戻さない。
- 現在のプロフィールリンクはnote。KAILOOPを「プロフィールのリンクから」と案内しない。KAILOOPは相談ページの実URLまたはDMを案内する。キャプション内URLは通常クリックできないので、DMで届ける導線が必要。
- 無料投稿で一つのやり方を完結させる。有料noteは実践シート・記入例・2週間の進め方が必要な人に案内する。無料部分を隠して買わせない。
- 1本の主な行動は一つ。「フォロー・保存・コメント・購入」を全部頼まない。販売を主目的とする投稿は当面1日1本まで、既存の1日4本の枠内。残りの投稿も読者に役立つ内容にする。
- 販売投稿では、無料の具体策から、続きを整理する実践シートや導入相談へ自然につなげる。実践・保存を主目的にした投稿へ、習慣としてnote・フォロー・コメントの案内を付け足さない。例示した行動を、本人が実際に続けてきた習慣や実績として語らない。
- 価格・実績・販売状態は `commerce.json` と当日の公開先で確認。期限・残席・割引を作り話にしない。
- 投稿から24時間以内は途中経過。再生数と購入を結びつける証拠がなければ、効果や因果関係を断言しない。相談・本番入金の記録を3日ごとにまとめ、最初の7日で次の一変更を決める。

## 保存と再実行

台本は従来どおり `auto/queue/<日時>_studio_<名前>/`。確認後 main にpushすると、`render` が動画を作って承認状態を付け、`autopost` が予定時刻以降に送る。GitHubの定期実行には遅れがあり、時刻ぴったりの投稿は保証しない。

`queue_check.py` は未来の枠の重複、本数、公開済みと処理中の区別、購入先の取り違えを確認する。台本は別途 `studio/check.mjs` と動画の目視確認が必要。push競合後は最新状態で再確認する。

`outreach.py` は **ローカルの記録用で、外部送信・決済・自動返信を一切しない**。同じ証拠IDは重複登録しない。返金は同じ相手・商品の記録済み入金額まで。並行更新はロックし、保存は置換で行う。

```sh
python3 brain/tools/outreach.py --store /path/to/notes/brain/sales add --handle example --org example-company --reason '実投稿で確認した理由' --post-url https://www.instagram.com/p/EXAMPLE/
python3 brain/tools/outreach.py --store /path/to/notes/brain/sales link --handle example --offer kailoop_consult
python3 brain/tools/outreach.py --store /path/to/notes/brain/sales record --handle example --kind replied --source-ref 'instagram:conversation:実ID:実時刻'
# 本番の証拠を確認できた時だけ。これは決済を行うコマンドではない。
python3 brain/tools/outreach.py --store /path/to/notes/brain/sales record --kind paid --offer note_delegation --amount-jpy 1980 --source-ref 'note:purchase:実証拠ID' --order-ref 'note:実注文ID' --occurred-at '2026-11-27T10:00:00+09:00'
# 上の日付は書式例。必ず販売元の実支払日時に置き換える。流入元が不明ならInstagram経由と記録しない。
python3 brain/tools/outreach.py --store /path/to/notes/brain/sales status --month 2026-11
```

`paused:true` は**新しい台本制作を止める設定**で、予約済み投稿は止まらない。予約を止める場合は `auto/hold.json` へ対象IDを追加する。`autoApprove:false` だけにしても、既に `approved:true` の投稿は止まらない。
