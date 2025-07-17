# AEGIS-SHIELD :: Oculus Sentry :: SIEM Core Engine
# Path: /monitoring/oculus_sentry/siem_core.py
import json
import logging
import time
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from kafka import KafkaConsumer
import yaml
import re
import hashlib

CODENAME = "SENTRY-CORE"
VERSION = "4.2-SIEM"

class OculusSentry:
    def __init__(self):
        self.logger = self._setup_logger()
        self.es = Elasticsearch(['http://elastic:9200'])
        self.rules = self._load_correlation_rules()
        self.consumer = KafkaConsumer(
            'security-events',
            bootstrap_servers=['kafka:9092'],
            auto_offset_reset='latest'
        )
        self.threat_cache = {}

    def _setup_logger(self):
        logging.basicConfig(
            filename='oculus_sentry.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(CODENAME)

    def _load_correlation_rules(self):
        rules = []
        rule_files = [
            'monitoring/oculus_sentry/correlation_rules/brute_force.yaml',
            'monitoring/oculus_sentry/correlation_rules/lateral_movement.yaml'
        ]
        
        for rule_file in rule_files:
            with open(rule_file) as f:
                rules.append(yaml.safe_load(f))
        
        self.logger.info(f"Loaded {len(rules)} correlation rules")
        return rules

    def _match_rule(self, event, rule):
        """Check if event matches correlation rule conditions"""
        # Field matching
        for condition in rule['conditions']:
            field_value = event.get(condition['field'])
            if not field_value:
                return False
            
            if condition['type'] == 'regex':
                if not re.match(condition['pattern'], str(field_value)):
                    return False
            elif condition['type'] == 'equals':
                if str(field_value) != condition['value']:
                    return False
        
        # Temporal conditions
        if 'timeframe' in rule:
            similar_events = self.es.search(
                index='security-events',
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"source.ip": event['source']['ip']}},
                                {"range": {
                                    "@timestamp": {
                                        "gte": f"now-{rule['timeframe']}m/m",
                                        "lte": "now/m"
                                    }
                                }}
                            ]
                        }
                    }
                }
            )
            if similar_events['hits']['total']['value'] < rule['threshold']:
                return False
        
        return True

    def _generate_alert(self, event, rule):
        """Create enriched security alert"""
        alert_id = hashlib.sha256(
            f"{event['@timestamp']}-{rule['id']}".encode()
        ).hexdigest()
        
        return {
            "alert_id": alert_id,
            "timestamp": datetime.utcnow().isoformat(),
            "rule": rule['id'],
            "severity": rule['severity'],
            "event": event,
            "codename": CODENAME,
            "version": VERSION,
            "status": "open"
        }

    def process_events(self):
        """Main processing loop"""
        self.logger.info(f"Starting {CODENAME} (v{VERSION}) event processing")
        for message in self.consumer:
            try:
                event = json.loads(message.value.decode('utf-8'))
                
                for rule in self.rules:
                    if self._match_rule(event, rule):
                        alert = self._generate_alert(event, rule)
                        self._store_alert(alert)
                        self._trigger_response(alert)
            except Exception as e:
                self.logger.error(f"Processing error: {str(e)}")

    def _store_alert(self, alert):
        """Store alert in Elasticsearch"""
        self.es.index(
            index='security-alerts',
            body=alert
        )
        self.logger.info(f"Generated alert {alert['alert_id']}")

    def _trigger_response(self, alert):
        """Execute automated response actions"""
        if alert['severity'] == 'critical':
            # Example: Block IP via firewall
            ip = alert['event']['source']['ip']
            self.logger.warning(f"Blocking malicious IP: {ip}")
            # os.system(f"iptables -A INPUT -s {ip} -j DROP")

if __name__ == "__main__":
    sentry = OculusSentry()
    sentry.process_events()
