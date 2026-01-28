resource "azurerm_container_group" "matcher" {
  # This creates as many groups as specified in the variable (e.g., 2)
  count               = var.matcher_count 
  
  name                = "matcher-cg-${count.index + 1}" # Generates matcher-cg-1, matcher-cg-2
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Private"
  network_profile_id  = azurerm_network_profile.net_profile.id

  container {
    name   = "matcher-c${count.index + 1}"
    image  = "your-registry.azurecr.io/ride_matching:latest"
    cpu    = "0.5"
    memory = "0.5"
    
    environment_variables = {
      # This dynamically sets C1, C2, C3...
      "CONSUMER_ID"      = "C${count.index + 1}" 
      "PRODUCER_ADDRESS" = "${var.producer_dns_label}.${var.location}.azurecontainer.io:5000"
    }
  }
}