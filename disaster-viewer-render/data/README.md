# 市区町村名データ

出典：気象庁「地域コード」
https://www.jma.go.jp/bosai/common/const/area.json

2026年10月17日取得。class20sの名称から市区町村名を抽出し、都道府県別の最長名称順リストに加工したものです。気象庁がこの加工データやアプリを作成したものではありません。

観測点名がこのリストの市区町村名で始まる場合にまとめます。政令指定都市の観測点は市単位、東京都特別区は区単位です。地域震度（isArea=true）は観測点情報と分離します。名称が一致しないものは「名称未分類」として元の名称を残し、推測ではまとめません。

気象庁サイトの利用について： https://www.jma.go.jp/jma/kishou/info/coment.html


## Ver.0.3 震度情報用名称

https://www.data.jma.go.jp/eqev/data/joho/shindo-name.html

2026年10月17日取得。上記の市区町村名1892項目を都道府県別に取り出し、地域コードの名称と照合してseismic_names.jsonを作成しました。「栃木那珂川町」は那珂川町、「横浜中区」は横浜市の中区として扱います。観測点名に最長一致する名称を利用します。東京都特別区は市町村階層、政令指定都市の区は市の下に表示します。未対応名は「観測点」として元の名称を保持します（旧版の「名称未分類」表示から変更）。

## Ver.0.8

static/coasts.json：気象庁の津波予報区海岸線 https://www.jma.go.jp/bosai/common/const/geojson/tsunami.json を2026年10月18日に取得。予報区コードで発表情報と結合して色を付けます。

typhoon_names.json：気象庁の台風の名前一覧 https://www.jma.go.jp/jma/kishou/know/typhoon/1-5.html から国際名とカタカナ名140組を抽出（2026年10月18日）。資料にない名前の読みは創作しません。

## Ver.0.10 の津波観測点と越境台風名

static/tsunami_stations.json は気象庁の[潮位観測点リスト](https://www.data.jma.go.jp/eqev/data/bulletin/data/tsunami/stat_j.txt)を2026年10月18日に取得し、地点コードと緯度経度に加工したものです。2026年の新設地点は未収録の場合があります。data/tsunami_stations.txt は取得時の原文です。

NOLO のカタカナ名「ノロ」は[デジタル台風](https://codh.ex.nii.ac.jp/digital-typhoon/news/2026/TC2628/)と[ウェザーニュース](https://weathernews.jp/onebox/typhoon/2026/28/)で確認しました。気象庁の年次経路に番号のない TC2613 は台風に発達しなかった熱帯低気圧として扱い、時刻と強さは付け加えません。

## Ver.0.9 の台風別位置表

気象庁の https://www.data.jma.go.jp/typhoon/position_table/table2026.html に記載された個別PDF（例： https://www.data.jma.go.jp/typhoon/data/T2629.pdf ）を利用します。CSVが公表されていない台風について、発表時刻・位置・気圧・最大風速などを抽出します。PDFは速報値の場合があり、後日訂正される可能性があります。tests/T2629.pdfは抽出検証用の実例です。

## Ver.0.12 の津波年次履歴

tsunami_2026.json は、P2P地震情報の気象庁発表記録（https://api.p2pquake.net/v2/jma/tsunami ）から2026年4月・6月・7月の発表を時刻ごとに保存したものです。観測値は2026年4月20日23:52と6月8日16:54の配信記録（Yahoo!天気・災害）、4月20日17:46の沖合観測（日本気象協会）から事実データを転記しました。出典リンクは各履歴にあります。観測点の位置は気象庁の潮位観測点リストに照合したもので、観測値そのものの測定時刻と発表時刻は別です。公開電文の全履歴を網羅するものではありません。



2026年の津波履歴には、気象庁の2026年9月30日と10月10日の津波予報電文も含めています。各行の `url` は発表原文です。
