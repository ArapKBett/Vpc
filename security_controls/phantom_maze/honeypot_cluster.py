import socket
import threading
import ssl
import paramiko
import http.server
import socketserver
import json
import logging
import random
import time
from datetime import datetime
from cryptography.fernet import Fernet
import mysql.connector
import psycopg2
import redis

class PhantomMaze:
    def __init__(self):
        self.logger = self.setup_logger()
        self.attack_db = {}
        self.deception_ports = {
            'ssh': [22, 2222, 22222],
            'http': [80, 8080, 8888],
            'https': [443, 8443],
            'database': [3306, 5432, 6379],
            'rdp': [3389],
            'smtp': [25, 587]
        }
        self.credentials_db = self.load_credential_database()
        self.active_connections = {}
        self.setup_services()

    def setup_logger(self):
        logging.basicConfig(
            filename='phantom_maze.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='a'
        )
        return logging.getLogger('PhantomMaze')

    def load_credential_database(self):
        # Pre-populated fake credentials
        return {
            'ssh': [
                {'username': 'admin', 'password': 'P@ssw0rd123'},
                {'username': 'root', 'password': 'toor'},
                {'username': 'user', 'password': 'welcome1'}
            ],
            'web': [
                {'username': 'admin@company.com', 'password': 'Admin@123'},
                {'username': 'user@company.com', 'password': 'User@2023'}
            ],
            'db': [
                {'username': 'sa', 'password': 'sqladmin'},
                {'username': 'postgres', 'password': 'postgres'}
            ]
        }

    def setup_services(self):
        # Start all deception services in separate threads
        for service, ports in self.deception_ports.items():
            for port in ports:
                try:
                    if service == 'ssh':
                        thread = threading.Thread(
                            target=self.run_ssh_honeypot,
                            args=(port,)
                        )
                    elif service in ['http', 'https']:
                        thread = threading.Thread(
                            target=self.run_web_honeypot,
                            args=(port, service == 'https')
                        )
                    elif service == 'database':
                        thread = threading.Thread(
                            target=self.run_database_honeypot,
                            args=(port,)
                        )
                    else:
                        thread = threading.Thread(
                            target=self.run_generic_service,
                            args=(port, service)
                        )
                    
                    thread.daemon = True
                    thread.start()
                    self.logger.info(f"Started {service} honeypot on port {port}")
                except Exception as e:
                    self.logger.error(f"Failed to start {service} on {port}: {str(e)}")

    def run_ssh_honeypot(self, port):
        ssh_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssh_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ssh_socket.bind(('0.0.0.0', port))
        ssh_socket.listen(100)

        while True:
            try:
                client, addr = ssh_socket.accept()
                threading.Thread(
                    target=self.handle_ssh_connection,
                    args=(client, addr, port)
                ).start()
            except Exception as e:
                self.logger.error(f"SSH honeypot error on {port}: {str(e)}")
                time.sleep(5)

    def handle_ssh_connection(self, client, addr, port):
        transport = paramiko.Transport(client)
        transport.add_server_key(paramiko.RSAKey.generate(2048))
        
        server = PhantomSSHServer(
            self.credentials_db['ssh'],
            self.logger,
            addr,
            port
        )
        transport.start_server(server=server)

        try:
            # Log connection details
            attack_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source_ip': addr[0],
                'port': port,
                'service': 'ssh',
                'attempted_credentials': server.attempted_credentials,
                'session_duration': time.time() - server.start_time
            }
            self.log_attack(attack_data)
            
            # Add to active connections for monitoring
            conn_id = f"{addr[0]}-{datetime.utcnow().timestamp()}"
            self.active_connections[conn_id] = {
                'type': 'ssh',
                'start_time': datetime.utcnow(),
                'source_ip': addr[0],
                'credentials': server.attempted_credentials
            }
        finally:
            transport.close()
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]

    def run_web_honeypot(self, port, ssl_enabled=False):
        handler = PhantomHTTPRequestHandler
        handler.credentials = self.credentials_db['web']
        handler.logger = self.logger

        with socketserver.TCPServer(('0.0.0.0', port), handler) as httpd:
            if ssl_enabled:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain('fake_cert.pem', 'fake_key.pem')
                httpd.socket = context.wrap_socket(
                    httpd.socket,
                    server_side=True
                )
            
            httpd.serve_forever()

    def run_database_honeypot(self, port):
        if port == 3306:
            self.run_mysql_honeypot(port)
        elif port == 5432:
            self.run_postgres_honeypot(port)
        elif port == 6379:
            self.run_redis_honeypot(port)

    def run_mysql_honeypot(self, port):
        # Simplified MySQL honeypot
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen(5)

        while True:
            try:
                conn, addr = s.accept()
                threading.Thread(
                    target=self.handle_mysql_connection,
                    args=(conn, addr)
                ).start()
            except Exception as e:
                self.logger.error(f"MySQL honeypot error: {str(e)}")

    def handle_mysql_connection(self, conn, addr):
        try:
            # Send MySQL banner
            conn.send(b"\x4a\x00\x00\x00\x0a\x35\x2e\x37\x2e\x33\x32\x00\x0d\x00\x00\x00\x7a\x22\x47\x5e\x3f\x00\xff\xf7\x08\x02\x00\x0f\x80\x15\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x6f\x7a\x21\x3d\x50\x5c\x5a\x32\x2a\x7a\x00\x6d\x79\x73\x71\x6c\x5f\x6e\x61\x74\x69\x76\x65\x5f\x70\x61\x73\x73\x77\x6f\x72\x64\x00")
            
            # Receive client handshake
            data = conn.recv(1024)
            
            # Parse credentials (simplified)
            username = data[36:].split(b"\x00")[0].decode()
            password_length = data[36 + len(username) + 1]
            password = data[36 + len(username) + 2:36 + len(username) + 2 + password_length].decode()
            
            # Log the attempt
            attack_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source_ip': addr[0],
                'port': 3306,
                'service': 'mysql',
                'username': username,
                'password': password
            }
            self.log_attack(attack_data)
            
            # Send error response
            conn.send(b"\xff\x15\x04\x23\x32\x38\x30\x30\x30\x41\x63\x63\x65\x73\x73\x20\x64\x65\x6e\x69\x65\x64\x20\x66\x6f\x72\x20\x75\x73\x65\x72\x20\x27"+username.encode()+b"\27\x40\x27\x6c\x6f\x63\x61\x6c\x68\x6f\x73\x74\x27\x20\x28\x75\x73\x69\x6e\x67\x20\x70\x61\x73\x73\x77\x6f\x72\x64\x3a\x20\x59\x45\x53\x29")
        finally:
            conn.close()

    def log_attack(self, attack_data):
        attacker_ip = attack_data.get('source_ip')
        self.logger.info(json.dumps(attack_data))
        
        # Update attack database
        if attacker_ip not in self.attack_db:
            self.attack_db[attacker_ip] = []
        self.attack_db[attacker_ip].append(attack_data)
        
        # Trigger defensive measures
        self.trigger_countermeasures(attacker_ip)

    def trigger_countermeasures(self, attacker_ip):
        # Implement real-time blocking or other countermeasures
        pass

class PhantomSSHServer(paramiko.ServerInterface):
    def __init__(self, credentials, logger, addr, port):
        self.credentials = credentials
        self.logger = logger
        self.addr = addr
        self.port = port
        self.attempted_credentials = []
        self.start_time = time.time()

    def check_auth_password(self, username, password):
        # Log all attempts
        self.attempted_credentials.append({
            'username': username,
            'password': password,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Random delay to simulate processing
        time.sleep(random.uniform(0.5, 2.5))
        
        # Always return failure but with different error messages
        error_msgs = [
            "Permission denied, please try again",
            "Account locked due to multiple failed attempts",
            "Invalid credentials",
            "SSH service unavailable",
            "Keyboard interactive authentication required"
        ]
        return paramiko.AUTH_FAILED, random.choice(error_msgs)

    def get_allowed_auths(self, username):
        return 'password,publickey'

class PhantomHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    credentials = []
    logger = None
    
    def do_GET(self):
        # Track the request
        self.log_request()
        
        # Serve fake responses based on path
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
            <html><head><title>Company Portal</title></head>
            <body><h1>Employee Portal</h1>
            <a href="/login">Login</a></body></html>
            """)
        elif self.path == '/login':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
            <html><head><title>Login</title></head>
            <body>
            <form action="/login" method="post">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
            </form>
            </body></html>
            """)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        if self.path == '/login':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode()
            username = post_data.split('username=')[1].split('&')[0]
            password = post_data.split('password=')[1]
            
            # Log the attempt
            attack_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source_ip': self.client_address[0],
                'port': self.server.server_address[1],
                'service': 'http',
                'username': username,
                'password': password,
                'user_agent': self.headers.get('User-Agent')
            }
            self.logger.info(json.dumps(attack_data))
            
            # Send fake response
            self.send_response(302)
            self.send_header('Location', '/login?error=1')
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass

if __name__ == '__main__':
    phantom_maze = PhantomMaze()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nShutting down Phantom Maze...")
