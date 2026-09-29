# The runtime runs in VPC mode in private subnets with no internet gateway and no NAT. Everything it calls
# (ECR, S3 for image layers, CloudWatch Logs, X-Ray, Bedrock, AgentCore Memory and Gateway) is reached through
# VPC endpoints. See docs/adr/0006-private-runtime-with-vpc-endpoints.md.

# AgentCore Runtime supports VPC mode only in some Availability Zones, identified by zone ID (the name-to-ID
# mapping differs per account). Pinning the IDs keeps the subnet set fixed.
data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "zone-id"
    values = var.availability_zone_ids
  }
}

locals {
  azs = data.aws_availability_zones.available.names
  interface_endpoints = toset([
    "bedrock-agentcore",
    "bedrock-agentcore.gateway",
    "bedrock-runtime",
    "ecr.api",
    "ecr.dkr",
    "logs",
    "xray",
  ])
}

resource "aws_vpc" "agent" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = var.name }
}

# No rules: nothing may use the default security group.
resource "aws_default_security_group" "agent" {
  vpc_id = aws_vpc.agent.id
}

resource "aws_subnet" "private" {
  count = length(local.azs)

  vpc_id                  = aws_vpc.agent.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  map_public_ip_on_launch = false

  tags = { Name = "${var.name}-private-${local.azs[count.index]}" }
}

# Only the local route and the S3 gateway endpoint route; no default route anywhere.
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.agent.id

  tags = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "runtime" {
  #checkov:skip=CKV2_AWS_5:Attached to the AgentCore runtime (network_mode_config.security_groups in runtime.tf), which Checkov does not model.
  name        = "${var.name}-runtime"
  description = "AgentCore runtime: HTTPS to the VPC endpoints and S3 only"
  vpc_id      = aws_vpc.agent.id

  tags = { Name = "${var.name}-runtime" }
}

resource "aws_vpc_security_group_egress_rule" "runtime_to_endpoints" {
  security_group_id            = aws_security_group.runtime.id
  description                  = "HTTPS to the interface endpoints"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.endpoints.id
}

resource "aws_vpc_security_group_egress_rule" "runtime_to_s3" {
  security_group_id = aws_security_group.runtime.id
  description       = "HTTPS to S3 through the gateway endpoint (ECR image layers)"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name}-endpoints"
  description = "Interface endpoints: HTTPS from the runtime only"
  vpc_id      = aws_vpc.agent.id

  tags = { Name = "${var.name}-endpoints" }
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_runtime" {
  security_group_id            = aws_security_group.endpoints.id
  description                  = "HTTPS from the runtime"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.runtime.id
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = aws_vpc.agent.id
  service_name        = "com.amazonaws.${local.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]

  tags = { Name = "${var.name}-${each.key}" }
}

# ECR stores image layers in a service-owned S3 bucket; the endpoint policy allows only that bucket.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.agent.id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "EcrImageLayers"
      Effect    = "Allow"
      Principal = "*"
      Action    = ["s3:GetObject"]
      Resource  = ["arn:${local.partition}:s3:::prod-${local.region}-starport-layer-bucket/*"]
    }]
  })

  tags = { Name = "${var.name}-s3" }
}

resource "aws_cloudwatch_log_group" "flow" {
  name              = "/${var.name}/vpc-flow-logs"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.agent.arn
}

resource "aws_iam_role" "flow" {
  name = "${var.name}-vpc-flow-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "flow" {
  name = "write-flow-logs"
  role = aws_iam_role.flow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
      Resource = "${aws_cloudwatch_log_group.flow.arn}:*"
    }]
  })
}

resource "aws_flow_log" "agent" {
  vpc_id                   = aws_vpc.agent.id
  traffic_type             = "ALL"
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.flow.arn
  iam_role_arn             = aws_iam_role.flow.arn
  max_aggregation_interval = 600
}
