# HubSpot 営業実績分析ツール

HubSpotのCRMデータを取得・分析し、営業実績レポートをMarkdownで生成するツールです。

## セットアップ

### 1. HubSpot Private App Tokenの作成

1. HubSpotにログイン → **Settings** (歯車アイコン)
2. 左メニュー: **Integrations** → **Private Apps**
3. **Create a private app** をクリック
4. アプリ名を入力（例: `Sales Analysis`）
5. **Scopes** タブで以下を有効化:
   - `crm.objects.deals.read`
   - `crm.objects.companies.read`
   - `crm.objects.contacts.read`
   - `crm.schemas.deals.read`
   - `crm.objects.owners.read`
6. **Create app** → トークンをコピー

### 2. 環境設定

```bash
cp .env.example .env
# .envにトークンを設定
# HUBSPOT_API_KEY=pat-xxx-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

## 使い方

```bash
# 全期間のレポートを生成
python analyze.py --period all

# 直近1年
python analyze.py --period 1y

# 直近半年
python analyze.py --period 6m

# 直近四半期
python analyze.py --period quarter

# カスタム期間
python analyze.py --period 2025-01-01:2025-12-31

# オーナー名を指定（デフォルト: Hideaki Kawano）
python analyze.py --period all --owner "Hideaki Kawano"

# 出力先を指定
python analyze.py --period all --output reports/custom_report.md
```

レポートは `reports/` ディレクトリに生成されます。
