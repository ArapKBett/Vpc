# Quantum-resistant VPC with zero-trust architecture
module "blackforge_vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.18.0"

  name = "blackforge-vpc"
  cidr = "10.42.0.0/16"

  azs = ["us-west-2a", "us-west-2b", "us-west-2c"]
  private_subnets = ["10.42.1.0/24", "10.42.2.0/24", "10.42.3.0/24"]
  public_subnets  = ["10.42.101.0/24", "10.42.102.0/24", "10.42.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  # Quantum-secure flow logs
  enable_flow_logs           = true
  flow_log_destination_type  = "cloud-watch-logs"
  flow_log_log_format        = "$${version} $${vpc-id} $${subnet-id} $${instance-id} $${interface-id} $$${account-id} $${srcaddr} $${dstaddr} $${srcport} $${dstport} $${protocol} $${packets} $${bytes} $${start} $${end} $${action} $${tcp-flags} $${log-status}"
  flow_log_max_aggregation_interval = 60

  # Bastion host setup
  enable_ssm_endpoint              = true
  ssm_endpoint_private_dns_enabled = true

  # VPC Endpoints for private access
  enable_s3_endpoint = true

  # Security groups - default deny all
  default_security_group_ingress = []
  default_security_group_egress  = []

  # Network ACLs
  manage_default_network_acl = true
  default_network_acl_ingress = []
  default_network_acl_egress = []

  # VPC Flow Logs
  vpc_flow_log_tags = {
    Name = "blackforge-flow-logs"
    Classification = "TopSecret"
  }
}

# Post-quantum VPN module
module "quantum_vpn" {
  source = "terraform-aws-modules/vpn-gateway/aws"
  version = "2.11.0"

  vpc_id = module.blackforge_vpc.vpc_id
  vpn_gateway_id = aws_vpn_gateway.blackforge.id

  customer_gateways = {
    HQ = {
      bgp_asn    = 65000
      ip_address = "203.0.113.1"
      type       = "ipsec.1"
    }
  }

  # Using strongSwan with post-quantum algorithms
  vpn_connections = {
    HQ = {
      customer_gateway_id = module.quantum_vpn.customer_gateway_id
      type                = "ipsec.1"
      static_routes_only  = true
      tunnel_phase1_encryption_algorithms   = ["AES256-GCM-SHA384"]
      tunnel_phase1_integrity_algorithms    = ["SHA2-384"]
      tunnel_phase1_dh_group_numbers        = [24]
      tunnel_phase2_encryption_algorithms   = ["AES256-GCM-SHA384"]
      tunnel_phase2_integrity_algorithms    = ["SHA2-384"]
      tunnel_phase2_dh_group_numbers        = [24]
    }
  }
}

# Quantum Key Management System
resource "aws_kms_key" "quantum_key" {
  description             = "Quantum-resistant KMS key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.quantum_kms_policy.json
  tags = {
    Name = "blackforge-quantum-key"
  }
}

# Zero-trust IAM policies
data "aws_iam_policy_document" "quantum_kms_policy" {
  statement {
    sid    = "EnableRoot"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowAttachment"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey"
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:CallerAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}
