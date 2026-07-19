from diagrams import Diagram, Edge
from diagrams.aws.compute import EC2
from diagrams.aws.storage import S3
from diagrams.aws.network import ELB
from diagrams.aws.database import ElastiCache
from diagrams.onprem.workflow import Airflow
from diagrams.onprem.queue import RabbitMQ
from diagrams.onprem.database import PostgreSQL
from diagrams.programming.language import Python
from diagrams.custom import Custom

# Use custom icons or standard ones
with Diagram(
    "Smart City Traffic Intelligence — Horizontal Scaling Architecture",
    show=False,
    direction="LR",
    filename="smart_city_architecture",
    outformat="png",
):
    # ========================================================
    #  PANEL 1: ARCHITECTURE (Left)
    # ========================================================
    with Diagram("Current Architecture (1 Worker)", direction="LR"):
        user = EC2("Operator Requests")  # representing user
        app = EC2("FastAPI (1 Worker)")

        # Core components
        with Diagram("Application Core", direction="TB"):
            predict = Python("Predict (XGBoost+GNN)")
            shap = Python("SHAP Explain")
            log = S3("CSV Log Write")

        # External adapters
        weather = EC2("Weather API")
        osm = EC2("OSM Adapter")
        mock = EC2("Mock IoT")

        user >> app >> predict >> shap >> log
        app >> weather
        app >> osm
        app >> mock

    # ========================================================
    #  PANEL 2: BOTTLENECK (Center)
    # ========================================================
    with Diagram("Bottleneck: Single-Threaded Queue", direction="TB"):
        queue = RabbitMQ("100+ Requests\nQueued")
        worker = EC2("1 Uvicorn Worker")
        slow = S3("Synchronous CSV")
        time = Custom("p95: 230s", icon_path="icon_clock.png")

        queue >> worker >> slow >> time

    # ========================================================
    #  PANEL 3: SOLUTION (Right)
    # ========================================================
    with Diagram("Scaled Solution (4 Workers + Redis)", direction="LR"):
        lb = ELB("Load Balancer")
        cache = ElastiCache("Redis Cache\n(TTL 30-60s)")
        workers = [EC2("Worker 1"), EC2("Worker 2"), EC2("Worker 3"), EC2("Worker 4")]
        async_log = RabbitMQ("Async Log Queue\n(TelemetryQueue)")
        csv = S3("CSV Logs (with Lock)")

        lb >> cache
        cache >> workers
        for w in workers:
            w >> async_log
        async_log >> csv

    # Connect the three panels with an arrow to show progression
    # (The diagram will stack them left-to-right automatically)