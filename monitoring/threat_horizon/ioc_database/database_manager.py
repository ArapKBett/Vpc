# AEGIS-SHIELD :: Threat Horizon :: IOC Database Manager
# Path: /monitoring/threat_horizon/ioc_database/database_manager.py
import sqlite3
import json
from datetime import datetime, timedelta
import logging
import hashlib

CODENAME = "IOC-GUARDIAN"
VERSION = "2.1-DB"

class IOCDatabase:
    def __init__(self):
        self.logger = self._setup_logger()
        self.conn = sqlite3.connect('monitoring/threat_horizon/ioc_database/threats.db')
    
    def _setup_logger(self):
        logging.basicConfig(
            filename='ioc_database.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(CODENAME)
    
    def search_iocs(self, ioc_type=None, severity=None, last_seen=None):
        """Search IOCs in database"""
        query = "SELECT * FROM iocs WHERE is_active = 1"
        params = []
        
        if ioc_type:
            query += " AND type = ?"
            params.append(ioc_type)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        if last_seen:
            cutoff = (datetime.utcnow() - timedelta(days=int(last_seen))).isoformat()
            query += " AND last_seen > ?"
            params.append(cutoff)
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'type': row[1],
                'value': row[2],
                'first_seen': row[3],
                'last_seen': row[4],
                'source': row[5],
                'severity': row[6]
            })
        
        return results
    
    def export_iocs(self, format='json'):
        """Export IOCs in specified format"""
        iocs = self.search_iocs()
        
        if format == 'json':
            return json.dumps(iocs, indent=2)
        elif format == 'csv':
            csv = "type,value,severity,source\n"
            for ioc in iocs:
                csv += f"{ioc['type']},{ioc['value']},{ioc['severity']},{ioc['source']}\n"
            return csv
        elif format == 'stix2':
            # Convert to STIX2 format
            stix_objects = []
            for ioc in iocs:
                stix_objects.append({
                    "type": "indicator",
                    "id": f"indicator--{ioc['id']}",
                    "created": ioc['first_seen'],
                    "modified": ioc['last_seen'],
                    "pattern": f"[{ioc['type']}:value = '{ioc['value']}']",
                    "valid_from": datetime.utcnow().isoformat()
                })
            return json.dumps(stix_objects, indent=2)
    
    def purge_database(self, days=30):
        """Purge IOCs older than specified days"""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM iocs WHERE last_seen < ?', (cutoff,))
        self.conn.commit()
        self.logger.info(f"Purged {cursor.rowcount} IOCs older than {days} days")

if __name__ == "__main__":
    print(f"Initializing {CODENAME} (v{VERSION})")
    db = IOCDatabase()
    
    # Example: Export recent high severity IOCs
    print(db.export_iocs(format='json'))
