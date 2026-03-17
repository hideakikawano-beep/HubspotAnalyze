#!/usr/bin/env python3
"""HubSpot 営業実績分析ツール - Hideaki Kawano向け営業データ分析スクリプト"""

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from dotenv import load_dotenv
from hubspot import HubSpot
from hubspot.crm.deals import (
    Filter,
    FilterGroup,
    PublicObjectSearchRequest,
)

load_dotenv()

# --- 定数 ---
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
    "hs_analytics_source",
]

COMPANY_PROPERTIES = [
    "name",
    "industry",
    "type",
    "domain",
]

ASSOCIATION_TYPES = {
    "notes": "notes",
    "emails": "emails",
    "calls": "calls",
    "meetings": "meetings",
    "tasks": "tasks",
}


# --- 期間パース ---
def parse_period(period_str: str) -> tuple[datetime | None, datetime | None]:
    """期間文字列をパースして(start, end)のdatetimeタプルを返す"""
    now = datetime.now()

    if period_str == "all":
        return None, None
    elif period_str == "1y":
        return now - timedelta(days=365), now
    elif period_str == "6m":
        return now - timedelta(days=182), now
    elif period_str == "quarter":
        # 現在の四半期の開始日
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start = datetime(now.year, quarter_month, 1)
        return start, now
    elif ":" in period_str:
        parts = period_str.split(":")
        start = datetime.strptime(parts[0], "%Y-%m-%d")
        end = datetime.strptime(parts[1], "%Y-%m-%d")
        return start, end
    else:
        print(f"不正な期間指定: {period_str}")
        print("有効な値: all, 1y, 6m, quarter, YYYY-MM-DD:YYYY-MM-DD")
        sys.exit(1)


# --- HubSpot API クライアント ---
class HubSpotAnalyzer:
    def __init__(self, api_key: str):
        self.client = HubSpot(access_token=api_key)
        self._pipeline_stages = {}

    def find_owner(self, owner_name: str) -> str | None:
        """オーナー名からIDを検索（部分一致）"""
        owners = self.client.crm.owners.get_page()
        for owner in owners.results:
            full_name = f"{owner.first_name} {owner.last_name}".strip()
            if owner_name.lower() in full_name.lower():
                print(f"  オーナー検出: {full_name} (ID: {owner.id})")
                return owner.id
        return None

    def get_pipeline_stages(self) -> dict[str, str]:
        """パイプラインのステージIDと名前のマッピングを取得"""
        if self._pipeline_stages:
            return self._pipeline_stages

        pipelines = self.client.crm.pipelines.get_all("deals")
        for pipeline in pipelines.results:
            for stage in pipeline.stages:
                self._pipeline_stages[stage.id] = stage.label
        return self._pipeline_stages

    def get_deals(
        self,
        owner_id: str,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[dict]:
        """オーナーと期間でフィルタした取引を取得"""
        filters = [
            Filter(
                property_name="hubspot_owner_id",
                operator="EQ",
                value=owner_id,
            )
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

        filter_group = FilterGroup(filters=filters)
        search_request = PublicObjectSearchRequest(
            filter_groups=[filter_group],
            properties=DEAL_PROPERTIES,
            limit=100,
        )

        all_deals = []
        after = None

        while True:
            if after:
                search_request.after = after

            response = self.client.crm.deals.search_api.do_search(
                public_object_search_request=search_request,
            )

            for deal in response.results:
                all_deals.append(
                    {
                        "id": deal.id,
                        "name": deal.properties.get("dealname", ""),
                        "amount": _parse_float(deal.properties.get("amount")),
                        "stage": deal.properties.get("dealstage", ""),
                        "pipeline": deal.properties.get("pipeline", ""),
                        "createdate": _parse_date(
                            deal.properties.get("createdate")
                        ),
                        "closedate": _parse_date(
                            deal.properties.get("closedate")
                        ),
                        "closed_won_date": _parse_date(
                            deal.properties.get("hs_closed_won_date")
                        ),
                        "closed_lost_reason": deal.properties.get(
                            "closed_lost_reason", ""
                        ),
                        "closed_won_reason": deal.properties.get(
                            "closed_won_reason", ""
                        ),
                        "source": deal.properties.get(
                            "hs_analytics_source", ""
                        ),
                    }
                )

            if response.paging and response.paging.next:
                after = response.paging.next.after
            else:
                break

        print(f"  取引数: {len(all_deals)}件取得")
        return all_deals

    def get_deal_companies(self, deal_id: str) -> list[dict]:
        """取引に紐づく会社情報を取得"""
        try:
            associations = (
                self.client.crm.deals.associations_api.get_all(
                    deal_id=deal_id,
                    to_object_type="companies",
                )
            )
            companies = []
            for assoc in associations.results:
                company = self.client.crm.companies.basic_api.get_by_id(
                    company_id=assoc.to_object_id,
                    properties=COMPANY_PROPERTIES,
                )
                companies.append(
                    {
                        "name": company.properties.get("name", ""),
                        "industry": company.properties.get("industry", ""),
                        "type": company.properties.get("type", ""),
                    }
                )
            return companies
        except Exception:
            return []

    def get_deal_activities(self, deal_id: str) -> dict[str, int]:
        """取引に紐づくアクティビティ数を種別ごとに取得"""
        activity_counts = {}
        for activity_type, obj_type in ASSOCIATION_TYPES.items():
            try:
                associations = (
                    self.client.crm.deals.associations_api.get_all(
                        deal_id=deal_id,
                        to_object_type=obj_type,
                    )
                )
                activity_counts[activity_type] = len(associations.results)
            except Exception:
                activity_counts[activity_type] = 0
        return activity_counts


# --- ユーティリティ ---
def _parse_float(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _parse_date(value) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        # HubSpot returns ISO format or milliseconds
        if isinstance(value, str) and "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        return datetime.fromtimestamp(int(value) / 1000)
    except (ValueError, TypeError):
        return None


def classify_deal(stage: str, stages: dict[str, str]) -> str:
    """取引ステージをwon/lost/openに分類"""
    stage_name = stages.get(stage, stage).lower()
    if "won" in stage_name or "成約" in stage_name or "受注" in stage_name:
        return "won"
    elif (
        "lost" in stage_name
        or "失注" in stage_name
        or "closed lost" in stage_name
    ):
        return "lost"
    return "open"


# --- 分析ロジック ---
def analyze_deals(
    analyzer: HubSpotAnalyzer,
    deals: list[dict],
    stages: dict[str, str],
) -> dict:
    """取引データを分析"""
    results = {
        "total": len(deals),
        "won": [],
        "lost": [],
        "open": [],
        "activities": {},
        "companies": {},
        "monthly_pipeline": defaultdict(lambda: {"count": 0, "amount": 0.0}),
    }

    for i, deal in enumerate(deals):
        status = classify_deal(deal["stage"], stages)
        results[status].append(deal)

        # 月別パイプライン
        if deal["createdate"]:
            month_key = deal["createdate"].strftime("%Y-%m")
            results["monthly_pipeline"][month_key]["count"] += 1
            results["monthly_pipeline"][month_key]["amount"] += deal["amount"]

        # アクティビティ取得（成約・失注の取引のみ、API呼び出し節約）
        if status in ("won", "lost"):
            print(
                f"  アクティビティ取得中... ({i + 1}/{len(deals)}) {deal['name']}",
                end="\r",
            )
            results["activities"][deal["id"]] = analyzer.get_deal_activities(
                deal["id"]
            )

            # 会社情報取得
            companies = analyzer.get_deal_companies(deal["id"])
            if companies:
                results["companies"][deal["id"]] = companies

    print()  # 改行
    return results


# --- レポート生成 ---
def generate_report(
    owner_name: str,
    period_str: str,
    start_date: datetime | None,
    end_date: datetime | None,
    deals: list[dict],
    analysis: dict,
    stages: dict[str, str],
) -> str:
    """Markdownレポートを生成"""
    lines = []

    # ヘッダー
    lines.append("# HubSpot 営業実績分析レポート")
    lines.append("")
    lines.append("## 分析概要")
    lines.append("")
    lines.append(f"- **対象者**: {owner_name}")
    period_display = _format_period(period_str, start_date, end_date)
    lines.append(f"- **分析期間**: {period_display}")
    lines.append(
        f"- **レポート生成日**: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )
    lines.append("")

    won = analysis["won"]
    lost = analysis["lost"]
    open_deals = analysis["open"]

    # --- 1. 取引サマリー ---
    lines.append("---")
    lines.append("")
    lines.append("## 1. 取引サマリー")
    lines.append("")

    total = analysis["total"]
    won_count = len(won)
    lost_count = len(lost)
    open_count = len(open_deals)
    closed_count = won_count + lost_count
    win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0

    won_amounts = [d["amount"] for d in won if d["amount"] > 0]
    avg_won_amount = sum(won_amounts) / len(won_amounts) if won_amounts else 0
    total_won_amount = sum(won_amounts)

    # リードタイム計算
    lead_times = []
    for d in won:
        close = d["closed_won_date"] or d["closedate"]
        if close and d["createdate"]:
            lt = (close - d["createdate"]).days
            if lt >= 0:
                lead_times.append(lt)
    avg_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0

    lines.append("| 指標 | 値 |")
    lines.append("|---|---|")
    lines.append(f"| 総取引数 | {total}件 |")
    lines.append(f"| 成約数 | {won_count}件 |")
    lines.append(f"| 失注数 | {lost_count}件 |")
    lines.append(f"| 進行中 | {open_count}件 |")
    lines.append(f"| 成約率（クローズ済み） | {win_rate:.1f}% |")
    lines.append(f"| 成約総額 | ¥{total_won_amount:,.0f} |")
    lines.append(f"| 平均成約額 | ¥{avg_won_amount:,.0f} |")
    lines.append(f"| 平均リードタイム（成約） | {avg_lead_time:.0f}日 |")
    lines.append("")

    # --- 2. アクティビティ分析 ---
    lines.append("---")
    lines.append("")
    lines.append("## 2. 成約までのアクティビティ分析")
    lines.append("")

    activities = analysis["activities"]
    if activities:
        # 成約案件のアクティビティ
        won_activities = {
            did: acts
            for did, acts in activities.items()
            if did in [d["id"] for d in won]
        }
        lost_activities = {
            did: acts
            for did, acts in activities.items()
            if did in [d["id"] for d in lost]
        }

        if won_activities:
            lines.append("### 成約案件のアクティビティ")
            lines.append("")
            total_by_type = Counter()
            total_per_deal = []
            for acts in won_activities.values():
                deal_total = sum(acts.values())
                total_per_deal.append(deal_total)
                for atype, count in acts.items():
                    total_by_type[atype] += count

            avg_total = (
                sum(total_per_deal) / len(total_per_deal)
                if total_per_deal
                else 0
            )
            lines.append(
                f"- **平均アクティビティ数（成約1件あたり）**: {avg_total:.1f}件"
            )
            lines.append("")
            lines.append("| アクティビティ種別 | 合計数 | 平均（1件あたり） |")
            lines.append("|---|---|---|")
            type_labels = {
                "notes": "メモ",
                "emails": "メール",
                "calls": "電話",
                "meetings": "ミーティング",
                "tasks": "タスク",
            }
            for atype, label in type_labels.items():
                total_c = total_by_type.get(atype, 0)
                avg_c = total_c / len(won_activities) if won_activities else 0
                lines.append(f"| {label} | {total_c} | {avg_c:.1f} |")
            lines.append("")

        if lost_activities:
            lines.append("### 失注案件のアクティビティ")
            lines.append("")
            total_by_type = Counter()
            total_per_deal = []
            for acts in lost_activities.values():
                deal_total = sum(acts.values())
                total_per_deal.append(deal_total)
                for atype, count in acts.items():
                    total_by_type[atype] += count

            avg_total = (
                sum(total_per_deal) / len(total_per_deal)
                if total_per_deal
                else 0
            )
            lines.append(
                f"- **平均アクティビティ数（失注1件あたり）**: {avg_total:.1f}件"
            )
            lines.append("")
            lines.append("| アクティビティ種別 | 合計数 | 平均（1件あたり） |")
            lines.append("|---|---|---|")
            for atype, label in type_labels.items():
                total_c = total_by_type.get(atype, 0)
                avg_c = total_c / len(lost_activities) if lost_activities else 0
                lines.append(f"| {label} | {total_c} | {avg_c:.1f} |")
            lines.append("")
    else:
        lines.append("アクティビティデータがありません。")
        lines.append("")

    # --- 3. 取引金額分析 ---
    lines.append("---")
    lines.append("")
    lines.append("## 3. 取引金額分析")
    lines.append("")

    all_amounts = [d["amount"] for d in deals if d["amount"] > 0]
    if all_amounts:
        # 金額帯分布
        brackets = [
            (0, 100000, "~10万"),
            (100000, 500000, "10万~50万"),
            (500000, 1000000, "50万~100万"),
            (1000000, 5000000, "100万~500万"),
            (5000000, 10000000, "500万~1000万"),
            (10000000, float("inf"), "1000万~"),
        ]

        lines.append("### 金額帯別分布")
        lines.append("")
        lines.append("| 金額帯 | 取引数 | 割合 |")
        lines.append("|---|---|---|")
        for low, high, label in brackets:
            count = sum(1 for a in all_amounts if low <= a < high)
            if count > 0:
                pct = count / len(all_amounts) * 100
                lines.append(f"| {label} | {count}件 | {pct:.1f}% |")
        lines.append("")

        # 月別推移
        monthly = defaultdict(lambda: {"count": 0, "won_amount": 0.0})
        for d in won:
            close = d["closed_won_date"] or d["closedate"]
            if close:
                mk = close.strftime("%Y-%m")
                monthly[mk]["count"] += 1
                monthly[mk]["won_amount"] += d["amount"]

        if monthly:
            lines.append("### 月別成約推移")
            lines.append("")
            lines.append("| 月 | 成約数 | 成約金額 |")
            lines.append("|---|---|---|")
            for mk in sorted(monthly.keys()):
                m = monthly[mk]
                lines.append(
                    f"| {mk} | {m['count']}件 | ¥{m['won_amount']:,.0f} |"
                )
            lines.append("")
    else:
        lines.append("金額データがありません。")
        lines.append("")

    # --- 4. 業界・業種別分析 ---
    lines.append("---")
    lines.append("")
    lines.append("## 4. 業界・業種別分析")
    lines.append("")

    companies = analysis["companies"]
    if companies:
        industry_stats = defaultdict(
            lambda: {"total": 0, "won": 0, "amount": 0.0}
        )
        won_ids = {d["id"] for d in won}

        for deal_id, comps in companies.items():
            for comp in comps:
                ind = comp.get("industry") or "不明"
                industry_stats[ind]["total"] += 1
                if deal_id in won_ids:
                    industry_stats[ind]["won"] += 1
                    # 対応するDealの金額を取得
                    for d in deals:
                        if d["id"] == deal_id:
                            industry_stats[ind]["amount"] += d["amount"]
                            break

        lines.append("| 業界 | 取引数 | 成約数 | 成約率 | 成約合計金額 |")
        lines.append("|---|---|---|---|---|")
        for ind, stats in sorted(
            industry_stats.items(), key=lambda x: x[1]["amount"], reverse=True
        ):
            wr = (
                stats["won"] / stats["total"] * 100
                if stats["total"] > 0
                else 0
            )
            lines.append(
                f"| {ind} | {stats['total']}件 | {stats['won']}件 "
                f"| {wr:.0f}% | ¥{stats['amount']:,.0f} |"
            )
        lines.append("")
    else:
        lines.append("業界データがありません（会社情報が取引に紐づいていない可能性）。")
        lines.append("")

    # --- 5. 成約/失注理由分析 ---
    lines.append("---")
    lines.append("")
    lines.append("## 5. 成約/失注理由分析")
    lines.append("")

    # 成約理由
    won_reasons = Counter()
    for d in won:
        reason = d.get("closed_won_reason") or "理由未記入"
        won_reasons[reason] += 1

    if won_reasons:
        lines.append("### 成約理由")
        lines.append("")
        lines.append("| 理由 | 件数 | 割合 |")
        lines.append("|---|---|---|")
        for reason, count in won_reasons.most_common():
            pct = count / len(won) * 100 if won else 0
            lines.append(f"| {reason} | {count}件 | {pct:.1f}% |")
        lines.append("")

    # 失注理由
    lost_reasons = Counter()
    for d in lost:
        reason = d.get("closed_lost_reason") or "理由未記入"
        lost_reasons[reason] += 1

    if lost_reasons:
        lines.append("### 失注理由")
        lines.append("")
        lines.append("| 理由 | 件数 | 割合 |")
        lines.append("|---|---|---|")
        for reason, count in lost_reasons.most_common():
            pct = count / len(lost) * 100 if lost else 0
            lines.append(f"| {reason} | {count}件 | {pct:.1f}% |")
        lines.append("")

    if not won_reasons and not lost_reasons:
        lines.append("成約/失注理由のデータがありません。")
        lines.append("")

    # --- 6. パイプライン推移 ---
    lines.append("---")
    lines.append("")
    lines.append("## 6. パイプライン推移")
    lines.append("")

    monthly_pipeline = analysis["monthly_pipeline"]
    if monthly_pipeline:
        lines.append("| 月 | 新規パイプライン数 | 新規パイプライン金額 | 累積金額 |")
        lines.append("|---|---|---|---|")
        cumulative = 0.0
        for mk in sorted(monthly_pipeline.keys()):
            m = monthly_pipeline[mk]
            cumulative += m["amount"]
            lines.append(
                f"| {mk} | {m['count']}件 "
                f"| ¥{m['amount']:,.0f} | ¥{cumulative:,.0f} |"
            )
        lines.append("")
    else:
        lines.append("パイプラインデータがありません。")
        lines.append("")

    # --- 7. ハイライト ---
    lines.append("---")
    lines.append("")
    lines.append("## 7. ハイライト")
    lines.append("")

    if won:
        # 最高額の成約
        top_won = max(won, key=lambda d: d["amount"])
        lines.append(
            f"- **最高額成約**: {top_won['name']} — ¥{top_won['amount']:,.0f}"
        )

        # 最短リードタイム
        if lead_times:
            min_lt = min(lead_times)
            for d in won:
                close = d["closed_won_date"] or d["closedate"]
                if close and d["createdate"]:
                    lt = (close - d["createdate"]).days
                    if lt == min_lt:
                        lines.append(
                            f"- **最短リードタイム成約**: {d['name']} — {lt}日"
                        )
                        break

        # 成約率が高い業界
        if companies:
            best_industry = None
            best_rate = 0
            for ind, stats in industry_stats.items():
                if stats["total"] >= 2:  # 最低2件以上
                    rate = stats["won"] / stats["total"]
                    if rate > best_rate:
                        best_rate = rate
                        best_industry = ind
            if best_industry:
                lines.append(
                    f"- **成約率トップ業界**: {best_industry} "
                    f"— {best_rate * 100:.0f}%"
                )

        # 最高額の月
        if monthly_pipeline:
            best_month = max(
                monthly_pipeline.items(), key=lambda x: x[1]["amount"]
            )
            lines.append(
                f"- **最高パイプライン月**: {best_month[0]} "
                f"— ¥{best_month[1]['amount']:,.0f} "
                f"（{best_month[1]['count']}件）"
            )
    else:
        lines.append("成約データがないためハイライトを表示できません。")
    lines.append("")

    # --- 8. ローライト ---
    lines.append("---")
    lines.append("")
    lines.append("## 8. ローライト")
    lines.append("")

    if lost:
        # 最高額の失注
        top_lost = max(lost, key=lambda d: d["amount"])
        lines.append(
            f"- **最高額失注**: {top_lost['name']} "
            f"— ¥{top_lost['amount']:,.0f}"
        )
        if top_lost.get("closed_lost_reason"):
            lines.append(f"  - 理由: {top_lost['closed_lost_reason']}")

        # 最長リードタイムで失注
        lost_lead_times = []
        for d in lost:
            if d["closedate"] and d["createdate"]:
                lt = (d["closedate"] - d["createdate"]).days
                if lt >= 0:
                    lost_lead_times.append((d, lt))
        if lost_lead_times:
            longest = max(lost_lead_times, key=lambda x: x[1])
            lines.append(
                f"- **最長リードタイム失注**: {longest[0]['name']} — {longest[1]}日"
            )

        # 最も多い失注理由
        if lost_reasons:
            top_reason = lost_reasons.most_common(1)[0]
            lines.append(
                f"- **最多失注理由**: {top_reason[0]} — {top_reason[1]}件"
            )
    else:
        lines.append("失注データがないためローライトを表示できません。")
    lines.append("")

    # --- 改善提案 ---
    lines.append("---")
    lines.append("")
    lines.append("## 9. 次の戦略への提案")
    lines.append("")

    if won and lost:
        lines.append("上記データに基づく示唆:")
        lines.append("")
        if win_rate >= 50:
            lines.append(
                f"- 成約率 {win_rate:.1f}% は良好。"
                "パイプライン拡大で売上増を狙えます"
            )
        else:
            lines.append(
                f"- 成約率 {win_rate:.1f}% に改善余地。"
                "案件の質の向上やフォローアップ強化を検討"
            )

        if avg_lead_time > 90:
            lines.append(
                f"- 平均リードタイム {avg_lead_time:.0f}日は長め。"
                "商談プロセスの短縮を検討"
            )

        if lost_reasons:
            top_lost_reason = lost_reasons.most_common(1)[0]
            lines.append(
                f"- 失注理由トップ「{top_lost_reason[0]}」への対策を優先"
            )
    lines.append("")

    return "\n".join(lines)


def _format_period(
    period_str: str,
    start_date: datetime | None,
    end_date: datetime | None,
) -> str:
    if period_str == "all":
        return "全期間"
    elif start_date and end_date:
        return (
            f"{start_date.strftime('%Y/%m/%d')} - "
            f"{end_date.strftime('%Y/%m/%d')}"
        )
    return period_str


# --- メイン ---
def main():
    parser = argparse.ArgumentParser(
        description="HubSpot 営業実績分析ツール",
    )
    parser.add_argument(
        "--period",
        default="all",
        help="分析期間: all, 1y, 6m, quarter, YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument(
        "--owner",
        default="Hideaki Kawano",
        help="オーナー名（部分一致検索、デフォルト: Hideaki Kawano）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="出力ファイルパス（デフォルト: reports/sales_report_YYYYMMDD.md）",
    )
    args = parser.parse_args()

    # APIキー確認
    api_key = os.environ.get("HUBSPOT_API_KEY")
    if not api_key:
        print("エラー: HUBSPOT_API_KEY が設定されていません。")
        print(".envファイルにPrivate App Tokenを設定してください。")
        print("詳細は README.md を参照してください。")
        sys.exit(1)

    # 期間パース
    start_date, end_date = parse_period(args.period)

    print("=" * 50)
    print("HubSpot 営業実績分析")
    print("=" * 50)

    # HubSpot API接続
    analyzer = HubSpotAnalyzer(api_key)

    # 1. オーナー検索
    print(f"\n[1/5] オーナー検索: {args.owner}")
    owner_id = analyzer.find_owner(args.owner)
    if not owner_id:
        print(f"エラー: オーナー '{args.owner}' が見つかりません。")
        sys.exit(1)

    # 2. パイプラインステージ取得
    print("\n[2/5] パイプライン情報取得中...")
    stages = analyzer.get_pipeline_stages()
    print(f"  {len(stages)}ステージ検出")

    # 3. 取引取得
    print(f"\n[3/5] 取引データ取得中（期間: {args.period}）...")
    deals = analyzer.get_deals(owner_id, start_date, end_date)

    if not deals:
        print("取引データが見つかりません。期間やオーナー名を確認してください。")
        sys.exit(0)

    # 4. 分析
    print("\n[4/5] データ分析中...")
    analysis = analyze_deals(analyzer, deals, stages)

    # 5. レポート生成
    print("\n[5/5] レポート生成中...")
    report = generate_report(
        args.owner,
        args.period,
        start_date,
        end_date,
        deals,
        analysis,
        stages,
    )

    # 出力
    output_path = args.output or os.path.join(
        "reports",
        f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nレポートを出力しました: {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
