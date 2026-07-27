# mf_attendance — MoneyForward 勤怠 一括打刻

`https://attendance.moneyforward.com/my_page/attendances` の勤怠画面に対して、
対象月の営業日（平日かつ日本の祝日を除く、未来日を除く）を **09:00 出勤 /
18:00 退勤** で一括登録するツール。既に打刻が入っている日は既定でスキップ。

MoneyForward クラウド勤怠は個人向けの公開 API が無いため、Playwright で
実 UI を操作する。初回だけ手動でログインし、以降はセッション Cookie を
`storage_state.json` に保存して使い回す。

## セットアップ

```sh
cd HubspotAnalyze/mf_attendance
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 初回ログイン

```sh
python login.py
```

Chromium ウィンドウが開くので MF ID / パスワード / 2FA を通して勤怠画面
まで到達したら、ターミナルで Enter を押す。`storage_state.json` が
書き出される。**このファイルは Cookie を含むのでコミットしないこと**
（親リポジトリの `.gitignore` で除外済み）。

## 使い方

```sh
# 今月の営業日を dry-run で確認
python bulk_stamp.py --dry-run

# 特定月
python bulk_stamp.py --month 2026-07 --dry-run
python bulk_stamp.py --month 2026-07

# 単日
python bulk_stamp.py --from 2026-07-27 --to 2026-07-27

# 時刻を変える
python bulk_stamp.py --month 2026-07 --start 09:30 --end 18:30

# 既存打刻も上書き（要注意）
python bulk_stamp.py --month 2026-07 --overwrite

# デバッグ時に画面を見たい
python bulk_stamp.py --month 2026-07 --headed
```

出力例:

```
Range: 2026-07-01 .. 2026-07-27  (18 business day(s))
2026-07-01: OK
2026-07-02: SKIP (existing value)
...
Summary: OK=17  SKIP=1  FAIL=0
```

失敗した日はスクリーンショットが `logs/YYYYMMDD_HHMMSS/<date>.png` に
残る。UI 変更でセレクタが合わなくなった場合は `bulk_stamp.py` 冒頭の
`SELECTORS` を調整する。

## 制約

- 会社設定で「上長承認後に確定」フローがある場合、本ツールは打刻の
  保存までしか行わない（申請ボタンは押さない）。必要になったら
  `--submit` オプションを別途足す。
- MF の利用規約に照らしグレー領域なので、個人利用に留めること。
  `storage_state.json` を絶対にリポジトリへコミットしないこと。
