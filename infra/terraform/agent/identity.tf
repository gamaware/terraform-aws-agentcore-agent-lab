# Inbound identity: store staff sign in to a Cognito user pool. The runtime and the gateway both validate the
# same access token (custom JWT authorizer, this pool's discovery URL, this app client). The gateway policy
# engine reads the token's cognito:groups claim. See docs/adr/0004-caller-token-reaches-the-gateway.md.

resource "aws_cognito_user_pool" "staff" {
  name                     = "${var.name}-staff"
  deletion_protection      = var.deletion_protection ? "ACTIVE" : "INACTIVE"
  mfa_configuration        = "OPTIONAL"
  auto_verified_attributes = []

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }
}

# Group names must not contain one another: the policies match them inside the groups claim
# (docs/adr/0003-authorization-outside-the-prompt.md). Terraform owns every group in this pool.
resource "aws_cognito_user_group" "staff" {
  for_each = toset(local.staff_group)

  user_pool_id = aws_cognito_user_pool.staff.id
  name         = each.key
  description  = each.key == "store-leads" ? "Can open returns up to the refund limit" : "Read-only store tools"
}

resource "aws_cognito_user_pool_client" "store_app" {
  name         = "${var.name}-store-app"
  user_pool_id = aws_cognito_user_pool.staff.id

  generate_secret               = false
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  access_token_validity         = 60
  id_token_validity             = 60
  refresh_token_validity        = 12

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "hours"
  }

  explicit_auth_flows = concat(
    ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    var.enable_admin_auth_flow ? ["ALLOW_ADMIN_USER_PASSWORD_AUTH"] : [],
  )
}
