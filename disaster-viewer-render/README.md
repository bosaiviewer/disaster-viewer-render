# あなたが行う移行手順：閲覧時取得・無料のRender試験版

2026年11月3日。今回は別ZIPの **disaster-viewer-render-v0.56.zip** を使います。Windows版をそのまま上書きしたり、PRIVATE_STARTをクラウドで実行したりする手順ではありません。

## 今回準備した構成

閲覧者のブラウザー → 同じRenderサービスの画面・API → 配信元、という構成です。画面ごとの選択・地図操作は各閲覧者のブラウザー内で独立します。取得は閲覧者の要求をきっかけに行い、Python側のキャッシュで同じ取得をまとめます。「全員が配信元へ別々に同じHTTP通信をする」方式ではありません。

常駐収集、Cron、外部の定期アクセス、Windows PC、Cloudflare Workerは使いません。P2P・WolfxのライブWebSocketは、従来どおり各閲覧者がライブ画面を開いている間に接続します。

今回は永続的な共有DBを作りません。SQLiteはRender上の一時キャッシュとして使い、再起動・休止・再配置で消えることを前提にします。同梱原文・静的データは残り、公開APIや公式アーカイブから提供される履歴を閲覧時に再取得しますが、**過去にこのサーバーだけが保存していた発表を完全に保持する構成ではありません**。その保存が必要になった段階でSupabase等を追加します。今回はSupabase登録も不要です。

## 用意するもの

- GitHubアカウント
- GitHub Desktop（大きな地図ファイルがあるため、ブラウザーのファイルアップロードだけでは不十分です）
- Renderアカウント
- この別ZIP。個人用パスワード・APIキー・Windowsの保存データは入っていません。

費用をかけない前提で、Renderのサービスは必ず **Free** を選びます。支払方法の登録や有料プランへの変更を求められ、無料の選択肢が確認できなければ作成を止めてください。カード情報をこのチャットへ送る必要はありません。

## 手順1：ZIPを展開する

1. ZIPを「すべて展開」します。
2. `disaster-viewer-render` フォルダーを開きます。
3. `cloud_entry56.py`、`gunicorn_conf56.py`、`requirements-render.txt`、`render.yaml`、`.python-version`、`static`、`data`、`templates` があることを確認します。

このフォルダーだけがアップロード対象です。既存のWindowsフォルダー、`.venv`、設定、秘密情報、SQLiteを追加しないでください。

## 手順2：GitHubへコードを置く

1. GitHub Desktopをインストールして、自分のGitHubへログインします。
2. **File → New repository** で、例えば `disaster-viewer-render` というリポジトリーを新しい場所へ作ります。
3. 作ったローカルリポジトリーをExplorerで開き、展開した `disaster-viewer-render` の**中身**をコピーします。ZIPそのものや、余分な親フォルダーごと入れないでください。
4. GitHub DesktopのChangesに、上記のファイルが見えることを確認し、Summaryに `Initial preview` 等を入力してCommitします。
5. **Publish repository** を押します。最初は **Keep this code private** をオンにしてコードをPrivateにします。

42MB程度の地図ファイルが含まれています。GitHubのブラウザーアップロードで弾かれる場合に、地図ファイルを削除して進めないでください。GitHub Desktopで通常のGitとして送ります。

## 手順3：RenderのFreeサービスを作る

1. Renderへログインし、**New → Web Service** を選びます。
2. GitHub連携を許可し、作ったリポジトリーだけを接続します。リポジトリーが見えなければ、GitHub連携のアクセス対象を確認します。
3. 次の内容を設定します。

|項目|入力する内容|
|---|---|
|Name|任意。例：disaster-viewer-preview|
|Branch|main（自分の作ったブランチに合わせる）|
|Root Directory|空欄。上記のファイルがリポジトリー直下にある場合|
|Language / Runtime|Python 3|
|Build Command|`pip install -r requirements-render.txt`|
|Start Command|`gunicorn -c gunicorn_conf56.py cloud_entry56:app`|
|Instance Type / Plan|**Free**|
|Health Check Path|`/healthz`|

`.python-version` は `3.13` としてあり、Renderがその系列の最新パッチを選びます。手動の `PYTHON_VERSION` 環境変数は今回は追加しません。

4. Environmentに次の値を設定します。

|名前|値|
|---|---|
|EV_CLOUD_ACCESS|`private`|
|EV_PREVIEW_PASSWORD|自分で決めた16文字以上の長いパスワード。英字・数字を使うと入力しやすくなります|
|EV_DATA_DIR|`/tmp/disaster-viewer56`|
|EV_WOLFX_MODE|`private`|

パスワードはRenderの環境変数画面だけに入れ、GitHub・README・チャットへ書きません。Wolfxの個別の再提供許可を取得済みという設定ではありません。配信条件は既存のWOLFX関連の説明を引き継ぎます。

5. **Create Web Service / Deploy** で初回配置を開始します。ここから外部サービスへコードが配置されます。私はこの操作を行っていません。
6. Logsで依存のインストールと起動を確認します。`Live` になったら、Renderが表示する `https://...onrender.com` を開きます。ドメインの購入は不要です。

`render.yaml` も同梱していますが、上記の手動作成とBlueprint作成を両方行わないでください。今回は画面でFreeを確認しやすい手動作成を基本にしています。

## 手順4：確認用ログインと動作確認

1. ブラウザーのログイン画面が出たら、ユーザー名は **viewer**、パスワードは上で設定した値です。
2. 最初のコールドスタートでは、Renderが起動するまで約1分待つ場合があります。リロードを連打しません。
3. ホームの設定の下でVer.0.56を確認します。
4. 地震・台風・火山・津波・警報等を順に開き、出典・更新時刻・エラー表示を確認します。
5. ライブは実験的機能の設定をオンにして開きます。初回の読み込み中は上部の地域プルダウンが無効、完了後は有効になることを確認します。
6. 別のブラウザーやスマホでも開き、地図の選択が互いに連動しないことを確認します。
7. 音はブラウザーの制限を受けるため「音声を試す」等の操作後に確認します。Render/Linuxではブラウザーの日本語音声へ切り替わります。
8. 閉じてから15分以上後に開き直す、再起動後に開く、を試します。保存したキャッシュが消える場合があり、初回取得へ戻るのはこの試験構成の制約です。

`/healthz` はプロセスの起動状態だけを返します。ここが200でも、各配信元の情報を取得できたことを保証しません。

## 一般公開へ変える場合

最初の動作確認はパスワード付きのまま行います。一般公開を決めた場合にだけ、Renderの環境変数 `EV_CLOUD_ACCESS` を `public` に変更して再配置します。認証が不要になり、URLを知る人が閲覧できます。今回はその変更をしていません。

PrivateなGitHubリポジトリーだけではサイトは非公開になりません。今回の確認用認証はサーバーで行います。機密情報・個人情報の保存用に設計したアカウントシステムではありません。ブラウザーのBasic認証は閉じるまで認証を覚える場合があるため、共有端末ではプライベートウィンドウを使って閉じます。

## 以後の修正版の反映

1. 新しいクラウド試験版の中身をローカルリポジトリーへ反映します。Windows版全体はコピーしません。
2. GitHub Desktopで差分を確認し、Commit → Pushします。
3. Renderの自動配置が有効なら、新しいコミットが配置されます。無効ならManual Deployで最新コミットを選びます。
4. URLを開き直して版番号と情報取得を確認します。環境変数のパスワードをコードへ移す必要はありません。

## 無料枠と、今回できていないこと

- Render Freeは休止・再起動・無料時間・通信量などの制限があります。本番の防災常時配信を保証する構成ではありません。
- 閲覧者が増えると通信量が増えます。サーバー内キャッシュでも、閲覧者へ送る帯域は消えません。
- 閲覧者ゼロの間は新しい発表の受信を継続しません。後から配信元が提供する範囲を補完します。
- Linux上のGunicorn、Renderの実ビルド・無料枠・スリープ復帰・実配信速度は、あなたの初回配置後の確認項目です。ローカル試験だけで確認済みとはしません。
- 一時キャッシュが消えた後の完全な履歴維持が必要なら、Supabase等の永続保存を追加する別工程が必要です。

## エラー時

|表示・状態|確認すること|
|---|---|
|パスワード未設定（503）|EV_PREVIEW_PASSWORDが16文字以上か。設定保存後の再配置が完了したか|
|401|ユーザー名viewerとパスワード。ブラウザーが古い認証を覚えている場合はプライベートウィンドウで試す|
|No open ports / 起動失敗|Start Command、gunicorn_conf56.py、RenderのPORT。app.pyを直接起動していないか|
|ModuleNotFoundError|Build Commandがrequirements-render.txtを使っているか。リポジトリー直下のファイル配置|
|古い画面|最新コミットの配置、ブラウザーの再読み込み、ホームの版番号|
|配信元だけ取得失敗|その情報の出典・時刻・Render Logsを確認。サービス全体がLiveでも配信元の制限や障害は別|
|無料枠の停止・有料の案内|無料を維持する場合はアップグレードせず、状況を確認。自動の外部アクセスで無理に維持しない|

共有してよいものはエラー文と、秘密を除いたLogsです。パスワード・Authorizationヘッダー・APIキーは共有しません。

公式資料：[Flaskの配置](https://render.com/docs/deploy-flask)、[無料枠](https://render.com/docs/free)、[Pythonバージョン](https://render.com/docs/python-version)。
