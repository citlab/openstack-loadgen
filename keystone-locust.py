
from locust import Locust, TaskSet, task

AUTH_URL = 'http://controller:35357/v2.0'
TENANT = "admin"
USER = "admin"
PASSWORD = "iep9Teig"

class KeystoneTaskSet(TaskSet):
    
    @task
    def login(l):
        l.client.post("/v2.0/tokens", {"tenantName": TENANT, ""}


class KeystoneLocust(Locust):
    task_set = KeystoneTaskSet
    min_wait = 3000
    max_wait = 7000

