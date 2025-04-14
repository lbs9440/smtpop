import socket
import base64
import hashlib

SERVER_HOST = 'localhost'
SERVER_PORT = 2525
DOMAIN = 'abeersclass.com'

class EmailClient:
    def __init__(self):
        self.username = None
        self.password_hash = None

    def run(self):
        print("Welcome to abeersclass.com Email Client")
        if self.login():
            print(f"Logged in as {self.username}@{DOMAIN}")
        else:
            print("Login failed.")

    def login(self):
        s = self.connect()
        if not s:
            return False

        try:
            self.send_and_print(s, "EHLO client.abeersclass.com")
            server_response = self.read_multiline(s)
            if "250-AUTH LOGIN PLAIN" not in server_response:
                print("Server does not support AUTH LOGIN.")
                s.close()
                return False

            self.send_and_print(s, "AUTH LOGIN")
            username_prompt = self.read_response(s).strip()
            if not username_prompt.startswith("334"):
                print("Expected username prompt.")
                s.close()
                return False

            user_input = input("Enter username or email: ").strip()
            if "@" in user_input:
                username, domain = user_input.split("@", 1)
                if domain.lower() != DOMAIN:
                    print("You're not in Abeers Class!.")
                    s.close()
                    return False
            else:
                username = user_input

            encoded_user = base64.b64encode(username.encode()).decode()
            self.send_and_print(s, encoded_user)

            password_prompt = self.read_response(s).strip()
            if not password_prompt.startswith("334"):
                print("Expected password prompt.")
                s.close()
                return False

            password = input("Enter password: ").strip()
            encoded_pass = base64.b64encode(password.encode()).decode()
            self.send_and_print(s, encoded_pass)

            auth_response = self.read_response(s).strip()
            print(f"Server: {auth_response}")

            if auth_response.startswith("235"):
                self.username = username
                self.password_hash = self.hash_password(password)
                s.close()
                return True
            else:
                s.close()
                return False

        except Exception as e:
            print("Login error:", e)
            s.close()
            return False

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((SERVER_HOST, SERVER_PORT))
            greeting = self.read_response(s)
            print(f"Server: {greeting.strip()}")
            return s
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    def read_response(self, sock):
        return sock.recv(2048).decode()

    def read_multiline(self, sock):
        data = b""
        while True:
            chunk = sock.recv(2048)
            data += chunk
            if b"\n" in chunk:
                break
        return data.decode()

    def send_and_print(self, sock, msg):
        sock.sendall((msg + "\r\n").encode())
        print(f"> {msg}")

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

def main():
    client = EmailClient()
    client.run()

if __name__ == "__main__":
    main()