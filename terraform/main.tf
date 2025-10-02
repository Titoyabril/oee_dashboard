# OEE Analytics Infrastructure - Terraform Configuration
# Deploys production OEE system with MQTT cluster, TimescaleDB, and edge gateways

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket         = "oee-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "oee-terraform-locks"
  }
}

# Provider configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "OEE-Analytics"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = var.owner
    }
  }
}

# Local variables
locals {
  common_tags = {
    Project     = "OEE-Analytics"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  mqtt_cluster_size = 3
  edge_gateway_count = var.edge_gateway_count
}

# ========================================
# Networking
# ========================================

module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = var.availability_zones
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  enable_vpn_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.common_tags
}

# ========================================
# Security Groups
# ========================================

# MQTT Broker Security Group
resource "aws_security_group" "mqtt_broker" {
  name_prefix = "${var.environment}-mqtt-broker-"
  description = "Security group for MQTT broker cluster"
  vpc_id      = module.vpc.vpc_id

  # MQTT SSL (from edge gateways)
  ingress {
    description = "MQTT SSL from edge gateways"
    from_port   = 8883
    to_port     = 8883
    protocol    = "tcp"
    cidr_blocks = [var.edge_network_cidr]
  }

  # MQTT WebSocket SSL (from dashboards)
  ingress {
    description = "MQTT WebSocket SSL"
    from_port   = 8084
    to_port     = 8084
    protocol    = "tcp"
    cidr_blocks = [var.dashboard_network_cidr]
  }

  # EMQX Dashboard (internal only)
  ingress {
    description = "EMQX Dashboard"
    from_port   = 18083
    to_port     = 18083
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr]
  }

  # EMQX Cluster communication
  ingress {
    description = "EMQX Cluster"
    from_port   = 4370
    to_port     = 4370
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-mqtt-broker-sg"
  })
}

# TimescaleDB Security Group
resource "aws_security_group" "timescaledb" {
  name_prefix = "${var.environment}-timescaledb-"
  description = "Security group for TimescaleDB"
  vpc_id      = module.vpc.vpc_id

  # PostgreSQL from application layer
  ingress {
    description     = "PostgreSQL from app servers"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_server.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-timescaledb-sg"
  })
}

# Application Server Security Group
resource "aws_security_group" "app_server" {
  name_prefix = "${var.environment}-app-server-"
  description = "Security group for Django application servers"
  vpc_id      = module.vpc.vpc_id

  # HTTP from load balancer
  ingress {
    description     = "HTTP from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # SSH from bastion (if needed)
  ingress {
    description = "SSH from admin"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-app-server-sg"
  })
}

# Application Load Balancer Security Group
resource "aws_security_group" "alb" {
  name_prefix = "${var.environment}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = module.vpc.vpc_id

  # HTTPS from anywhere
  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP (redirect to HTTPS)
  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.environment}-alb-sg"
  })
}

# ========================================
# MQTT Broker Cluster (EMQX)
# ========================================

module "mqtt_cluster" {
  source = "./modules/mqtt_cluster"

  environment        = var.environment
  cluster_size       = local.mqtt_cluster_size
  instance_type      = var.mqtt_instance_type
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_ids = [aws_security_group.mqtt_broker.id]

  # TLS certificates (managed externally, referenced here)
  tls_cert_arn = var.mqtt_tls_cert_arn

  # Monitoring
  enable_cloudwatch_logs = true
  enable_prometheus     = true

  tags = local.common_tags
}

# ========================================
# TimescaleDB (RDS with TimescaleDB extension)
# ========================================

module "timescaledb" {
  source = "./modules/timescaledb"

  environment          = var.environment
  instance_class       = var.timescale_instance_class
  allocated_storage    = var.timescale_storage_gb
  max_allocated_storage = var.timescale_max_storage_gb

  vpc_id               = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.database_subnet_group_name
  security_group_ids   = [aws_security_group.timescaledb.id]

  database_name     = "oee_analytics"
  master_username   = var.timescale_username
  master_password   = var.timescale_password  # Should use secrets manager in production

  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  multi_az               = var.environment == "production"
  enable_performance_insights = true

  tags = local.common_tags
}

# ========================================
# Application Servers (Django)
# ========================================

module "app_servers" {
  source = "./modules/app_cluster"

  environment       = var.environment
  cluster_name      = "oee-django"
  instance_type     = var.app_instance_type
  desired_capacity  = var.app_desired_capacity
  min_size          = var.app_min_size
  max_size          = var.app_max_size

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_ids = [aws_security_group.app_server.id]

  # Application configuration
  docker_image = var.django_docker_image

  environment_variables = {
    DJANGO_SETTINGS_MODULE = "oee_dashboard.settings"
    USE_TIMESCALEDB       = "True"
    TIMESCALE_HOST        = module.timescaledb.endpoint
    TIMESCALE_DB          = "oee_analytics"
    TIMESCALE_USER        = var.timescale_username
    TIMESCALE_PASSWORD    = var.timescale_password
    MQTT_BROKER_HOST      = module.mqtt_cluster.load_balancer_dns
    REDIS_URL             = module.redis.endpoint
  }

  tags = local.common_tags
}

# ========================================
# Redis (for Django Channels)
# ========================================

module "redis" {
  source = "./modules/redis"

  environment        = var.environment
  node_type          = var.redis_node_type
  num_cache_nodes    = var.redis_num_nodes

  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [aws_security_group.app_server.id]

  automatic_failover_enabled = var.environment == "production"

  tags = local.common_tags
}

# ========================================
# Application Load Balancer
# ========================================

module "alb" {
  source = "./modules/alb"

  environment         = var.environment
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  security_group_ids  = [aws_security_group.alb.id]

  target_group_arn    = module.app_servers.target_group_arn
  ssl_certificate_arn = var.ssl_certificate_arn

  health_check_path = "/health/"

  tags = local.common_tags
}

# ========================================
# Monitoring & Observability
# ========================================

module "monitoring" {
  source = "./modules/monitoring"

  environment = var.environment

  # CloudWatch Log Groups
  log_groups = [
    "/aws/ecs/oee-django",
    "/aws/rds/timescaledb",
    "/aws/emqx/cluster",
  ]

  # CloudWatch Alarms
  enable_alarms = true
  sns_topic_arn = aws_sns_topic.alerts.arn

  # Prometheus
  enable_prometheus = true
  prometheus_workspace_name = "${var.environment}-oee-prometheus"

  tags = local.common_tags
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-oee-alerts"

  tags = merge(local.common_tags, {
    Name = "${var.environment}-oee-alerts"
  })
}

resource "aws_sns_topic_subscription" "alert_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ========================================
# Outputs
# ========================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "mqtt_broker_endpoint" {
  description = "MQTT broker load balancer endpoint"
  value       = module.mqtt_cluster.load_balancer_dns
}

output "timescaledb_endpoint" {
  description = "TimescaleDB endpoint"
  value       = module.timescaledb.endpoint
  sensitive   = true
}

output "application_url" {
  description = "Application load balancer URL"
  value       = "https://${module.alb.dns_name}"
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.redis.endpoint
  sensitive   = true
}
