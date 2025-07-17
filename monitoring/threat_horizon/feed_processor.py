# AEGIS-SHIELD :: Threat Horizon :: Intelligence Processor
# Path: /monitoring/threat_horizon/feed_processor.py
import requests
import json
import sqlite3
from datetime import datetime, timedelta
import logging
import hashlib
import pytz
from stix2 import MemoryStore, Filter

CODENAME = "THREAT-ORB"
VERSION = "3.5-INTEL"

class ThreatProcessor:
    def __init__(self):
        self.logger = self._setup_logger()
        self.feeds = self._load_feeds_config()
        self.conn = sqlite3.connect('monitoring/threat_horizon/ioc_database/threats.db')
        self._init_db()
        self.stix_memory = MemoryStore()

    def _setup_logger(self):
        logging.basicConfig(
            filename='threat_processor.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(CODENAME)

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS iocs (
                id TEXT PRIMARY KEY,
                type TEXT,
                value TEXT,
                first_seen TEXT,
                last_seen TEXT,
                source TEXT,
                severity TEXT,
                is_active INTEGER
            )
        ''')
        self.conn.commit()

    def _load_feeds_config(self):
        with open('monitoring/threat_horizon/feeds.json') as f:
            return json.load(f)

    def _hash_ioc(self, ioc_value):
        return hashlib.sha256(ioc_value.encode()).hexdigest()

    def _fetch_feed(self, feed_url):
        try:
            headers = {'User-Agent': f'{CODENAME}/{VERSION}'}
            response = requests.get(feed_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if feed_url.endswith('.json'):
                return response.json()
            elif feed_url.endswith('.stix2'):
                self.stix_memory.load_from_string(response.text)
                return self._process_stix()
            else:
                return response.text.splitlines()
        except Exception as e:
            self.logger.error(f"Feed fetch error: {str(e)}")
            return None

    def _process_stix(self):
        iocs = []
        filters = [
            Filter('type', '=', 'indicator'),
            Filter('valid_until', '>', datetime.now(pytz.UTC).isoformat())
        ]
        
        for indicator in self.stix_memory.query(filters):
            iocs.append({
                'type': 'stix',
                'value': indicator.pattern,
                'timestamp': indicator.created.isoformat(),
                'source': 'STIX Feed'
            })
        
        return iocs

    def _store_ioc(self, ioc):
        cursor = self.conn.cursor()
        
        # Check if IOC exists
        cursor.execute('SELECT * FROM iocs WHERE value = ?', (ioc['value'],))
        existing = cursor.fetchone()
        
        if existing:
            # Update last seen time
            cursor.execute('''
                UPDATE iocs 
                SET last_seen = ?, is_active = 1
                WHERE value = ?
            ''', (datetime.utcnow().isoformat(), ioc['value']))
        else:
            # Insert new IOC
            cursor.execute('''
                INSERT INTO iocs 
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                self._hash_ioc(ioc['value']),
                ioc.get('type', 'unknown'),
                ioc['value'],
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
                ioc.get('source', 'unknown'),
                ioc.get('severity', 'medium')
            ))
        
        self.conn.commit()

    def process_all_feeds(self):
        """Process all configured threat feeds"""
        self.logger.info(f"Starting {CODENAME} (v{VERSION}) feed processing")
        
        for feed in self.feeds['sources']:
            try:
                data = self._fetch_feed(feed['url'])
                if not data:
                    continue
                
                if isinstance(data, list):
                    for item in data:
                        self._store_ioc({
                            'type': feed.get('type', 'ip'),
                            'value': item.strip(),
                            'source': feed['name']
                        })
                elif isinstance(data, dict):
                    for item in data.get('indicators', []):
                        self._store_ioc({
                            'type': item.get('type'),
                            'value': item.get('value'),
                            'source': feed['name'],
                            'severity': item.get('severity', 'medium')
                        })
                
                self.logger.info(f"Processed {feed['name']} feed")
            except Exception as e:
                self.logger.error(f"Error processing {feed['name']}: {str(e)}")
        
        # Purge old IOCs
        self._purge_inactive()

    def _purge_inactive(self):
        """Remove IOCs not seen in 30 days"""
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE iocs 
            SET is_active = 0 
            WHERE last_seen < ?
        ''', (cutoff,))
        self.conn.commit()
        self.logger.info(f"Purged {cursor.rowcount} inactive IOCs")

    def check_ioc(self, value):
        """Check if value exists in threat database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM iocs 
            WHERE value = ? AND is_active = 1
        ''', (value,))
        return cursor.fetchone()

if __name__ == "__main__":
    processor = ThreatProcessor()
    processor.process_all_feeds()
