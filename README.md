# HubSpot 営業実績分析ツール

HubSpotの営業データを分析し、各指標をMarkdownレポートとして出力するPythonスクリプトです。

## セットアップ

### 1. HubSpot Private App Token の作成

1. HubSpotにログイン
2. **Settings（設定）** → **Integrations（連携）** → **Private Apps** に移動
3. **Create a private app** をクリック
4. アプリ名を入力（例: `Sales Analysis`）
5. **Scopes** タブで以下の権限を有効化:
   - `crm.objects.deals.read` - 取引の読み取り
   - `crm.objects.companies.read` - 会社の読み取り
   - `crm.objects.contacts.read` - コンタクトの読み取り
   - `crm.schemas.deals.read` - 取引スキーマの読み取り
   - `crm.objects.owners.read` - オーナーの読み取り
6. **Create app** をクリックしてトークンをコピー

### 2. 環境設定

```bash
# .envファイルを作成
cp .env.example .env

# .envを編集してトークンを設定
# HUBSPOT_API_KEY=your_private_app_token_here

# 依存パッケージをインストール
pip install -r requirements.txt
```

## 使い方

```bash
# 全期間のデータを分析
python analyze.py --period all

# 直近1年
python analyze.py --period 1y

# 直近半年
python analyze.py --period 6m

# 直近四半期
python analyze.py --period quarter

# カスタム期間（YYYY-MM-DD:YYYY-MM-DD）
python analyze.py --period 2025-01-01:2025-12-31

# オーナー名を指定（デフォルト: Hideaki Kawano）
python analyze.py --period 6m --owner "Hideaki Kawano"

# 出力ファイルを指定
python analyze.py --period 1y --output reports/custom_report.md
```

## 出力内容

レポートには以下の指標が含まれます:

1. **取引サマリー** - 総取引数、成約率、平均成約額、平均リードタイム
2. **アクティビティ分析** - 成約までのアクティビティ数・種別内訳
3. **取引金額分析** - 金額帯別分布、月別推移
4. **業界・業種別分析** - 業界別の取引数・成約率・金額
5. **成約/失注理由分析** - 理由別の集計
6. **パイプライン推移** - 月別の新規パイプライン数・金額
7. **ハイライト** - 最高額成約、最短リードタイム等
8. **ローライト** - 最高額失注、改善が必要な領域
