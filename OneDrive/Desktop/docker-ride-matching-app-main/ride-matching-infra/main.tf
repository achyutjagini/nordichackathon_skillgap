# 1. Provider and Resource Group Setup
provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = "ride-matching-pro-rg"
  location = "Sweden Central" # Optimal for H&M Stockholm location
}

# 2. Networking Foundation (The Secure VNet)
resource "azurerm_virtual_network" "vnet" {
  name                = "ride-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_subnet" "subnet" {
  name                 = "container-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]

  # Delegation is required for ACI to join a VNet
  delegation {
    name = "aci-delegation"
    service_delegation {
      name    = "Microsoft.ContainerInstance/containerGroups"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_network_profile" "net_profile" {
  name                = "ride-net-profile"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  container_network_interface {
    name = "nic"
    ip_configuration {
      name      = "ipconfig"
      subnet_id = azurerm_subnet.subnet.id
    }
  }
}

# 3. Infrastructure Groups (Private)
# RabbitMQ Message Broker
resource "azurerm_container_group" "rabbitmq" {
  name                = "rabbitmq-cg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Private"
  network_profile_id  = azurerm_network_profile.net_profile.id

  container {
    name   = "rabbitmq"
    image  = "rabbitmq:3-management"
    cpu    = "1"
    memory = "1"
    ports { port = 5672; protocol = "TCP" }
  }
}

# MongoDB Database
resource "azurerm_container_group" "mongodb" {
  name                = "mongodb-cg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Private"
  network_profile_id  = azurerm_network_profile.net_profile.id

  container {
    name   = "mongodb"
    image  = "mongo:latest"
    cpu    = "1"
    memory = "1"
    ports { port = 27017; protocol = "TCP" }
  }
}

# 4. Application Groups
# Producer (Public Facing Entry Point)
resource "azurerm_container_group" "producer" {
  name                = "producer-cg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Public" 
  dns_name_label      = "ride-producer-api" # Creates a URL for your curl requests

  container {
    name   = "producer"
    image  = "your-registry.azurecr.io/producer:latest"
    cpu    = "0.5"
    memory = "0.5"
    ports { port = 5000; protocol = "TCP" }
  }
}

# Ride Matching Consumer (C1)
resource "azurerm_container_group" "matcher" {
  name                = "matcher-cg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Private"
  network_profile_id  = azurerm_network_profile.net_profile.id

  container {
    name   = "matcher-c1"
    image  = "your-registry.azurecr.io/ride_matching:latest"
    cpu    = "0.5"
    memory = "0.5"
    environment_variables = {
      "CONSUMER_ID"      = "C1"
      "PRODUCER_ADDRESS" = "ride-producer-api.swedencentral.azurecontainer.io:5000"
    }
  }
}

# Ride Database Consumer
resource "azurerm_container_group" "db_worker" {
  name                = "db-worker-cg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Private"
  network_profile_id  = azurerm_network_profile.net_profile.id

  container {
    name   = "db-worker"
    image  = "your-registry.azurecr.io/ride_database:latest"
    cpu    = "0.5"
    memory = "0.5"
  }
}