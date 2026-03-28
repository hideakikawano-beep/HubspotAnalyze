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


def get_industry_for_company(company_name):
    """会社名から業界を取得（マッピングから検索）"""
    for key, industry in COMPANY_INDUSTRY_MAP.items():
        if key.lower() in company_name.lower() or company_name.lower() in key.lower():
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


def fetch_deals(client, owner_id, start_date, end_date):
    """取引を検索して取得"""
    filters = [
        Filter(property_name="hubspot_owner_id", operator="EQ", value=owner_id)
    ]

    if start_date:
        filters.append(
            Filter(
                property_name="createdate",
                operator="GTE",
                value=str(int(start_date.timestamp() * 1000)),
            )
        )
    if end_date:
        filters.append(
            Filter(
                property_name="createdate",
                operator="LTE",
                value=str(int(end_date.timestamp() * 1000)),
            )
        )

    all_deals = []
    after = None

    while True:
        search_request = PublicObjectSearchRequest(
            filter_groups=[FilterGroup(filters=filters)],
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

    print(f"取引数: {len(all_deals)}件を取得")
    return all_deals


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
    """取引に関連するアクティビティ数を取得"""
    deal_activities = {}
    activity_object_types = ["notes", "emails", "calls", "meetings", "tasks"]
    total = len(deal_ids)

    for i, deal_id in enumerate(deal_ids):
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


def analyze_data(deals, stage_map, deal_companies, deal_activities):
    """データを分析してレポート用の構造化データを返す"""
    results = {
        "total": len(deals),
        "won": [],
        "lost": [],
        "open": [],
        "amounts": [],
        "won_amounts": [],
        "lead_times": [],
        "industries": defaultdict(lambda: {"total": 0, "won": 0, "lost": 0, "amount": 0}),
        "won_reasons": Counter(),
        "lost_reasons": Counter(),
        "monthly_pipeline": defaultdict(lambda: {"count": 0, "amount": 0}),
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

        # 月別パイプライン
        create_str = props.get("createdate")
        if create_str:
            try:
                create_dt = datetime.fromisoformat(create_str.replace("Z", "+00:00"))
                month_key = create_dt.strftime("%Y-%m")
                results["monthly_pipeline"][month_key]["count"] += 1
                results["monthly_pipeline"][month_key]["amount"] += amount
            except (ValueError, TypeError):
                pass

        # リードタイム計算
        lead_time_days = None
        close_str = props.get("closedate")
        if create_str and close_str:
            try:
                create_dt = datetime.fromisoformat(create_str.replace("Z", "+00:00"))
                close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
                lead_time_days = (close_dt - create_dt).days
                if lead_time_days >= 0:
                    deal_data["lead_time"] = lead_time_days
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
            reason = props.get("closed_lost_reason") or "理由未記載"
            results["lost_reasons"][reason] += 1
        else:
            results["open"].append(deal_data)

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
                results["industries"][industry]["amount"] += amount
                if status == "won":
                    results["industries"][industry]["won"] += 1
                elif status == "lost":
                    results["industries"][industry]["lost"] += 1
        else:
            # フォールバック: 取引名から会社名を抽出して業界を推定
            company_name = extract_company_from_dealname(props.get("dealname", ""))
            industry = get_industry_for_company(company_name)
            results["industries"][industry]["total"] += 1
            results["industries"][industry]["amount"] += amount
            if status == "won":
                results["industries"][industry]["won"] += 1
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

    # 1. 取引サマリー
    add("---")
    add()
    add("## 1. 取引サマリー")
    add()

    won_count = len(results["won"])
    lost_count = len(results["lost"])
    open_count = len(results["open"])
    decided = won_count + lost_count
    win_rate = (won_count / decided * 100) if decided > 0 else 0
    avg_won = (sum(results["won_amounts"]) / won_count) if won_count > 0 else 0
    avg_lead = (sum(results["lead_times"]) / len(results["lead_times"])) if results["lead_times"] else 0
    total_won_amount = sum(results["won_amounts"])
    total_amount = sum(results["amounts"])

    add("| 指標 | 値 |")
    add("|---|---|")
    add(f"| 総取引数 | {results['total']}件 |")
    add(f"| 成約数 | {won_count}件 |")
    add(f"| 失注数 | {lost_count}件 |")
    add(f"| 進行中 | {open_count}件 |")
    add(f"| 成約率 | {win_rate:.1f}% |")
    add(f"| 成約合計金額 | ¥{total_won_amount:,.0f} |")
    add(f"| 平均成約額 | ¥{avg_won:,.0f} |")
    add(f"| 平均リードタイム（成約） | {avg_lead:.1f}日 |")
    add(f"| パイプライン総額 | ¥{total_amount:,.0f} |")
    add()

    # 2. アクティビティ分析
    add("---")
    add()
    add("## 2. 成約までのアクティビティ分析")
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

    if results["won"]:
        add("### 成約案件のアクティビティ詳細（上位5件）")
        add()
        add("| 案件名 | 金額 | リードタイム | アクティビティ数 |")
        add("|---|---|---|---|")
        sorted_won = sorted(results["won"], key=lambda d: d["amount"], reverse=True)[:5]
        for d in sorted_won:
            lt = f"{d.get('lead_time', '-')}日" if d.get("lead_time") is not None else "-"
            add(f"| {d['name']} | ¥{d['amount']:,.0f} | {lt} | {d['total_activities']}件 |")
        add()

    # 3. 取引金額分析
    add("---")
    add()
    add("## 3. 取引金額分析")
    add()

    non_zero = [a for a in results["amounts"] if a > 0]
    if non_zero:
        add("### 金額帯別の取引分布")
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
            count = len([a for a in non_zero if low <= a < high])
            if count > 0:
                add(f"| {label} | {count}件 |")
        add()

    if results["monthly_pipeline"]:
        add("### 月別の取引金額推移")
        add()
        add("| 月 | 新規件数 | 新規金額 |")
        add("|---|---|---|")
        for month in sorted(results["monthly_pipeline"].keys()):
            data = results["monthly_pipeline"][month]
            add(f"| {month} | {data['count']}件 | ¥{data['amount']:,.0f} |")
        add()

    # 4. 業界別分析
    add("---")
    add()
    add("## 4. 業界・業種別分析")
    add()

    if results["industries"]:
        add("| 業界 | 取引数 | 成約数 | 失注数 | 成約率 | 合計金額 |")
        add("|---|---|---|---|---|---|")
        sorted_industries = sorted(
            results["industries"].items(),
            key=lambda x: x[1]["amount"],
            reverse=True,
        )
        for industry, data in sorted_industries:
            decided_ind = data["won"] + data["lost"]
            rate = (data["won"] / decided_ind * 100) if decided_ind > 0 else 0
            add(
                f"| {industry} | {data['total']}件 | {data['won']}件 | {data['lost']}件 | {rate:.0f}% | ¥{data['amount']:,.0f} |"
            )
        add()
    else:
        add("（関連する会社データがありません）")
        add()

    # 5. 成約/失注理由分析
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

    # 6. パイプライン推移
    add("---")
    add()
    add("## 6. パイプライン推移")
    add()

    if results["monthly_pipeline"]:
        add("| 月 | 新規パイプライン数 | 新規パイプライン金額 | 累積件数 | 累積金額 |")
        add("|---|---|---|---|---|")
        cumulative_count = 0
        cumulative_amount = 0
        for month in sorted(results["monthly_pipeline"].keys()):
            data = results["monthly_pipeline"][month]
            cumulative_count += data["count"]
            cumulative_amount += data["amount"]
            add(
                f"| {month} | {data['count']}件 | ¥{data['amount']:,.0f} | {cumulative_count}件 | ¥{cumulative_amount:,.0f} |"
            )
        add()
    else:
        add("（データなし）")
        add()

    # 7. ハイライト
    add("---")
    add()
    add("## 7. ハイライト")
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
    add()

    # 8. ローライト
    add("---")
    add()
    add("## 8. ローライト")
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

    start_date, end_date = get_date_range(args.period)
    if start_date:
        print(f"期間: {start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}")
    else:
        print("期間: 全期間")

    print("パイプライン情報を取得中...")
    stage_map, pipeline_map = fetch_pipeline_stages(client)

    print("取引データを取得中...")
    deals = fetch_deals(client, owner_id, start_date, end_date)

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

    print("アクティビティデータを取得中...")
    deal_activities = fetch_deal_activities(client, deal_ids)

    print("データを分析中...")
    analysis = analyze_data(deals, stage_map, deal_companies, deal_activities)

    print("レポートを生成中...")
    report = generate_report(analysis, owner_name, args.period, start_date, end_date)

    output_path = args.output or f"reports/sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nレポートを保存しました: {output_path}")
    print("完了!")


if __name__ == "__main__":
    main()
