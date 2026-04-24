#!/usr/bin/env python3
"""HubSpot 営業実績分析ツール - Hideaki Kawano向け"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from dotenv import load_dotenv
from hubspot import HubSpot
from hubspot.crm.deals import (
    PublicObjectSearchRequest,
    Filter,
    FilterGroup,
)

load_dotenv()

DEAL_PROPERTIES = [
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "createdate",
    "closedate",
    "hs_closed_won_date",
    "closed_lost_reason",
    "closed_won_reason",
    "hubspot_owner_id",
    "hs_deal_stage_probability",
    "started_day",
    "dealtype",
]

COMPANY_PROPERTIES = ["name", "industry", "type", "domain"]

ACTIVITY_TYPES = {
    "notes": "ノート",
    "emails": "メール",
    "calls": "電話",
    "meetings": "ミーティング",
    "tasks": "タスク",
}

# 会社名→業界のマッピング（リサーチ結果）
COMPANY_INDUSTRY_MAP = {
    # 医療・ヘルスケア
    "ふじおか病院": "医療・ヘルスケア",
    "ほしの在宅ケアクリニック": "医療・ヘルスケア",
    "みやぎ健診プラザ": "医療・ヘルスケア",
    "ファストドクター": "医療・ヘルスケア",
    "メディカルトピア草加病院": "医療・ヘルスケア",
    "悠翔会": "医療・ヘルスケア",
    "早津江病院": "医療・ヘルスケア",
    "本間病院": "医療・ヘルスケア",
    "玉谷クリニック": "医療・ヘルスケア",
    "石橋内科": "医療・ヘルスケア",
    "美濃市立美濃病院": "医療・ヘルスケア",
    "豊見城メンタルクリニック": "医療・ヘルスケア",
    "首里ハートクリニック": "医療・ヘルスケア",
    "鼻のクリニック東京": "医療・ヘルスケア",
    "医療法人仁寿会": "医療・ヘルスケア",
    "医療法人社団DTJ": "医療・ヘルスケア",
    "医療法人社団　六心会": "医療・ヘルスケア",
    "医療法人社団博腎会": "医療・ヘルスケア",
    "医療法人社団同仁会": "医療・ヘルスケア",
    "医療法人育和会": "医療・ヘルスケア",
    "特定医療法人自由会": "医療・ヘルスケア",
    "済生会": "医療・ヘルスケア",
    "駒沢公園動物病院": "医療・ヘルスケア",
    "訪問看護ステーションFit": "医療・ヘルスケア",
    "株式会社JMDC": "医療・ヘルスケア",
    # 介護・福祉
    "いまづ聖徳園": "介護・福祉",
    "株式会社グッドライフケア東京": "介護・福祉",
    "社会福祉法人 陶都会": "介護・福祉",
    "社会福祉法人　健仁会": "介護・福祉",
    "社会福祉法人かるが会": "介護・福祉",
    "社会福祉法人長岡東山福祉会": "介護・福祉",
    "善常会": "介護・福祉",
    # 製造業
    "イハラニッケイ化学工業": "製造業（化学）",
    "オリエンタル酵母工業": "製造業（食品）",
    "ロート製薬": "製造業（製薬）",
    "三菱ガス化学": "製造業（化学）",
    "日本シイエムケイ": "製造業（電子部品）",
    "日立建機": "製造業（建設機械）",
    "株式会社　湯山製作所": "製造業（医療機器）",
    "仙台銘板": "製造業（標識・銘板）",
    "株式会社アイコットリョーワ": "製造業（タイル・建材）",
    "株式会社アシックス": "製造業（スポーツ用品）",
    # 医療機器
    "ジェイ・エム・エス": "製造業（医療機器）",
    # IT・テクノロジー
    "イオンスマートテクノロジー": "IT・テクノロジー",
    "キッセイコムテック": "IT・テクノロジー",
    "株式会社AtoJ": "IT・テクノロジー",
    "株式会社オーエスディー": "IT・テクノロジー",
    # 金融・保険
    "いちよし証券": "金融・保険",
    "株式会社かんぽ生命保険": "金融・保険",
    # 不動産
    "ネクサス・アールハウジング": "不動産",
    "明和地所": "不動産",
    "福岡地所": "不動産",
    "日本総合住生活": "不動産・住宅管理",
    # コンサルティング
    "京都総研コンサルティング": "コンサルティング",
    "ジェネックスパートナーズ": "コンサルティング",
    # 法律
    "にわ法律事務所": "法律",
    "中村・角田・松本法律事務所": "法律",
    # 教育・研究
    "インターネット・アカデミー": "教育",
    "四国医療専門学校": "教育",
    "国立大学法人東京科学大学": "教育・研究",
    "大阪大学": "教育・研究",
    "福岡看護大学": "教育",
    # 行政・公共
    "大阪府教育庁": "行政・公共",
    "広島県呉市雇用促進協議会": "行政・公共",
    "国立研究開発法人日本医療研究開発機構": "行政・公共（研究機関）",
    # 公益法人
    "公益財団法人ボーイスカウト日本連盟": "公益法人・NPO",
    "一般社団法人 東京LAB": "公益法人・NPO",
    # 物流・運輸
    "エス･ディ･ロジ": "物流・運輸",
    "エス・ディ・ロジ": "物流・運輸",
    "大王海運": "物流・運輸",
    "常滑運輸": "物流・運輸",
    # 商社
    "三菱商事マシナリ": "商社",
    # 建設・設計
    "阪急設計コンサルタント": "建設・設計",
    # 外食・サービス
    "株式会社ゼンショーホールディングス": "外食産業",
    # エンタメ・メディア
    "バンダイナムコミュージックライブ": "エンタメ・メディア",
    "ゴルフダイジェスト・オンライン": "エンタメ・メディア",
    # 人材・教育
    "ヒューマンホールディングス": "人材・教育",
    # 農業
    "鹿児島県農業協同組合中央会": "農業・協同組合",
    # その他
    "株式会社ユニサス": "IT・テクノロジー",
    "株式会社NKB Y's": "広告・マーケティング",
    "株式会社ＣＦＰ": "金融・保険",
    "サンワ": "製造業",
    "リベロ": "IT・テクノロジー",
    "トーイン": "製造業（印刷関連）",
    "OpenWork": "IT・テクノロジー（HR Tech）",
    "エポック社": "製造業（玩具）",
}


def extract_company_from_dealname(dealname):
    """取引名から会社名を抽出する（例: '会社名_プラン_詳細' → '会社名'）"""
    if not dealname:
        return "不明"
    # 先頭の会社名部分を抽出（_, -, スペース で区切られた最初の部分）
    name = re.split(r'[_\-–—]', dealname)[0].strip()
    # 「株式会社」等を含む場合は次のパートも含める
    if not name:
        return "不明"
    return name


# 会社名のキーワードから業界を自動推定するルール（優先度順）
INDUSTRY_KEYWORD_RULES = [
    # 医療・ヘルスケア
    (["病院", "クリニック", "医院", "診療所", "健診", "検診", "歯科"], "医療・ヘルスケア"),
    (["医療法人", "医療社団", "医療財団"], "医療・ヘルスケア"),
    (["訪問看護", "看護ステーション"], "医療・ヘルスケア"),
    (["製薬", "ファーマ"], "製造業（製薬）"),
    (["医療機器"], "製造業（医療機器）"),
    # 介護・福祉
    (["介護", "デイサービス", "老人保健", "福祉", "ケア", "在宅ケア"], "介護・福祉"),
    (["社会福祉法人"], "介護・福祉"),
    # 教育・研究
    (["大学", "学校", "学園", "学院", "アカデミー", "専門学校"], "教育・研究"),
    (["研究開発法人", "研究機構", "研究所"], "教育・研究"),
    # 行政・公共
    (["教育庁", "教育委員会", "市役所", "区役所", "県庁", "府庁"], "行政・公共"),
    (["促進協議会", "振興会", "振興協会"], "行政・公共"),
    # 法律
    (["法律事務所", "弁護士", "法務"], "法律"),
    # 金融・保険
    (["証券", "銀行", "信金", "信用金庫", "保険", "生命保険", "損保"], "金融・保険"),
    # 不動産
    (["不動産", "地所", "ハウジング", "住宅", "住生活"], "不動産"),
    # 建設・設計
    (["建設", "建機", "設計コンサルタント", "建築"], "建設・設計"),
    # 物流・運輸
    (["運輸", "海運", "物流", "ロジ", "倉庫", "運送"], "物流・運輸"),
    # 農業
    (["農業協同組合", "農協", "JA"], "農業・協同組合"),
    # 公益法人
    (["公益財団", "公益社団", "一般社団", "一般財団", "ボーイスカウト", "NPO"], "公益法人・NPO"),
    # コンサルティング
    (["コンサルティング", "コンサルタント"], "コンサルティング"),
    # IT・テクノロジー
    (["テクノロジー", "コムテック", "システム", "ソフト", "IT", "デジタル", "テック"], "IT・テクノロジー"),
    # 化学・製造
    (["化学工業", "化学", "ガス化学"], "製造業（化学）"),
    (["酵母", "食品"], "製造業（食品）"),
    (["製作所", "製造", "工業", "銘板"], "製造業"),
    # エンタメ
    (["ミュージック", "エンタテインメント", "エンターテイメント", "ゲーム"], "エンタメ・メディア"),
    (["ダイジェスト", "メディア", "出版", "放送"], "エンタメ・メディア"),
    # 外食
    (["ゼンショー", "フード", "飲食", "レストラン", "外食"], "外食産業"),
    # 人材
    (["ヒューマン", "人材", "リクルート", "派遣"], "人材・教育"),
    # 商社
    (["商事", "商社", "マシナリ"], "商社"),
    # スポーツ
    (["アシックス", "スポーツ"], "製造業（スポーツ用品）"),
    # 動物病院
    (["動物病院", "ペット", "獣医"], "医療・ヘルスケア（動物）"),
]


def get_industry_for_company(company_name):
    """会社名から業界を取得（1.マッピング → 2.キーワードルール → 3.不明）"""
    if not company_name or company_name == "不明":
        return "不明"

    # 1. 手動マッピングから検索
    for key, industry in COMPANY_INDUSTRY_MAP.items():
        if key.lower() in company_name.lower() or company_name.lower() in key.lower():
            return industry

    # 2. キーワードルールで自動推定
    for keywords, industry in INDUSTRY_KEYWORD_RULES:
        for kw in keywords:
            if kw in company_name:
                return industry

    return "不明"


def parse_args():
    parser = argparse.ArgumentParser(description="HubSpot 営業実績分析ツール")
    parser.add_argument(
        "--period",
        default="all",
        help="分析期間: all, 1y, 6m, quarter, or YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument(
        "--date-field",
        default="both",
        choices=["createdate", "closedate", "both"],
        help="期間フィルタの基準日: createdate(作成日), closedate(成約/失注日), both(両方を含む, デフォルト)",
    )
    parser.add_argument(
        "--owner",
        default="Hideaki Kawano",
        help="対象オーナー名 (部分一致)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="出力ファイルパス (デフォルト: reports/sales_report_YYYYMMDD.md)",
    )
    parser.add_argument(
        "--list-companies",
        action="store_true",
        help="取引名から会社名を抽出してリスト表示",
    )
    parser.add_argument(
        "--skip-activities",
        action="store_true",
        help="アクティビティ取得をスキップ（高速化）",
    )
    parser.add_argument(
        "--fiscal-quarters",
        action="store_true",
        help="FY25 Q4〜FY26 Q4 の四半期別セクションで1本のレポートを生成",
    )
    parser.add_argument(
        "--deal-type",
        default=None,
        help="取引タイプで絞り込み（例: 新規MRR）。未指定時は全タイプ",
    )
    return parser.parse_args()


def get_date_range(period_str):
    """期間文字列からstart_date, end_dateを返す"""
    now = datetime.now()
    end_date = now

    if period_str == "all":
        return None, None
    elif period_str == "1y":
        start_date = now - timedelta(days=365)
    elif period_str == "6m":
        start_date = now - timedelta(days=182)
    elif period_str == "quarter":
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start_date = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif ":" in period_str:
        parts = period_str.split(":")
        start_date = datetime.strptime(parts[0], "%Y-%m-%d")
        end_date = datetime.strptime(parts[1], "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    else:
        print(f"不明な期間指定: {period_str}")
        sys.exit(1)

    return start_date, end_date


FISCAL_QUARTERS = [
    ("FY25 Q4", datetime(2025, 11, 1), datetime(2025, 12, 31, 23, 59, 59)),
    ("FY26 Q1", datetime(2026, 1, 1), datetime(2026, 3, 31, 23, 59, 59)),
    ("FY26 Q2", datetime(2026, 4, 1), datetime(2026, 6, 30, 23, 59, 59)),
    ("FY26 Q3", datetime(2026, 7, 1), datetime(2026, 9, 30, 23, 59, 59)),
    ("FY26 Q4", datetime(2026, 10, 1), datetime(2026, 12, 31, 23, 59, 59)),
]

FISCAL_RANGE_START = FISCAL_QUARTERS[0][1]
FISCAL_RANGE_END = FISCAL_QUARTERS[-1][2]


def _parse_hubspot_datetime(value):
    """HubSpot の日付プロパティ (ISO-8601 文字列 or ms数値) を naive datetime に変換"""
    if value is None or value == "":
        return None
    # ISO-8601 文字列（HubSpot SDK の通常の返却形式）
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            # 数値文字列の場合のフォールバック
            try:
                return datetime.fromtimestamp(int(value) / 1000)
            except (ValueError, TypeError):
                return None
        # tz-aware を naive に揃える（既存ロジックと一致させる）
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    # 数値の場合（ms）
    try:
        return datetime.fromtimestamp(int(value) / 1000)
    except (ValueError, TypeError):
        return None


def _in_range(value, q_start, q_end):
    dt = _parse_hubspot_datetime(value)
    if dt is None:
        return False
    return q_start <= dt <= q_end


def _delivery_date(props):
    """納品日(started_day) を優先し、無ければ closedate にフォールバック"""
    return props.get("started_day") or props.get("closedate")


def filter_deals_for_quarter(deals, q_start, q_end):
    """納品日(started_day; 無ければcloseate)が [q_start, q_end] に入る取引を返す"""
    return [
        d for d in deals
        if _in_range(_delivery_date(d.properties), q_start, q_end)
    ]


def pipeline_in_quarter(deals, stage_map, deal_companies, q_start, q_end):
    """未来四半期向け: 納品予定日(started_day; 無ければclosedate)が該当期間のオープン案件のみ抽出し集計"""
    items = []
    for d in deals:
        delivery = _delivery_date(d.properties)
        if not _in_range(delivery, q_start, q_end):
            continue
        stage_id = d.properties.get("dealstage", "")
        stage_info = stage_map.get(stage_id, {})
        if classify_deal(stage_info) != "open":
            continue
        try:
            amount = float(d.properties.get("amount") or 0)
        except (ValueError, TypeError):
            amount = 0.0

        companies = deal_companies.get(d.id, [])
        if companies:
            company_name = (companies[0].properties.get("name") or "-").strip() or "-"
        else:
            company_name = extract_company_from_dealname(d.properties.get("dealname", "")) or "-"

        items.append({
            "id": d.id,
            "name": d.properties.get("dealname", "不明"),
            "amount": amount,
            "delivery_date": delivery,
            "stage": stage_info.get("label", stage_id),
            "company": company_name,
        })
    total_amount = sum(it["amount"] for it in items)
    return {"deals": items, "count": len(items), "amount": total_amount}


def find_owner(client, owner_name):
    """オーナー名で検索してowner_idを返す"""
    owners_list = client.crm.owners.get_all()
    for owner in owners_list:
        full_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
        email = owner.email or ""
        if (
            owner_name.lower() in full_name.lower()
            or owner_name.lower() in email.lower()
        ):
            print(f"オーナー検出: {full_name} (ID: {owner.id}, Email: {email})")
            return owner.id, full_name
    print(f"オーナー '{owner_name}' が見つかりません。")
    print("利用可能なオーナー:")
    for owner in owners_list:
        full_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
        print(f"  - {full_name} ({owner.email})")
    sys.exit(1)


def _search_deals(client, filter_groups, after=None):
    """HubSpot Search APIで取引を検索（ページング対応）"""
    all_deals = []
    while True:
        search_request = PublicObjectSearchRequest(
            filter_groups=filter_groups,
            properties=DEAL_PROPERTIES,
            limit=100,
            after=after or "0",
        )
        response = client.crm.deals.search_api.do_search(
            public_object_search_request=search_request
        )
        all_deals.extend(response.results)
        if response.paging and response.paging.next:
            after = response.paging.next.after
        else:
            break
    return all_deals


def fetch_deals(client, owner_id, start_date, end_date, date_field="both", deal_type=None):
    """取引を検索して取得
    date_field: 'createdate', 'closedate', or 'both'
    'both' = 作成日が期間内 OR 成約/失注日が期間内 の両方を取得（重複排除）
    deal_type: 指定時は dealtype プロパティが一致する取引のみ取得（例: "新規MRR"）
    """
    base_filters = [Filter(property_name="hubspot_owner_id", operator="EQ", value=owner_id)]
    if deal_type:
        base_filters.append(Filter(property_name="dealtype", operator="EQ", value=deal_type))

    if not start_date:
        # 全期間の場合
        results = _search_deals(client, [FilterGroup(filters=base_filters)])
        print(f"取引数: {len(results)}件を取得")
        return results

    start_ms = str(int(start_date.timestamp() * 1000))
    end_ms = str(int(end_date.timestamp() * 1000))

    if date_field == "both":
        # 作成日ベースで検索
        create_filters = base_filters + [
            Filter(property_name="createdate", operator="GTE", value=start_ms),
            Filter(property_name="createdate", operator="LTE", value=end_ms),
        ]
        # 成約/失注日ベースで検索
        close_filters = base_filters + [
            Filter(property_name="closedate", operator="GTE", value=start_ms),
            Filter(property_name="closedate", operator="LTE", value=end_ms),
        ]
        print("  作成日ベースで検索中...")
        deals_by_create = _search_deals(client, [FilterGroup(filters=create_filters)])
        print(f"  → {len(deals_by_create)}件")
        print("  成約/失注日ベースで検索中...")
        deals_by_close = _search_deals(client, [FilterGroup(filters=close_filters)])
        print(f"  → {len(deals_by_close)}件")

        # 重複排除してマージ
        seen_ids = set()
        all_deals = []
        for deal in deals_by_create + deals_by_close:
            if deal.id not in seen_ids:
                seen_ids.add(deal.id)
                all_deals.append(deal)
        print(f"取引数: {len(all_deals)}件を取得（重複排除後）")
        return all_deals
    else:
        filters = base_filters + [
            Filter(property_name=date_field, operator="GTE", value=start_ms),
            Filter(property_name=date_field, operator="LTE", value=end_ms),
        ]
        results = _search_deals(client, [FilterGroup(filters=filters)])
        print(f"取引数: {len(results)}件を取得")
        return results


def fetch_pipeline_stages(client):
    """パイプラインとステージのマッピングを取得"""
    pipelines = client.crm.pipelines.pipelines_api.get_all(object_type="deals")
    stage_map = {}
    pipeline_map = {}
    for pipeline in pipelines.results:
        pipeline_map[pipeline.id] = pipeline.label
        for stage in pipeline.stages:
            stage_map[stage.id] = {
                "label": stage.label,
                "pipeline": pipeline.label,
                "display_order": stage.display_order,
                "metadata": stage.metadata,
            }
    return stage_map, pipeline_map


def _get_associations_v4(client, deal_id, to_object_type):
    """v4 Associations APIで関連オブジェクトIDを取得"""
    try:
        response = client.crm.associations.v4.basic_api.get_page(
            object_type="deals",
            object_id=deal_id,
            to_object_type=to_object_type,
            limit=500,
        )
        if response and response.results:
            return [r.to_object_id for r in response.results]
    except Exception:
        pass
    return []


def fetch_associated_companies(client, deal_ids):
    """取引に関連する会社を一括取得"""
    deal_companies = {}
    total = len(deal_ids)
    company_cache = {}

    for i, deal_id in enumerate(deal_ids):
        if (i + 1) % 20 == 0 or i + 1 == total:
            print(f"  関連会社: {i + 1}/{total}件処理中...", flush=True)
        company_ids = _get_associations_v4(client, deal_id, "companies")
        if company_ids:
            companies = []
            for cid in company_ids:
                if cid in company_cache:
                    companies.append(company_cache[cid])
                    continue
                try:
                    company = client.crm.companies.basic_api.get_by_id(
                        company_id=cid, properties=COMPANY_PROPERTIES
                    )
                    companies.append(company)
                    company_cache[cid] = company
                except Exception:
                    pass
            if companies:
                deal_companies[deal_id] = companies

    print(f"関連会社: {sum(len(v) for v in deal_companies.values())}社を取得")
    return deal_companies


def fetch_deal_activities(client, deal_ids):
    """取引に関連するアクティビティ数を取得（最初の5件が全て0なら残りをスキップ）"""
    deal_activities = {}
    activity_object_types = ["notes", "emails", "calls", "meetings", "tasks"]
    total = len(deal_ids)
    sample_size = min(5, total)
    found_any = False

    # まず最初の数件をサンプリング
    print(f"  アクティビティ: 最初の{sample_size}件をサンプリング中...", flush=True)
    for i in range(sample_size):
        deal_id = deal_ids[i]
        counts = {}
        for obj_type in activity_object_types:
            ids = _get_associations_v4(client, deal_id, obj_type)
            counts[obj_type] = len(ids)
        deal_activities[deal_id] = counts
        if sum(counts.values()) > 0:
            found_any = True

    if not found_any:
        print("  → サンプルが全て0件のため、残りをスキップします")
        for deal_id in deal_ids[sample_size:]:
            deal_activities[deal_id] = {t: 0 for t in activity_object_types}
    else:
        # アクティビティが存在する場合は残りも取得
        for i, deal_id in enumerate(deal_ids[sample_size:], start=sample_size):
            if (i + 1) % 20 == 0 or i + 1 == total:
                print(f"  アクティビティ: {i + 1}/{total}件処理中...", flush=True)
            counts = {}
            for obj_type in activity_object_types:
                ids = _get_associations_v4(client, deal_id, obj_type)
                counts[obj_type] = len(ids)
            deal_activities[deal_id] = counts

    total_acts = sum(sum(c.values()) for c in deal_activities.values())
    print(f"アクティビティ: 合計{total_acts}件を取得")
    return deal_activities


def classify_deal(stage_info):
    """ステージ情報からWon/Lost/Openを判定"""
    if not stage_info:
        return "open"
    metadata = stage_info.get("metadata", {})
    if metadata.get("isClosed") == "true":
        probability = metadata.get("probability", "0")
        if probability == "1.0" or probability == "1":
            return "won"
        else:
            return "lost"
    return "open"


def analyze_data(deals, stage_map, deal_companies, deal_activities, monthly_date_field="closedate"):
    """データを分析してレポート用の構造化データを返す

    monthly_date_field: 月次集計(monthly_won/lost/pipeline)の基準日
      - "closedate" (デフォルト): 従来どおり成約/失注日ベース
      - "started_day": 納品日ベース(未設定時はclosedateにフォールバック)
    """
    results = {
        "total": len(deals),
        "won": [],
        "lost": [],
        "open": [],
        "amounts": [],
        "won_amounts": [],
        "lost_amounts": [],
        "open_amounts": [],
        "lead_times": [],
        "industries": defaultdict(lambda: {"total": 0, "won": 0, "lost": 0, "open": 0, "amount_total": 0, "amount_won": 0}),
        "won_reasons": Counter(),
        "lost_reasons": Counter(),
        # パイプライン（新規作成ベース）
        "monthly_pipeline": defaultdict(lambda: {"count": 0, "amount": 0}),
        # 成約（成約日ベース）
        "monthly_won": defaultdict(lambda: {"count": 0, "amount": 0}),
        # 失注（closedate ベース）
        "monthly_lost": defaultdict(lambda: {"count": 0, "amount": 0}),
        "activity_stats": defaultdict(list),
        "won_activities": [],
        "highlights": [],
        "lowlights": [],
    }

    for deal in deals:
        props = deal.properties
        deal_id = deal.id
        stage_id = props.get("dealstage", "")
        stage_info = stage_map.get(stage_id, {})
        status = classify_deal(stage_info)

        amount = 0
        try:
            amount = float(props.get("amount") or 0)
        except (ValueError, TypeError):
            pass

        deal_data = {
            "id": deal_id,
            "name": props.get("dealname", "不明"),
            "amount": amount,
            "stage": stage_info.get("label", stage_id),
            "pipeline": stage_info.get("pipeline", props.get("pipeline", "不明")),
            "createdate": props.get("createdate"),
            "closedate": props.get("closedate"),
            "status": status,
        }

        # 月次集計の基準日
        #  - closedate モード: monthly_pipeline=createdate, monthly_won/lost=closedate
        #  - started_day モード: 全て 納品日(未設定時はclosedateにフォールバック)
        create_str = props.get("createdate")
        close_str = props.get("closedate")

        if monthly_date_field == "started_day":
            pipeline_date_str = _delivery_date(props)
            outcome_date_str = _delivery_date(props)
        else:
            pipeline_date_str = create_str
            outcome_date_str = close_str

        # 月別パイプライン
        if pipeline_date_str:
            try:
                pl_dt = datetime.fromisoformat(pipeline_date_str.replace("Z", "+00:00"))
                month_key = pl_dt.strftime("%Y-%m")
                results["monthly_pipeline"][month_key]["count"] += 1
                results["monthly_pipeline"][month_key]["amount"] += amount
            except (ValueError, TypeError):
                pass

        # リードタイム計算(createdate→closedate)
        lead_time_days = None
        if create_str and close_str:
            try:
                create_dt = datetime.fromisoformat(create_str.replace("Z", "+00:00"))
                close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
                lead_time_days = (close_dt - create_dt).days
                if lead_time_days >= 0:
                    deal_data["lead_time"] = lead_time_days
            except (ValueError, TypeError):
                pass

        # 月別成約・失注
        if outcome_date_str and status in ("won", "lost"):
            try:
                outcome_dt = datetime.fromisoformat(outcome_date_str.replace("Z", "+00:00"))
                outcome_month = outcome_dt.strftime("%Y-%m")
                if status == "won":
                    results["monthly_won"][outcome_month]["count"] += 1
                    results["monthly_won"][outcome_month]["amount"] += amount
                else:
                    results["monthly_lost"][outcome_month]["count"] += 1
                    results["monthly_lost"][outcome_month]["amount"] += amount
            except (ValueError, TypeError):
                pass

        # アクティビティ
        activities = deal_activities.get(deal_id, {})
        total_activities = sum(activities.values())
        deal_data["activities"] = activities
        deal_data["total_activities"] = total_activities

        for act_type, count in activities.items():
            results["activity_stats"][act_type].append(count)

        if status == "won":
            results["won"].append(deal_data)
            results["won_amounts"].append(amount)
            if lead_time_days is not None:
                results["lead_times"].append(lead_time_days)
            results["won_activities"].append(total_activities)
            reason = props.get("closed_won_reason") or "理由未記載"
            results["won_reasons"][reason] += 1
        elif status == "lost":
            results["lost"].append(deal_data)
            results["lost_amounts"].append(amount)
            reason = props.get("closed_lost_reason") or "理由未記載"
            results["lost_reasons"][reason] += 1
        else:
            results["open"].append(deal_data)
            results["open_amounts"].append(amount)

        results["amounts"].append(amount)

    # 業界別分析
    for deal in deals:
        deal_id = deal.id
        props = deal.properties
        stage_id = props.get("dealstage", "")
        stage_info = stage_map.get(stage_id, {})
        status = classify_deal(stage_info)
        amount = 0
        try:
            amount = float(props.get("amount") or 0)
        except (ValueError, TypeError):
            pass

        companies = deal_companies.get(deal_id, [])
        if companies:
            for company in companies:
                industry = (company.properties.get("industry") or "不明").strip()
                if not industry:
                    industry = "不明"
                results["industries"][industry]["total"] += 1
                results["industries"][industry]["amount_total"] += amount
                if status == "won":
                    results["industries"][industry]["won"] += 1
                    results["industries"][industry]["amount_won"] += amount
                elif status == "lost":
                    results["industries"][industry]["lost"] += 1
        else:
            # フォールバック: 取引名から会社名を抽出して業界を推定
            company_name = extract_company_from_dealname(props.get("dealname", ""))
            industry = get_industry_for_company(company_name)
            results["industries"][industry]["total"] += 1
            results["industries"][industry]["amount_total"] += amount
            if status == "won":
                results["industries"][industry]["won"] += 1
                results["industries"][industry]["amount_won"] += amount
            elif status == "lost":
                results["industries"][industry]["lost"] += 1

    # ハイライト
    if results["won"]:
        top_deal = max(results["won"], key=lambda d: d["amount"])
        results["highlights"].append(
            f"最高額成約: **{top_deal['name']}** (¥{top_deal['amount']:,.0f})"
        )
        won_with_lt = [d for d in results["won"] if d.get("lead_time") is not None and d["lead_time"] >= 0]
        if won_with_lt:
            fastest = min(won_with_lt, key=lambda d: d["lead_time"])
            results["highlights"].append(
                f"最短成約: **{fastest['name']}** ({fastest['lead_time']}日)"
            )

    # ローライト
    if results["lost"]:
        top_lost = max(results["lost"], key=lambda d: d["amount"])
        results["lowlights"].append(
            f"最高額失注: **{top_lost['name']}** (¥{top_lost['amount']:,.0f})"
        )
        lost_with_lt = [d for d in results["lost"] if d.get("lead_time") is not None]
        if lost_with_lt:
            slowest = max(lost_with_lt, key=lambda d: d["lead_time"])
            results["lowlights"].append(
                f"最長リードタイム失注: **{slowest['name']}** ({slowest['lead_time']}日)"
            )

    return results


def generate_report(results, owner_name, period_str, start_date, end_date):
    """Markdownレポートを生成"""
    now = datetime.now()
    lines = []

    def add(text=""):
        lines.append(text)

    add("# HubSpot 営業実績分析レポート")
    add()
    add("## 分析概要")
    add()
    add(f"- **対象**: {owner_name}")
    if start_date and end_date:
        add(f"- **期間**: {start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}")
    else:
        add("- **期間**: 全期間")
    add(f"- **生成日**: {now.strftime('%Y/%m/%d %H:%M')}")
    add()

    # === 共通変数 ===
    won_count = len(results["won"])
    lost_count = len(results["lost"])
    open_count = len(results["open"])
    decided = won_count + lost_count
    win_rate = (won_count / decided * 100) if decided > 0 else 0
    avg_won = (sum(results["won_amounts"]) / won_count) if won_count > 0 else 0
    avg_lead = (sum(results["lead_times"]) / len(results["lead_times"])) if results["lead_times"] else 0
    total_won_amount = sum(results["won_amounts"])
    total_lost_amount = sum(results["lost_amounts"])
    total_open_amount = sum(results["open_amounts"])
    total_amount = sum(results["amounts"])

    # =============================================
    # 1. 成約実績サマリー
    # =============================================
    add("---")
    add()
    add("## 1. 成約実績")
    add()

    add("| 指標 | 値 |")
    add("|---|---|")
    add(f"| 成約数 | {won_count}件 |")
    add(f"| 成約合計金額 | ¥{total_won_amount:,.0f} |")
    add(f"| 平均成約額 | ¥{avg_won:,.0f} |")
    add(f"| 平均リードタイム | {avg_lead:.1f}日 |")
    add(f"| 成約率（成約/決着済） | {win_rate:.1f}%（{won_count}/{decided}件） |")
    add()

    # 月別成約推移
    if results["monthly_won"]:
        add("### 月別成約推移")
        add()
        add("| 月 | 成約件数 | 成約金額 | 累積件数 | 累積金額 |")
        add("|---|---|---|---|---|")
        cum_cnt = 0
        cum_amt = 0
        for month in sorted(results["monthly_won"].keys()):
            data = results["monthly_won"][month]
            cum_cnt += data["count"]
            cum_amt += data["amount"]
            add(f"| {month} | {data['count']}件 | ¥{data['amount']:,.0f} | {cum_cnt}件 | ¥{cum_amt:,.0f} |")
        add()

    # 成約案件一覧（上位10件）
    if results["won"]:
        add("### 成約案件（金額上位10件）")
        add()
        add("| 案件名 | 金額 | リードタイム | アクティビティ数 |")
        add("|---|---|---|---|")
        sorted_won = sorted(results["won"], key=lambda d: d["amount"], reverse=True)[:10]
        for d in sorted_won:
            lt = f"{d.get('lead_time', '-')}日" if d.get("lead_time") is not None else "-"
            add(f"| {d['name']} | ¥{d['amount']:,.0f} | {lt} | {d['total_activities']}件 |")
        add()

    # 成約金額帯分布
    won_non_zero = [a for a in results["won_amounts"] if a > 0]
    if won_non_zero:
        add("### 成約金額帯別の分布")
        add()
        brackets = [
            (0, 100000, "~¥100,000"),
            (100000, 500000, "¥100,000~¥500,000"),
            (500000, 1000000, "¥500,000~¥1,000,000"),
            (1000000, 5000000, "¥1,000,000~¥5,000,000"),
            (5000000, 10000000, "¥5,000,000~¥10,000,000"),
            (10000000, float("inf"), "¥10,000,000~"),
        ]
        add("| 金額帯 | 件数 | 小計 |")
        add("|---|---|---|")
        for low, high, label in brackets:
            matched = [a for a in won_non_zero if low <= a < high]
            if matched:
                add(f"| {label} | {len(matched)}件 | ¥{sum(matched):,.0f} |")
        add()

    # =============================================
    # 2. パイプライン（新規作成）
    # =============================================
    add("---")
    add()
    add("## 2. パイプライン（新規作成）")
    add()

    add("| 指標 | 値 |")
    add("|---|---|")
    add(f"| 期間内の新規パイプライン総数 | {results['total']}件 |")
    add(f"| 新規パイプライン総額 | ¥{total_amount:,.0f} |")
    add(f"| うち進行中 | {open_count}件（¥{total_open_amount:,.0f}） |")
    add(f"| うち成約 | {won_count}件（¥{total_won_amount:,.0f}） |")
    add(f"| うち失注 | {lost_count}件（¥{total_lost_amount:,.0f}） |")
    add()

    # 月別パイプライン推移
    if results["monthly_pipeline"]:
        add("### 月別パイプライン推移（作成日ベース）")
        add()
        all_months = sorted(set(
            list(results["monthly_pipeline"].keys()) +
            list(results["monthly_won"].keys()) +
            list(results["monthly_lost"].keys())
        ))
        add("| 月 | 新規PL件数 | 新規PL金額 | 成約件数 | 成約金額 | 失注件数 | 失注金額 |")
        add("|---|---|---|---|---|---|---|")
        for month in all_months:
            pl = results["monthly_pipeline"].get(month, {"count": 0, "amount": 0})
            wo = results["monthly_won"].get(month, {"count": 0, "amount": 0})
            lo = results["monthly_lost"].get(month, {"count": 0, "amount": 0})
            add(
                f"| {month} | {pl['count']}件 | ¥{pl['amount']:,.0f}"
                f" | {wo['count']}件 | ¥{wo['amount']:,.0f}"
                f" | {lo['count']}件 | ¥{lo['amount']:,.0f} |"
            )
        add()

    # パイプライン金額帯分布
    all_non_zero = [a for a in results["amounts"] if a > 0]
    if all_non_zero:
        add("### パイプライン金額帯別の分布（全取引）")
        add()
        brackets = [
            (0, 100000, "~¥100,000"),
            (100000, 500000, "¥100,000~¥500,000"),
            (500000, 1000000, "¥500,000~¥1,000,000"),
            (1000000, 5000000, "¥1,000,000~¥5,000,000"),
            (5000000, 10000000, "¥5,000,000~¥10,000,000"),
            (10000000, float("inf"), "¥10,000,000~"),
        ]
        add("| 金額帯 | 件数 |")
        add("|---|---|")
        for low, high, label in brackets:
            count = len([a for a in all_non_zero if low <= a < high])
            if count > 0:
                add(f"| {label} | {count}件 |")
        add()

    # =============================================
    # 3. 成約までのアクティビティ分析
    # =============================================
    add("---")
    add()
    add("## 3. 成約までのアクティビティ分析")
    add()

    if results["won_activities"]:
        avg_activities = sum(results["won_activities"]) / len(results["won_activities"])
        add(f"成約案件の平均アクティビティ数: **{avg_activities:.1f}件**")
        add()

    add("### アクティビティ種別の内訳（全案件）")
    add()
    add("| 種別 | 合計 | 平均/案件 |")
    add("|---|---|---|")
    for act_type, label in ACTIVITY_TYPES.items():
        counts = results["activity_stats"].get(act_type, [])
        total_act = sum(counts)
        avg_act = (total_act / len(counts)) if counts else 0
        add(f"| {label} | {total_act}件 | {avg_act:.1f}件 |")
    add()

    # =============================================
    # 4. 業界・業種別分析
    # =============================================
    add("---")
    add()
    add("## 4. 業界・業種別分析")
    add()

    if results["industries"]:
        add("| 業界 | 取引数 | 成約数 | 失注数 | 進行中 | 成約率 | 成約金額 | パイプライン総額 |")
        add("|---|---|---|---|---|---|---|---|")
        sorted_industries = sorted(
            results["industries"].items(),
            key=lambda x: x[1]["amount_won"],
            reverse=True,
        )
        for industry, data in sorted_industries:
            decided_ind = data["won"] + data["lost"]
            rate = (data["won"] / decided_ind * 100) if decided_ind > 0 else 0
            open_ind = data["total"] - data["won"] - data["lost"]
            add(
                f"| {industry} | {data['total']}件 | {data['won']}件 | {data['lost']}件 | {open_ind}件"
                f" | {rate:.0f}% | ¥{data['amount_won']:,.0f} | ¥{data['amount_total']:,.0f} |"
            )
        add()
    else:
        add("（関連する会社データがありません）")
        add()

    # =============================================
    # 5. 成約/失注理由分析
    # =============================================
    add("---")
    add()
    add("## 5. 成約/失注理由分析")
    add()

    add("### 成約理由")
    add()
    if results["won_reasons"]:
        add("| 理由 | 件数 |")
        add("|---|---|")
        for reason, count in results["won_reasons"].most_common():
            add(f"| {reason} | {count}件 |")
        add()
    else:
        add("（成約案件なし）")
        add()

    add("### 失注理由")
    add()
    if results["lost_reasons"]:
        add("| 理由 | 件数 |")
        add("|---|---|")
        for reason, count in results["lost_reasons"].most_common():
            add(f"| {reason} | {count}件 |")
        add()
    else:
        add("（失注案件なし）")
        add()

    # 失注案件一覧（金額上位5件）
    if results["lost"]:
        add("### 失注案件（金額上位5件）")
        add()
        add("| 案件名 | 金額 | リードタイム | 失注理由 |")
        add("|---|---|---|---|")
        sorted_lost = sorted(results["lost"], key=lambda d: d["amount"], reverse=True)[:5]
        for d in sorted_lost:
            lt = f"{d.get('lead_time', '-')}日" if d.get("lead_time") is not None else "-"
            # find reason from deal properties
            add(f"| {d['name']} | ¥{d['amount']:,.0f} | {lt} | - |")
        add()

    # =============================================
    # 6. ハイライト
    # =============================================
    add("---")
    add()
    add("## 6. ハイライト")
    add()
    if results["highlights"]:
        for h in results["highlights"]:
            add(f"- {h}")
    else:
        add("（特筆事項なし）")

    if results["industries"]:
        best_industry = None
        best_rate = 0
        for ind, data in results["industries"].items():
            decided_ind = data["won"] + data["lost"]
            if decided_ind >= 2:
                rate = data["won"] / decided_ind
                if rate > best_rate:
                    best_rate = rate
                    best_industry = ind
        if best_industry:
            add(f"- 成約率が高い業界: **{best_industry}** ({best_rate*100:.0f}%)")

    # パイプライン成長のハイライト
    if results["monthly_pipeline"]:
        months = sorted(results["monthly_pipeline"].keys())
        if len(months) >= 2:
            last = results["monthly_pipeline"][months[-1]]
            prev = results["monthly_pipeline"][months[-2]]
            if prev["count"] > 0:
                growth = ((last["count"] - prev["count"]) / prev["count"]) * 100
                if growth > 0:
                    add(f"- パイプライン件数: {months[-2]}→{months[-1]}で **+{growth:.0f}%** 増加")
                elif growth < 0:
                    add(f"- パイプライン件数: {months[-2]}→{months[-1]}で **{growth:.0f}%** 減少")
    add()

    # =============================================
    # 7. ローライト
    # =============================================
    add("---")
    add()
    add("## 7. ローライト")
    add()
    if results["lowlights"]:
        for ll in results["lowlights"]:
            add(f"- {ll}")
    else:
        add("（特筆事項なし）")

    if results["lost_reasons"]:
        top_reason = results["lost_reasons"].most_common(1)[0]
        add(f"- 最多失注理由「{top_reason[0]}」({top_reason[1]}件) への対策検討を推奨")
    if results["lead_times"]:
        long_deals = [d for d in results["won"] if d.get("lead_time", 0) > avg_lead * 1.5]
        if long_deals:
            add(f"- 平均より50%以上長いリードタイムの成約案件が{len(long_deals)}件 — プロセス改善の余地あり")
    add()

    add("---")
    add(f"*レポート生成: {now.strftime('%Y/%m/%d %H:%M')}*")

    return "\n".join(lines)


def _quarter_summary_row(label, status_label, results):
    """四半期サマリー表の1行を生成（過去/現在向け）"""
    won_count = len(results["won"])
    lost_count = len(results["lost"])
    open_count = len(results["open"])
    decided = won_count + lost_count
    win_rate = (won_count / decided * 100) if decided > 0 else 0
    avg_lead = (sum(results["lead_times"]) / len(results["lead_times"])) if results["lead_times"] else 0
    total_won = sum(results["won_amounts"])
    total_lost = sum(results["lost_amounts"])
    total_open = sum(results["open_amounts"])
    return (
        f"| {label} | {status_label} | {results['total']}件"
        f" | {won_count}件 | ¥{total_won:,.0f}"
        f" | {lost_count}件 | ¥{total_lost:,.0f}"
        f" | {open_count}件 | ¥{total_open:,.0f}"
        f" | {win_rate:.0f}% | {avg_lead:.0f}日 |"
    )


def _future_summary_row(label, pipeline):
    """四半期サマリー表の1行を生成（未来向け: パイプラインのみ）"""
    return (
        f"| {label} | 未来（予定） | - "
        f"| - | -"
        f" | - | -"
        f" | {pipeline['count']}件 | ¥{pipeline['amount']:,.0f}"
        f" | - | - |"
    )


def _render_quarter_detail(label, start, end, results):
    """過去/現在四半期の詳細セクションを生成"""
    out = []
    won_count = len(results["won"])
    lost_count = len(results["lost"])
    open_count = len(results["open"])
    decided = won_count + lost_count
    win_rate = (won_count / decided * 100) if decided > 0 else 0
    avg_won = (sum(results["won_amounts"]) / won_count) if won_count > 0 else 0
    avg_lead = (sum(results["lead_times"]) / len(results["lead_times"])) if results["lead_times"] else 0
    total_won = sum(results["won_amounts"])
    total_lost = sum(results["lost_amounts"])
    total_open = sum(results["open_amounts"])
    total_amount = sum(results["amounts"])

    out.append("---")
    out.append("")
    out.append(f"## {label} ({start.strftime('%Y/%m/%d')} 〜 {end.strftime('%Y/%m/%d')})")
    out.append("")
    out.append("### 主要指標")
    out.append("")
    out.append("| 指標 | 値 |")
    out.append("|---|---|")
    out.append(f"| 期間内の取引数 | {results['total']}件 |")
    out.append(f"| 成約数 | {won_count}件 |")
    out.append(f"| 成約合計金額 | ¥{total_won:,.0f} |")
    out.append(f"| 平均成約額 | ¥{avg_won:,.0f} |")
    out.append(f"| 失注数 | {lost_count}件（¥{total_lost:,.0f}） |")
    out.append(f"| 進行中（オープン） | {open_count}件（¥{total_open:,.0f}） |")
    out.append(f"| パイプライン総額 | ¥{total_amount:,.0f} |")
    out.append(f"| 成約率 | {win_rate:.1f}%（{won_count}/{decided}件） |")
    out.append(f"| 平均リードタイム | {avg_lead:.1f}日 |")
    out.append("")

    # 月別推移（この四半期内の月のみ）
    months = sorted(set(
        list(results["monthly_pipeline"].keys())
        + list(results["monthly_won"].keys())
        + list(results["monthly_lost"].keys())
    ))
    if months:
        out.append("### 月別推移（納品日ベース）")
        out.append("")
        out.append("| 月 | 取引数 | 総額 | 成約件数 | 成約金額 | 失注件数 | 失注金額 |")
        out.append("|---|---|---|---|---|---|---|")
        for month in months:
            pl = results["monthly_pipeline"].get(month, {"count": 0, "amount": 0})
            wo = results["monthly_won"].get(month, {"count": 0, "amount": 0})
            lo = results["monthly_lost"].get(month, {"count": 0, "amount": 0})
            out.append(
                f"| {month} | {pl['count']}件 | ¥{pl['amount']:,.0f}"
                f" | {wo['count']}件 | ¥{wo['amount']:,.0f}"
                f" | {lo['count']}件 | ¥{lo['amount']:,.0f} |"
            )
        out.append("")

    # 成約案件トップ5
    if results["won"]:
        out.append("### 成約案件（金額上位5件）")
        out.append("")
        out.append("| 案件名 | 金額 | リードタイム |")
        out.append("|---|---|---|")
        for d in sorted(results["won"], key=lambda d: d["amount"], reverse=True)[:5]:
            lt = f"{d.get('lead_time', '-')}日" if d.get("lead_time") is not None else "-"
            out.append(f"| {d['name']} | ¥{d['amount']:,.0f} | {lt} |")
        out.append("")

    # 失注案件トップ5
    if results["lost"]:
        out.append("### 失注案件（金額上位5件）")
        out.append("")
        out.append("| 案件名 | 金額 | リードタイム |")
        out.append("|---|---|---|")
        for d in sorted(results["lost"], key=lambda d: d["amount"], reverse=True)[:5]:
            lt = f"{d.get('lead_time', '-')}日" if d.get("lead_time") is not None else "-"
            out.append(f"| {d['name']} | ¥{d['amount']:,.0f} | {lt} |")
        out.append("")

    # 業界別
    if results["industries"]:
        out.append("### 業界別")
        out.append("")
        out.append("| 業界 | 取引数 | 成約 | 失注 | 進行中 | 成約率 | 成約金額 |")
        out.append("|---|---|---|---|---|---|---|")
        sorted_ind = sorted(
            results["industries"].items(),
            key=lambda x: x[1]["amount_won"],
            reverse=True,
        )
        for industry, data in sorted_ind:
            decided_ind = data["won"] + data["lost"]
            rate = (data["won"] / decided_ind * 100) if decided_ind > 0 else 0
            open_ind = data["total"] - data["won"] - data["lost"]
            out.append(
                f"| {industry} | {data['total']}件 | {data['won']}件"
                f" | {data['lost']}件 | {open_ind}件"
                f" | {rate:.0f}% | ¥{data['amount_won']:,.0f} |"
            )
        out.append("")

    return out


def _render_future_quarter(label, start, end, pipeline):
    """未来四半期のセクション（予定パイプラインのみ）"""
    out = []
    out.append("---")
    out.append("")
    out.append(f"## {label} ({start.strftime('%Y/%m/%d')} 〜 {end.strftime('%Y/%m/%d')}) — 予定パイプライン")
    out.append("")
    out.append(f"**該当期間に成約予定のオープン案件: {pipeline['count']}件 / 合計 ¥{pipeline['amount']:,.0f}**")
    out.append("")

    if pipeline["deals"]:
        out.append("| 案件名 | 会社 | 金額 | 納品予定日 | ステージ |")
        out.append("|---|---|---|---|---|")
        for d in sorted(pipeline["deals"], key=lambda x: x["amount"], reverse=True):
            delivery_short = "-"
            if d.get("delivery_date"):
                try:
                    delivery_short = datetime.fromisoformat(
                        d["delivery_date"].replace("Z", "+00:00")
                    ).strftime("%Y/%m/%d")
                except (ValueError, TypeError):
                    delivery_short = d["delivery_date"]
            out.append(
                f"| {d['name']} | {d['company']} | ¥{d['amount']:,.0f}"
                f" | {delivery_short} | {d['stage']} |"
            )
        out.append("")
    else:
        out.append("（該当案件なし）")
        out.append("")

    return out


def generate_quarterly_report(per_quarter, overall_results, owner_name):
    """会計四半期別の統合レポートを生成"""
    now = datetime.now()
    lines = []

    def add(text=""):
        lines.append(text)

    add("# HubSpot 営業実績分析レポート（四半期別・納品日ベース）")
    add()
    add("## 概要")
    add()
    add(f"- **対象**: {owner_name}")
    add(f"- **期間**: {FISCAL_RANGE_START.strftime('%Y/%m/%d')} 〜 {FISCAL_RANGE_END.strftime('%Y/%m/%d')}")
    add(f"- **基準日**: 納品日（HubSpotカスタムプロパティ `started_day`、未設定時は closedate にフォールバック）")
    add(f"- **生成日**: {now.strftime('%Y/%m/%d %H:%M')}")
    add()

    # ================================
    # 四半期サマリー表
    # ================================
    add("---")
    add()
    add("## 四半期サマリー")
    add()
    add("| 四半期 | 状態 | 取引数 | 成約数 | 成約金額 | 失注数 | 失注金額 | パイプライン数 | パイプライン金額 | 成約率 | 平均LT |")
    add("|---|---|---|---|---|---|---|---|---|---|---|")
    for entry in per_quarter:
        label = entry["label"]
        if entry["kind"] == "future":
            add(_future_summary_row(label, entry["pipeline"]))
        else:
            status_label = "期中" if entry["kind"] == "current" else "完了"
            add(_quarter_summary_row(label, status_label, entry["results"]))
    add()
    add(
        "*注: 取引は **納品日(started_day)** が当該四半期内のものを計上しています"
        "（納品日未設定時は closedate にフォールバック）。"
        "未来四半期は 納品予定日が該当期間のオープン案件のみ表示しています。*"
    )
    add()

    # ================================
    # 四半期別詳細
    # ================================
    for entry in per_quarter:
        if entry["kind"] == "future":
            lines.extend(_render_future_quarter(
                entry["label"], entry["start"], entry["end"], entry["pipeline"]
            ))
        else:
            lines.extend(_render_quarter_detail(
                entry["label"], entry["start"], entry["end"], entry["results"]
            ))

    # ================================
    # 全期間サマリー
    # ================================
    won_count = len(overall_results["won"])
    lost_count = len(overall_results["lost"])
    open_count = len(overall_results["open"])
    decided = won_count + lost_count
    win_rate = (won_count / decided * 100) if decided > 0 else 0
    avg_lead = (
        sum(overall_results["lead_times"]) / len(overall_results["lead_times"])
        if overall_results["lead_times"] else 0
    )
    total_won = sum(overall_results["won_amounts"])
    total_lost = sum(overall_results["lost_amounts"])
    total_open = sum(overall_results["open_amounts"])
    total_amount = sum(overall_results["amounts"])

    add("---")
    add()
    add(f"## 全期間サマリー ({FISCAL_RANGE_START.strftime('%Y/%m/%d')} 〜 {FISCAL_RANGE_END.strftime('%Y/%m/%d')})")
    add()
    add("| 指標 | 値 |")
    add("|---|---|")
    add(f"| 取引総数 | {overall_results['total']}件 |")
    add(f"| 成約数 | {won_count}件 |")
    add(f"| 成約合計金額 | ¥{total_won:,.0f} |")
    add(f"| 失注数 | {lost_count}件（¥{total_lost:,.0f}） |")
    add(f"| 進行中（オープン） | {open_count}件（¥{total_open:,.0f}） |")
    add(f"| パイプライン総額 | ¥{total_amount:,.0f} |")
    add(f"| 成約率 | {win_rate:.1f}%（{won_count}/{decided}件） |")
    add(f"| 平均リードタイム | {avg_lead:.1f}日 |")
    add()

    add("---")
    add(f"*レポート生成: {now.strftime('%Y/%m/%d %H:%M')}*")

    return "\n".join(lines)


def main():
    args = parse_args()

    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        print("エラー: HUBSPOT_API_KEY が設定されていません。")
        print(".env ファイルにトークンを設定してください。")
        sys.exit(1)

    print("HubSpot に接続中...")
    client = HubSpot(access_token=api_key)

    owner_id, owner_name = find_owner(client, args.owner)

    if args.fiscal_quarters:
        start_date = FISCAL_RANGE_START
        end_date = FISCAL_RANGE_END
        print(
            f"四半期別モード: {start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%Y/%m/%d')}"
            f"（{len(FISCAL_QUARTERS)}四半期）"
        )
    else:
        start_date, end_date = get_date_range(args.period)
        if start_date:
            print(f"期間: {start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}")
        else:
            print("期間: 全期間")

    print("パイプライン情報を取得中...")
    stage_map, pipeline_map = fetch_pipeline_stages(client)

    type_label = f"、取引タイプ: {args.deal_type}" if args.deal_type else ""
    print(f"取引データを取得中...（フィルタ: {args.date_field}{type_label}）")
    deals = fetch_deals(
        client, owner_id, start_date, end_date,
        date_field=args.date_field,
        deal_type=args.deal_type,
    )

    if not deals:
        print("取引が見つかりませんでした。")
        sys.exit(0)

    # --list-companies モード: 取引名から会社名を抽出して一覧表示
    if args.list_companies:
        companies = set()
        for deal in deals:
            name = extract_company_from_dealname(deal.properties.get("dealname", ""))
            if name and name != "不明":
                companies.add(name)
        print(f"\n=== 取引名から抽出した会社名一覧 ({len(companies)}社) ===")
        for c in sorted(companies):
            industry = get_industry_for_company(c)
            mark = "" if industry != "不明" else " [要リサーチ]"
            print(f"  {c}{mark}")
        sys.exit(0)

    deal_ids = [d.id for d in deals]

    print("関連会社データを取得中...")
    deal_companies = fetch_associated_companies(client, deal_ids)

    # 会社データが取れなかった場合、取引名から会社名を抽出してフォールバック
    if not deal_companies:
        print("  → 関連会社が0件のため、取引名から会社名を抽出します...")

    if args.skip_activities:
        print("アクティビティ取得をスキップ（--skip-activities）")
        deal_activities = {did: {"notes": 0, "emails": 0, "calls": 0, "meetings": 0, "tasks": 0} for did in deal_ids}
    else:
        print("アクティビティデータを取得中...")
        deal_activities = fetch_deal_activities(client, deal_ids)

    print("データを分析中...")
    monthly_date_field = "started_day" if args.fiscal_quarters else "closedate"
    analysis = analyze_data(
        deals, stage_map, deal_companies, deal_activities,
        monthly_date_field=monthly_date_field,
    )

    if args.fiscal_quarters:
        print("四半期別レポートを生成中(納品日ベース)...")
        now = datetime.now()
        per_quarter = []
        for label, q_start, q_end in FISCAL_QUARTERS:
            if q_start > now:
                pipeline = pipeline_in_quarter(deals, stage_map, deal_companies, q_start, q_end)
                per_quarter.append({
                    "label": label,
                    "kind": "future",
                    "start": q_start,
                    "end": q_end,
                    "pipeline": pipeline,
                })
                print(f"  {label}: 未来四半期 — 予定パイプライン {pipeline['count']}件 / ¥{pipeline['amount']:,.0f}")
            else:
                subset = filter_deals_for_quarter(deals, q_start, q_end)
                q_results = analyze_data(
                    subset, stage_map, deal_companies, deal_activities,
                    monthly_date_field="started_day",
                )
                kind = "current" if q_end >= now else "past"
                per_quarter.append({
                    "label": label,
                    "kind": kind,
                    "start": q_start,
                    "end": q_end,
                    "results": q_results,
                })
                print(f"  {label}: {len(subset)}件を分析")

        report = generate_quarterly_report(per_quarter, analysis, owner_name)
        default_name = f"reports/sales_report_FY25Q4-FY26Q4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    else:
        print("レポートを生成中...")
        report = generate_report(analysis, owner_name, args.period, start_date, end_date)
        default_name = f"reports/sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    output_path = args.output or default_name
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nレポートを保存しました: {output_path}")
    print("完了!")


if __name__ == "__main__":
    main()
