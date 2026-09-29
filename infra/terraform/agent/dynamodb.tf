# Fictional store data the tools read and write. In a real engagement these would be the order and inventory
# services' APIs; tables keep the lab self-contained.

locals {
  tables = {
    orders  = { hash = "order_id", range = null }
    stock   = { hash = "sku", range = "store_id" }
    returns = { hash = "return_id", range = null }
  }
}

resource "aws_dynamodb_table" "store" {
  for_each = local.tables

  name                        = "${var.name}-${each.key}"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = each.value.hash
  range_key                   = each.value.range
  deletion_protection_enabled = var.deletion_protection

  attribute {
    name = each.value.hash
    type = "S"
  }

  dynamic "attribute" {
    for_each = each.value.range == null ? [] : [each.value.range]
    content {
      name = attribute.value
      type = "S"
    }
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.agent.arn
  }

  point_in_time_recovery {
    enabled = true
  }
}
