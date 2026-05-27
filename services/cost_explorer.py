from datetime import datetime, timedelta
from services.aws_session import AwsSession


class CostExplorerService:
    def __init__(self, session: AwsSession):
        self.client = session.get_client("ce")

    def get_monthly_cost_by_service(self, months: int = 3):
        end = datetime.now()
        start = end - timedelta(days=30 * months)

        resp = self.client.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End": end.strftime("%Y-%m-%d"),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        services = {}
        for result in resp.get("ResultsByTime", []):
            period = result["TimePeriod"]["Start"]
            for group in result.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if service not in services:
                    services[service] = {}
                services[service][period] = services[service].get(period, 0) + amount

        return services

    def get_total_cost(self, months: int = 3):
        end = datetime.now()
        start = end - timedelta(days=30 * months)

        resp = self.client.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End": end.strftime("%Y-%m-%d"),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )

        totals = {}
        for result in resp.get("ResultsByTime", []):
            period = result["TimePeriod"]["Start"]
            amount = float(result["Total"]["UnblendedCost"]["Amount"])
            totals[period] = amount
        return totals
