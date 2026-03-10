import time
from locust import HttpUser, task, between, events
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize Locust environment"""
    print("🚀 Starting Load Test for ArcGIS Compliance Backend")
    print("📊 Testing API endpoints and Celery performance")
    print("=" * 60)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print(f"🎯 Test started with {environment.runner.user_count} users")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("🏁 Test completed - Check results above")

class ArcGISComplianceUser(HttpUser):
    """Load testing user for ArcGIS Compliance Backend"""

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Setup before each user starts"""
        # You might want to add authentication here if needed
        # self.client.headers = {'Authorization': 'Bearer your-token'}
        pass

    @task(3)  # 30% of requests
    def test_compliance_api(self):
        """Test compliance calculation API"""
        start_time = time.time()

        # Test compliance endpoint - get all compliance records
        with self.client.get("/api/compliance/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                logger.info(f"✅ Compliance API: {len(response.json())} records")
            else:
                response.failure(f"❌ Compliance API failed: {response.status_code}")

        execution_time = time.time() - start_time
        logger.info(".2f")

    @task(3)  # 30% of requests
    def test_community_api(self):
        """Test community census data API"""
        start_time = time.time()

        # Test community endpoint
        with self.client.get("/api/community/communities/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                logger.info(f"✅ Community API: {len(response.json())} records")
            else:
                response.failure(f"❌ Community API failed: {response.status_code}")

        execution_time = time.time() - start_time
        logger.info(".2f")

    @task(2)  # 20% of requests
    def test_regulatory_rules_api(self):
        """Test regulatory rules API"""
        start_time = time.time()

        # Test regulatory rules endpoint
        with self.client.get("/api/regulatory-rules/rules/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                logger.info(f"✅ Regulatory Rules API: {len(response.json())} records")
            else:
                response.failure(f"❌ Regulatory Rules API failed: {response.status_code}")

        execution_time = time.time() - start_time
        logger.info(".2f")

    @task(1)  # 10% of requests
    def test_census_years_api(self):
        """Test census years API"""
        start_time = time.time()

        # Test census years endpoint
        with self.client.get("/api/community/census-years/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                logger.info(f"✅ Census Years API: {len(response.json())} records")
            else:
                response.failure(f"❌ Census Years API failed: {response.status_code}")

        execution_time = time.time() - start_time
        logger.info(".2f")

    @task(1)  # 10% of requests
    def test_sites_api(self):
        """Test sites API"""
        start_time = time.time()

        # Test sites endpoint
        with self.client.get("/api/sites/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                logger.info(f"✅ Sites API: {len(response.json())} records")
            else:
                response.failure(f"❌ Sites API failed: {response.status_code}")

        execution_time = time.time() - start_time
        logger.info(".2f")

    @task(1)  # 10% - Heavy load test
    def test_trigger_compliance_calculation(self):
        """Test triggering compliance calculation (heavy operation)"""
        start_time = time.time()

        # Get first community from list
        community_response = self.client.get("/api/community/communities/")
        if community_response.status_code == 200 and community_response.json():
            community_id = community_response.json()[0]['id']

            # Trigger compliance calculation for that community
            with self.client.post(f"/api/compliance/", json={
                "community": community_id,
                "program": "Paint"
            }, catch_response=True) as response:
                if response.status_code in [200, 201]:
                    response.success()
                    logger.info(f"✅ Compliance calculation triggered for community {community_id}")
                else:
                    response.failure(f"❌ Compliance calculation failed: {response.status_code}")

        execution_time = time.time() - start_time
        logger.info(".2f")

class MonitoringUser(HttpUser):
    """User for monitoring Celery and Redis status"""

    wait_time = between(5, 10)  # Check every 5-10 seconds

    @task
    def monitor_celery_flower(self):
        """Monitor Celery via Flower (if accessible)"""
        try:
            # This would only work if Flower is exposed publicly
            with self.client.get("http://localhost:5555/dashboard", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                    logger.info("✅ Flower dashboard accessible")
                else:
                    response.failure("❌ Flower dashboard not accessible")
        except Exception as e:
            logger.info(f"ℹ️  Flower monitoring skipped: {e}")

    @task
    def monitor_redis_info(self):
        """Monitor Redis status via API endpoint (would need custom endpoint)"""
        # You could add a custom API endpoint to expose Redis stats
        logger.info("ℹ️  Redis monitoring would require custom API endpoint")
