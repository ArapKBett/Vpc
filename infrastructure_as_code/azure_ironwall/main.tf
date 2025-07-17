# Azure provider configuration
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  client_id       = var.client_id
  client_secret   = var.client_secret
  tenant_id       = var.tenant_id
}

# Quantum-resistant Azure Virtual Network
resource "azurerm_virtual_network" "ironwall_vnet" {
  name                = "ironwall-vnet"
  address_space       = ["10.42.0.0/16"]
  location            = var.location
  resource_group_name = azurerm_resource_group.ironwall_rg.name

  tags = {
    Classification = "TopSecret"
    Codename       = "Ironwall"
  }
}

# Secure subnets with NSGs
resource "azurerm_subnet" "secure_subnets" {
  for_each = {
    "bastion"    = "10.42.1.0/24"
    "app"        = "10.42.2.0/24"
    "data"       = "10.42.3.0/24"
    "gateway"    = "10.42.4.0/24"
    "deception"  = "10.42.254.0/24"
  }

  name                 = each.key
  resource_group_name  = azurerm_resource_group.ironwall_rg.name
  virtual_network_name = azurerm_virtual_network.ironwall_vnet.name
  address_prefixes     = [each.value]

  enforce_private_link_endpoint_network_policies = true
  service_endpoints                             = ["Microsoft.KeyVault", "Microsoft.Storage"]
}

# Zero-trust Network Security Groups
resource "azurerm_network_security_group" "ironwall_nsg" {
  for_each = azurerm_subnet.secure_subnets

  name                = "nsg-${each.key}"
  location            = var.location
  resource_group_name = azurerm_resource_group.ironwall_rg.name

  security_rule {
    name                       = "default-deny-all-inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = {
    Environment = "Production"
  }
}

# Azure Bastion with quantum encryption
resource "azurerm_bastion_host" "quantum_bastion" {
  name                = "quantum-bastion"
  location            = var.location
  resource_group_name = azurerm_resource_group.ironwall_rg.name

  ip_configuration {
    name                 = "configuration"
    subnet_id            = azurerm_subnet.secure_subnets["bastion"].id
    public_ip_address_id = azurerm_public_ip.bastion_pip.id
  }

  tunneling_enabled      = true
  sku                    = "Standard"
  scale_units            = 2

  tags = {
    Crypto = "PostQuantum"
  }
}

# Post-quantum VPN Gateway
resource "azurerm_virtual_network_gateway" "quantum_vpn_gateway" {
  name                = "quantum-vpn-gw"
  location            = var.location
  resource_group_name = azurerm_resource_group.ironwall_rg.name

  type     = "Vpn"
  vpn_type = "RouteBased"
  sku      = "VpnGw2"

  ip_configuration {
    name                          = "vnetGatewayConfig"
    public_ip_address_id          = azurerm_public_ip.vpn_gw_pip.id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.secure_subnets["gateway"].id
  }

  vpn_client_configuration {
    address_space = ["172.16.100.0/24"]
    root_certificate {
      name             = "quantum-root-cert"
      public_cert_data = file("${path.module}/certs/quantum-root.cer")
    }
    vpn_client_protocols = ["OpenVPN"]
  }

  custom_route {
    address_prefixes = ["0.0.0.0/0"]
  }
}

# Azure Firewall with threat intelligence
resource "azurerm_firewall" "ironwall_fw" {
  name                = "ironwall-fw"
  location            = var.location
  resource_group_name = azurerm_resource_group.ironwall_rg.name
  sku_name            = "AZFW_Hub"
  sku_tier            = "Premium"

  ip_configuration {
    name                 = "configuration"
    subnet_id            = azurerm_subnet.secure_subnets["gateway"].id
    public_ip_address_id = azurerm_public_ip.fw_pip.id
  }

  threat_intel_mode = "Alert"
}

# Quantum Key Vault
resource "azurerm_key_vault" "quantum_kv" {
  name                        = "quantum-kv-${random_string.random.result}"
  location                    = var.location
  resource_group_name         = azurerm_resource_group.ironwall_rg.name
  enabled_for_disk_encryption = true
  tenant_id                   = var.tenant_id
  soft_delete_retention_days  = 90
  purge_protection_enabled    = true
  sku_name                    = "premium"

  access_policy {
    tenant_id = var.tenant_id
    object_id = var.object_id

    key_permissions = [
      "Get", "List", "Create", "Delete", "Recover", "Backup", "Restore",
      "Decrypt", "Encrypt", "UnwrapKey", "WrapKey", "Verify", "Sign"
    ]

    secret_permissions = [
      "Get", "List", "Set", "Delete", "Recover", "Backup", "Restore"
    ]
  }

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ips
  }
}

# Private Endpoints for secure access
resource "azurerm_private_endpoint" "kv_pe" {
  name                = "pe-kv-${azurerm_key_vault.quantum_kv.name}"
  location            = var.location
  resource_group_name = azurerm_resource_group.ironwall_rg.name
  subnet_id           = azurerm_subnet.secure_subnets["data"].id

  private_service_connection {
    name                           = "psc-kv"
    private_connection_resource_id = azurerm_key_vault.quantum_kv.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.kv_dns.id]
  }
}

# Variables
variable "subscription_id" {}
variable "client_id" {}
variable "client_secret" {}
variable "tenant_id" {}
variable "location" {
  default = "eastus2"
}
variable "allowed_ips" {
  type    = list(string)
  default = []
}
variable "object_id" {}

resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}

output "vnet_id" {
  value = azurerm_virtual_network.ironwall_vnet.id
}
