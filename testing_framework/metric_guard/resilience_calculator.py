# AEGIS-SHIELD :: Metric Guard :: Resilience Calculator
# Path: /testing_framework/metric_guard/resilience_calculator.py
import json
import statistics
import time
from datetime import datetime
import logging
import pandas as pd
import numpy as np
from prometheus_client import start_http_server, Gauge

CODENAME = "RECOVERY-GUARD"
VERSION = "1.5-METRIC"

class ResilienceCalculator:
    def __init__(self):
        self.logger = self._setup_logger()
        self.metrics = self._init_metrics()
        self.start_time = time.time()
        
    def _setup_logger(self):
        logging.basicConfig(
            filename='resilience_metrics.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(CODENAME)
    
    def _init_metrics(self):
        start_http_server(9100)
        return {
            'recovery_time': Gauge(
                'resilience_recovery_seconds',
                'Time taken to recover from failures',
                ['failure_type']
            ),
            'availability': Gauge(
                'resilience_availability_percent',
                'System availability percentage'
            ),
            'throughput': Gauge(
                'resilience_throughput_rps',
                'Requests processed per second during failure'
            )
        }
    
    def analyze_chaos_report(self, report_file):
        """Calculate resilience metrics from chaos report"""
        with open(report_file) as f:
            report = json.load(f)
        
        recovery_times = []
        for result in report['results']:
            if result['status'] == 'success':
                if 'recovery' in result['result']:
                    recovery_times.append(result['result']['recovery'])
                
                # Update Prometheus metrics
                self.metrics['recovery_time'].labels(
                    failure_type=result['action']
                ).set(result['result'].get('recovery_sec', 0))
        
        if recovery_times:
            metrics = {
                'mean_recovery': statistics.mean(recovery_times),
                'max_recovery': max(recovery_times),
                'min_recovery': min(recovery_times),
                'availability': self._calculate_availability(report),
                'timestamp': datetime.utcnow().isoformat(),
                'codename': CODENAME,
                'version': VERSION
            }
            
            self.metrics['availability'].set(metrics['availability'])
            return metrics
        return None
    
    def _calculate_availability(self, report):
        """Calculate system availability during test"""
        total_time = 0
        downtime = 0
        
        for result in report['results']:
            if 'duration' in result['result']:
                total_time += result['result']['duration']
                if result['action'] in ['ec2_termination', 'pod_deletion']:
                    downtime += result['result'].get('downtime', 0)
        
        if total_time == 0:
            return 100.0
        return 100.0 - (downtime / total_time * 100)
    
    def generate_dashboard_data(self, reports):
        """Prepare data for resilience dashboard"""
        data = []
        for report in reports:
            with open(report) as f:
                data.append(json.load(f))
        
        df = pd.DataFrame(data)
        df.to_csv('testing_framework/metric_guard/dashboard/resilience_data.csv')
        self.logger.info("Dashboard data updated")

if __name__ == "__main__":
    print(f"Initializing {CODENAME} (v{VERSION})")
    calculator = ResilienceCalculator()
    
    # Example analysis
    metrics = calculator.analyze_chaos_report("chaos_report_net-001.json")
    with open("resilience_metrics.json", 'w') as f:
        json.dump(metrics, f, indent=2)
    
    # Update dashboard
    calculator.generate_dashboard_data([
        "chaos_report_net-001.json",
        "chaos_report_comp-001.json"
    ])
