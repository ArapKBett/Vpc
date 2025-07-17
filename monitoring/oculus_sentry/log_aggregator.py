import logging
import json
import time
from datetime import datetime
import pandas as pd
from elasticsearch import Elasticsearch
import pymongo
import socket
import syslog
import threading
from prometheus_client import start_http_server, Counter, Gauge

class OculusSentry:
    def __init__(self, config_file='sentry_config.json'):
        with open(config_file) as f:
            self.config = json.load(f)
        
        self.logger = self.setup_logger()
        self.es = Elasticsearch(self.config['elasticsearch_hosts'])
        self.mongo = pymongo.MongoClient(self.config['mongo_uri'])
        self.db = self.mongo[self.config['mongo_db']]
        self.alerts = self.db.alerts
        self.metrics = self.setup_metrics()
        self.running = True
        
    def setup_logger(self):
        logging.basicConfig(
            filename='oculus_sentry.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('OculusSentry')
    
    def setup_metrics(self):
        metrics = {
            'events_processed': Counter(
                'sentry_events_processed_total',
                'Total security events processed'
            ),
            'alerts_triggered': Counter(
                'sentry_alerts_triggered_total',
                'Total security alerts triggered'
            ),
            'processing_time': Gauge(
                'sentry_event_processing_seconds',
                'Time taken to process events'
            ),
            'threat_level': Gauge(
                'sentry_threat_level',
                'Current threat level (0-10)'
            )
        }
        
        # Start Prometheus metrics server
        start_http_server(9090)
        return metrics
    
    def start_monitoring(self):
        # Start all monitoring threads
        threads = [
            threading.Thread(target=self.syslog_listener),
            threading.Thread(target=self.windows_event_monitor),
            threading.Thread(target=self.netflow_analyzer),
            threading.Thread(target=self.alert_correlator)
        ]
        
        for thread in threads:
            thread.daemon = True
            thread.start()
        
        self.logger.info("Started all monitoring threads")
        
        # Main processing loop
        while self.running:
            try:
                self.process_queued_events()
                time.sleep(1)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.logger.error(f"Processing error: {str(e)}")
                time.sleep(5)
    
    def syslog_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 514))
        
        self.logger.info("Syslog listener started on UDP 514")
        
        while self.running:
            try:
                data, addr = sock.recvfrom(8192)
                message = data.decode('utf-8').strip()
                
                event = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'source_ip': addr[0],
                    'facility': syslog.LOG_USER,
                    'message': message,
                    'type': 'syslog'
                }
                
                self.store_event(event)
                self.metrics['events_processed'].inc()
            except Exception as e:
                self.logger.error(f"Syslog error: {str(e)}")
    
    def windows_event_monitor(self):
        # Simulated Windows Event Log monitoring
        while self.running:
            try:
                # In production, this would use WinEvtLog API
                event = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'Security',
                    'event_id': random.choice([4624, 4625, 4648, 4768, 4776]),
                    'message': 'Simulated Windows security event',
                    'type': 'windows_event'
                }
                
                self.store_event(event)
                self.metrics['events_processed'].inc()
                time.sleep(random.uniform(0.1, 1.0))
            except Exception as e:
                self.logger.error(f"Windows event error: {str(e)}")
                time.sleep(5)
    
    def netflow_analyzer(self):
        # Simulated NetFlow analysis
        while self.running:
            try:
                flow = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'src_ip': f"10.0.{random.randint(0,255)}.{random.randint(1,254)}",
                    'dst_ip': f"192.168.{random.randint(0,255)}.{random.randint(1,254)}",
                    'bytes': random.randint(100, 100000),
                    'packets': random.randint(1, 100),
                    'type': 'netflow'
                }
                
                self.store_event(flow)
                self.metrics['events_processed'].inc()
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Netflow error: {str(e)}")
                time.sleep(5)
    
    def store_event(self, event):
        """Store event in both Elasticsearch and MongoDB"""
        start_time = time.time()
        
        try:
            # Index in Elasticsearch
            self.es.index(
                index='security-events',
                body=event
            )
            
            # Store in MongoDB
            self.db.events.insert_one(event)
            
            # Update metrics
            self.metrics['processing_time'].set(time.time() - start_time)
        except Exception as e:
            self.logger.error(f"Storage error: {str(e)}")
    
    def process_queued_events(self):
        """Process events and trigger alerts"""
        try:
            # Get recent events from MongoDB
            query = {
                'processed': {'$exists': False},
                'timestamp': {
                    '$gte': datetime.utcnow() - timedelta(minutes=5)
                }
            }
            
            events = list(self.db.events.find(query).limit(1000))
            
            for event in events:
                # Apply correlation rules
                alerts = self.apply_correlation_rules(event)
                
                if alerts:
                    self.metrics['alerts_triggered'].inc(len(alerts))
                    self.metrics['threat_level'].set(
                        min(10, self.metrics['threat_level']._value.get() + 0.1 * len(alerts))
                    )
                
                # Mark as processed
                self.db.events.update_one(
                    {'_id': event['_id']},
                    {'$set': {'processed': True}}
                )
        except Exception as e:
            self.logger.error(f"Processing error: {str(e)}")
    
    def apply_correlation_rules(self, event):
        """Apply security correlation rules to events"""
        alerts = []
        
        # Rule 1: Multiple failed logins
        if event.get('type') == 'windows_event' and event.get('event_id') == 4625:
            count = self.db.events.count_documents({
                'source_ip': event.get('source_ip'),
                'event_id': 4625,
                'timestamp': {
                    '$gte': datetime.utcnow() - timedelta(minutes=5)
                }
            })
            
            if count > 5:
                alerts.append({
                    'rule': 'multiple_failed_logins',
                    'severity': 'high',
                    'source_ip': event.get('source_ip'),
                    'count': count
                })
        
        # Rule 2: Unusual data transfer
        elif event.get('type') == 'netflow' and event.get('bytes', 0) > 500000:
            alerts.append({
                'rule': 'large_data_transfer',
                'severity': 'medium',
                'src_ip': event.get('src_ip'),
                'dst_ip': event.get('dst_ip'),
                'bytes': event.get('bytes')
            })
        
        # Store alerts if any
        if alerts:
            self.alerts.insert_many([{
                **alert,
                'timestamp': datetime.utcnow().isoformat(),
                'event_id': str(event.get('_id'))
            } for alert in alerts])
        
        return alerts
    
    def alert_correlator(self):
        """Correlate alerts into higher-level incidents"""
        while self.running:
            try:
                # Get unprocessed alerts
                alerts = list(self.alerts.find({
                    'correlated': {'$exists': False}
                }).limit(100))
                
                if alerts:
                    # Group by source IP
                    ip_alerts = {}
                    for alert in alerts:
                        ip = alert.get('source_ip') or alert.get('src_ip')
                        if ip not in ip_alerts:
                            ip_alerts[ip] = []
                        ip_alerts[ip].append(alert)
                    
                    # Create incidents for IPs with multiple alerts
                    for ip, ip_alert_list in ip_alerts.items():
                        if len(ip_alert_list) > 2:
                            incident = {
                                'timestamp': datetime.utcnow().isoformat(),
                                'source_ip': ip,
                                'alert_count': len(ip_alert_list),
                                'alerts': [a['_id'] for a in ip_alert_list],
                                'severity': max(a['severity'] for a in ip_alert_list),
                                'status': 'open'
                            }
                            
                            self.db.incidents.insert_one(incident)
                    
                    # Mark alerts as correlated
                    self.alerts.update_many(
                        {'_id': {'$in': [a['_id'] for a in alerts]}},
                        {'$set': {'correlated': True}}
                    )
                
                time.sleep(10)
            except Exception as e:
                self.logger.error(f"Alert correlation error: {str(e)}")
                time.sleep(30)

if __name__ == '__main__':
    sentry = OculusSentry()
    sentry.start_monitoring()
