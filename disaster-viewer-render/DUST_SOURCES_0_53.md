# 黄砂の配信元・時刻・画像利用条件

確認日：2026年11月3日。気象庁が公開する時刻一覧と原図を利用します。独自の解析・予報は作りません。配信されたJavaScriptを実行せず、時刻の文字列だけを読み取ります。種類・範囲は固定の許可リストから選び、任意URLを取得できるAPIにはしていません。

|種類|時刻・原図|説明|
|---|---|---|
|地表付近の濃度|fcst/list_js/s_jp{jp,as}_list.js → img/surf/{jp,as}/|地表から上空1kmまでのモデル濃度|
|大気中の総量|fcst/list_js/c_jp{jp,as}_list.js → img/colu/{jp,as}/|地表から大気上端までのモデル総量|
|トゥルーカラー|himawari/kosa_js/TRMTime.js → img/TRM/|可視・近赤外・赤外による再現画像。夜間は赤外|
|ダスト|himawari/kosa_js/DSTTime.js → img/DST/|赤外による砂じん識別用の合成画像。黄砂以外も含む|
|観測実況|obs/list_js/jp{jp,as}_list.js → img/{jp,as}/|目視の黄砂等の観測を日別に表示。当日は速報|

URLの基準は `https://www.data.jma.go.jp/env/kosa/`。ひまわりのアジア域は画像ファイル名の末尾が `_as.jpg` です。ひまわりの一覧はファイル名のUTCから10分を足した時刻を公式画面が表示するため、同じ処理を行って日本時間にします。日別観測を「00:00の観測」として表示しません。

解析予測図は原則毎日6時頃、ひまわり画像は1時間ごと、当日の観測実況図は毎時10分・40分頃に更新されると公式画面で案内されています。実際の提供・欠測・変更により異なります。一覧の共通キャッシュはモデル図30分、衛星・日別観測10分。画面の自動確認周期と原図の更新周期は別です。画像は選んだ時刻だけ取得します。

## 利用条件

- [気象庁の利用規約](https://www.jma.go.jp/jma/kishou/info/coment.html)
- [地表付近の解析予測図](https://www.data.jma.go.jp/env/kosa/fcst/)
- [トゥルーカラー画像](https://www.data.jma.go.jp/env/kosa/himawari/himawari-TRM.html)
- [ダスト画像](https://www.data.jma.go.jp/env/kosa/himawari/himawari-DST.html)
- [観測実況](https://www.data.jma.go.jp/env/kosa/obs/japan.html)
- [トゥルーカラー再現画像の利用について](https://www.data.jma.go.jp/sat_info/himawari/TCR.html)

トゥルーカラー画像の個別条件も確認しました。表示面積の都合から同条件(4)で認める機関略称 **JMA / NOAA/NESDIS / CSU/CIRA** を画像の近くに表示し、公式の説明・謝辞・文献・条件へのリンクを設けます。黄砂の色や未着色だけで、存在・不在や健康影響を断定しません。画像の取得に失敗した場合は、その旨を表示します。

実配信10組の確認記録はDUST_SOURCE_AUDIT_0_53.json。全画像・全時刻の完全性を確認したものではありません。
