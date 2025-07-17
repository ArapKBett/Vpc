# AEGIS-SHIELD :: Chaos Prime :: Chaos Engine
# Path: /testing_framework/chaos_prime/failure_scenarios/chaos_engine.py
import random
import time
import subprocess
import docker
import kubernetes.client
from kubernetes.client import CoreV1Api
from kubernetes.config import load_kube_config
import boto3
import logging
from datetime import datetime
import json

CODENAME = "SYSTEM-SHOCK"
VERSION = "3.1-CHAOS"

class ChaosEngine:
    def __init__(self):
        self.logger = self._setup_logger()
        self.ec2 = boto3.client('ec2')
        self.docker = docker.from_env()
        self.k8s_client = self._init_k8s()
        self.scenarios = self._load_scenarios()
        
    def _setup_logger(self):
        logging.basicConfig(
            filename='chaos_engine.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(CODENAME)
    
    def _init_k8s(self):
        try:
            load_kube_config()
            return CoreV1Api()
        except:
            self.logger.warning("Kubernetes not available")
            return None
    
    def _load_scenarios(self):
        with open('testing_framework/chaos_prime/failure_scenarios/scenarios.json') as f:
            return json.load(f)
    
    def execute_scenario(self, scenario_id):
        """Execute predefined failure scenario"""
        scenario = next((s for s in self.scenarios if s['id'] == scenario_id), None)
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        
        self.logger.info(f"Executing scenario: {scenario['name']}")
        results = []
        
        for action in scenario['actions']:
            try:
                if action['type'] == 'network':
                    result = self._network_chaos(action)
                elif action['type'] == 'compute':
                    result = self._compute_chaos(action)
                elif action['type'] == 'k8s':
                    result = self._k8s_chaos(action)
                
                results.append({
                    'action': action['name'],
                    'status': 'success',
                    'result': result,
                    'timestamp': datetime.utcnow().isoformat()
                })
            except Exception as e:
                results.append({
                    'action': action['name'],
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return {
            'scenario': scenario['name'],
            'results': results,
            'codename': CODENAME,
            'version': VERSION
        }
    
    def _network_chaos(self, action):
        """Execute network failure scenarios"""
        if action['name'] == 'latency_injection':
            latency = random.randint(100, 1000)
            subprocess.run(f"tc qdisc add dev eth0 root netem delay {latency}ms", shell=True)
            return f"Injected {latency}ms latency"
        
        elif action['name'] == 'packet_loss':
            loss = random.randint(5, 30)
            subprocess.run(f"tc qdisc change dev eth0 root netem loss {loss}%", shell=True)
            return f"Injected {loss}% packet loss"
    
    def _compute_chaos(self, action):
        """Execute compute failure scenarios"""
        if action['name'] == 'ec2_termination':
            instances = self.ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            if instances['Reservations']:
                instance_id = random.choice(instances['Reservations'][0]['Instances'])['InstanceId']
                self.ec2.terminate_instances(InstanceIds=[instance_id])
                return f"Terminated instance {instance_id}"
        
        elif action['name'] == 'docker_kill':
            containers = self.docker.containers.list()
            if containers:
                container = random.choice(containers)
                container.kill()
                return f"Killed container {container.id}"
    
    def _k8s_chaos(self, action):
        """Execute Kubernetes failure scenarios"""
        if not self.k8s_client:
            raise Exception("Kubernetes not configured")
        
        if action['name'] == 'pod_deletion':
            pods = self.k8s_client.list_pod_for_all_namespaces().items
            if pods:
                pod = random.choice(pods)
                self.k8s_client.delete_namespaced_pod(
                    pod.metadata.name,
                    pod.metadata.namespace
                )
                return f"Deleted pod {pod.metadata.name}"

if __name__ == "__main__":
    print(f"Initializing {CODENAME} (v{VERSION})")
    chaos = ChaosEngine()
    
    # Execute all scenarios
    for scenario in chaos.scenarios:
        report = chaos.execute_scenario(scenario['id'])
        with open(f"chaos_report_{scenario['id']}.json", 'w') as f:
            json.dump(report, f, indent=2)
