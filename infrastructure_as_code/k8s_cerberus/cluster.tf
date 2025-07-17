# Kubernetes provider configuration
provider "kubernetes" {
  host                   = module.cerberus_cluster.cluster_endpoint
  cluster_ca_certificate = base64decode(module.cerberus_cluster.cluster_certificate_authority_data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks",
      "get-token",
      "--cluster-name",
      module.cerberus_cluster.cluster_name
    ]
  }
}

# Quantum-secure EKS cluster
module "cerberus_cluster" {
  source  = "terraform-aws-modules/eks/aws"
  version = "18.30.2"

  cluster_name    = "cerberus-cluster"
  cluster_version = "1.24"
  vpc_id          = var.vpc_id
  subnet_ids      = var.private_subnet_ids

  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]

  # Quantum-resistant encryption
  cluster_encryption_config = [{
    provider_key_arn = aws_kms_key.quantum_k8s.arn
    resources        = ["secrets"]
  }]

  # Zero-trust node groups
  eks_managed_node_groups = {
    secure_workers = {
      desired_size    = 3
      min_size        = 3
      max_size        = 10
      instance_types  = ["m6i.large"]
      capacity_type   = "ON_DEMAND"

      # Titan-hardened AMI
      ami_type        = "AL2_x86_64"

      # Node security configuration
      enable_monitoring           = true
      create_security_group       = false
      create_iam_role             = true
      iam_role_additional_policies = [
        "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
        "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
      ]

      # Kernel hardening
      pre_bootstrap_user_data = <<-EOT
        #!/bin/bash
        echo 'kernel.kptr_restrict=2' >> /etc/sysctl.d/99-hardening.conf
        echo 'kernel.dmesg_restrict=1' >> /etc/sysctl.d/99-hardening.conf
        echo 'net.ipv4.conf.all.rp_filter=1' >> /etc/sysctl.d/99-hardening.conf
        sysctl -p /etc/sysctl.d/99-hardening.conf
      EOT
    }
  }

  # Network policy enforcement
  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }

    egress_all = {
      description      = "Node all egress"
      protocol         = "-1"
      from_port        = 0
      to_port          = 0
      type             = "egress"
      cidr_blocks      = ["0.0.0.0/0"]
      ipv6_cidr_blocks = ["::/0"]
    }
  }
}

# Quantum KMS key for Kubernetes secrets
resource "aws_kms_key" "quantum_k8s" {
  description             = "Quantum-resistant KMS key for Cerberus cluster"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.quantum_kms_policy.json
  tags = {
    Name = "cerberus-quantum-key"
  }
}

# Post-quantum security policies
resource "kubernetes_network_policy" "zero_trust_policy" {
  metadata {
    name      = "zero-trust-default-deny"
    namespace = "default"
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]

    # Explicitly allow nothing
    ingress = []
    egress  = []
  }
}

# Falco runtime security
resource "helm_release" "falco" {
  name       = "falco"
  repository = "https://falcosecurity.github.io/charts"
  chart      = "falco"
  version    = "2.0.0"
  namespace  = "falco"

  set {
    name  = "falco.jsonOutput"
    value = "true"
  }

  set {
    name  = "falco.httpOutput.enabled"
    value = "true"
  }

  set {
    name  = "falco.httpOutput.url"
    value = "http://falco-sensor:2801"
  }
}

# Kyverno policy engine
resource "helm_release" "kyverno" {
  name       = "kyverno"
  repository = "https://kyverno.github.io/kyverno/"
  chart      = "kyverno"
  version    = "2.6.0"
  namespace  = "kyverno"

  set {
    name  = "validationFailureAction"
    value = "enforce"
  }
}

# Network policy for deception pods
resource "kubernetes_network_policy" "deception_policy" {
  metadata {
    name      = "allow-deception-traffic"
    namespace = "default"
  }

  spec {
    pod_selector {
      match_labels = {
        "app" = "deception"
      }
    }

    ingress {
      from   = []
      ports {
        port     = "any"
        protocol = "any"
      }
    }

    egress {
      to {
        ip_block {
          cidr = "0.0.0.0/0"
        }
      }
    }

    policy_types = ["Ingress", "Egress"]
  }
}
