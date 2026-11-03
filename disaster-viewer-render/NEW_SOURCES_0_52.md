# 追加・修正データの出典と条件

確認日：2026年11月3日。

## 黄砂

[気象庁 黄砂情報](https://www.data.jma.go.jp/env/kosa/fcst/)の地表付近・日本域の解析／予測PNGと時刻一覧を利用します。JavaScriptの時刻一覧は文字列として解析し、配信されたコードを実行しません。一覧は30分キャッシュ、画像は選んだ時刻だけ読み込みます。黄砂がないとの判定を、画像取得失敗から作りません。

[気象庁の利用規約](https://www.jma.go.jp/jma/kishou/info/coment.html)を確認し、出典と元の図を表示します。独自の黄砂予報を作る機能ではありません。画像の解析・予測の区別、画像内の凡例を残しています。地形等の作成元の説明は気象庁の原ページにあります。解析予測図の更新は原ページでは毎日午前6時頃と案内されており、画面の再取得間隔とデータ自体の更新周期は別です。

## 土砂災害警戒区域

[重ねるハザードマップのオープンデータ仕様](https://disaportal.gsi.go.jp/hazardmap/copyright/opendata.html)にある全国用配信を使用します。

|区分|全国用タイルの識別子|
|---|---|
|土石流|05_dosekiryukeikaikuiki|
|急傾斜地の崩壊|05_kyukeishakeikaikuiki|
|地すべり|05_jisuberikeikaikuiki|

`https://disaportaldata.gsi.go.jp/raster/識別子/{z}/{x}/{y}.png`。`_data/都道府県番号/`を用いる別形式と混同しないよう修正しました。[利用規約](https://disaportal.gsi.go.jp/hazardmap/copyright/copyright.html)に従い、出典・加工と公式凡例を表示します。区域指定のハザードであり、土砂キキクルなどの現在の危険度ではありません。未着色・404が、安全を意味するわけではありません。

## 暑さ指数

CSVの配信・条件はNEW_SOURCES_0_51.mdを引き継ぎます。今回の数値区分は[環境省の暑さ指数の説明](https://www.wbgt.env.go.jp/wbgt.php)にある日常生活の区分（31以上・28以上・25以上・25未満）に合わせています。地域の熱中症アラートは、数値区分と別に表示します。現在値は過去3時間以内の実況推定値に限定し、過去の記録と混同しません。現在値がない場合も将来の有効な予測があれば別に表示します。

## 津波の毎秒確認

新設 `/api/realtime/tsunami` は気象庁の現在一覧・掲載終了情報・必要な新規発表だけを扱います。約1秒ごとのブラウザー照会を、最短10秒間隔の共通HTTP確認にまとめます。既存のP2P WebSocketも併用します。1Hzの公式配信契約を追加したものではなく、常に1秒以内に原発表を取得できる保証はありません。失敗中は前回状態と未確認を明記します。ゼロ閲覧者でこの新設処理が動く仕組みではありません。

## 河川情報センター

[水防災オープンデータ提供サービス](https://www.river.or.jp/koeki/opendata/index.html)は利用可能ですが、無契約・無料の公開APIではありません。[方式](https://www.river.or.jp/koeki/opendata/hoshiki.html)、[料金](https://www.river.or.jp/koeki/opendata/ryokin.html)、[申込み・契約](https://www.river.or.jp/koeki/opendata/order.html)を確認しました。今回追加したのは案内へのリンクです。データ購読・課金・申込みはしていません。接続先、契約する項目・地域、再提供条件、受信形式の詳細が確定していないため、ダミー接続や契約が必要な機能を実装済みとは表示しません。
