from locust import HttpUser, task, between
import jwt
import uuid
import urllib3

# Disabilita i warning relativi ai certificati non verificati
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class PlayerServiceUser(HttpUser):
    host = "https://localhost:5001" 
    wait_time = between(1, 5)

    def on_start(self):
        self.client.verify = False

        unique_id = str(uuid.uuid4())[:8]
        self.username = f"user_{unique_id}"
        self.password = "securepassword123"
        
        self.client.post("/account", json={
            "username": self.username,
            "password": self.password
        })
        
        response = self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.player_id = str(data.get("id"))
        else:
            self.token = None
            self.player_id = None
            print(f"Login failed: {response.status_code} - {response.text}")

    @task(2)
    def validate_token(self):
        if not self.token:
            return
        try:
            decoded_token = jwt.decode(
                self.token,
                options={"verify_signature": False},
                algorithms=["RS256"]
            )
            assert decoded_token["username"] == self.username, "Username mismatch in token"
            assert decoded_token["iss"] == "player-service", "Issuer mismatch"
        except Exception as e:
            print(f"Token validation failed: {e}")

    @task(1)
    def health_check(self):
        response = self.client.get("/health")
        if response.status_code == 200:
            assert response.json().get("status") == "healthy", "Health check failed"
        else:
            print(f"Health check failed: {response.status_code} - {response.text}")