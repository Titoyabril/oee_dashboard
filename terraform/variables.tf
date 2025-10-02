# Terraform Variables for OEE Analytics Infrastructure

# ========================================
# General
# ========================================

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "owner" {
  description = "Owner/team responsible for infrastructure"
  type        = string
  default     = "manufacturing-it"
}

variable "alert_email" {
  description = "Email address for alerts"
  type        = string
}

# ========================================
# Networking
# ========================================

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "edge_network_cidr" {
  description = "CIDR block for edge gateway network (OT VLAN)"
  type        = string
  default     = "10.10.0.0/16"
}

variable "dashboard_network_cidr" {
  description = "CIDR block for dashboard users (IT VLAN)"
  type        = string
  default     = "192.168.0.0/16"
}

variable "admin_cidr" {
  description = "CIDR block for administrative access"
  type        = string
  default     = "192.168.1.0/24"
}

# ========================================
# MQTT Broker Cluster
# ========================================

variable "mqtt_instance_type" {
  description = "EC2 instance type for MQTT brokers"
  type        = string
  default     = "t3.large"

  validation {
    condition     = can(regex("^t3\\.", var.mqtt_instance_type)) || can(regex("^m5\\.", var.mqtt_instance_type))
    error_message = "MQTT instance type must be t3.* or m5.* family for production."
  }
}

variable "mqtt_tls_cert_arn" {
  description = "ARN of TLS certificate for MQTT broker (AWS Certificate Manager)"
  type        = string
}

# ========================================
# TimescaleDB (RDS PostgreSQL)
# ========================================

variable "timescale_instance_class" {
  description = "RDS instance class for TimescaleDB"
  type        = string
  default     = "db.m5.xlarge"
}

variable "timescale_storage_gb" {
  description = "Allocated storage for TimescaleDB in GB"
  type        = number
  default     = 500
}

variable "timescale_max_storage_gb" {
  description = "Maximum autoscaling storage for TimescaleDB in GB"
  type        = number
  default     = 2000
}

variable "timescale_username" {
  description = "Master username for TimescaleDB"
  type        = string
  default     = "oeeuser"
  sensitive   = true
}

variable "timescale_password" {
  description = "Master password for TimescaleDB"
  type        = string
  sensitive   = true
}

# ========================================
# Application Servers (Django)
# ========================================

variable "app_instance_type" {
  description = "EC2 instance type for Django application servers"
  type        = string
  default     = "t3.medium"
}

variable "app_desired_capacity" {
  description = "Desired number of application servers"
  type        = number
  default     = 3
}

variable "app_min_size" {
  description = "Minimum number of application servers"
  type        = number
  default     = 2
}

variable "app_max_size" {
  description = "Maximum number of application servers"
  type        = number
  default     = 10
}

variable "django_docker_image" {
  description = "Docker image for Django application"
  type        = string
  default     = "your-ecr-repo/oee-django:latest"
}

variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate for ALB (AWS Certificate Manager)"
  type        = string
}

# ========================================
# Redis (ElastiCache)
# ========================================

variable "redis_node_type" {
  description = "ElastiCache node type for Redis"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 2
}

# ========================================
# Edge Gateways
# ========================================

variable "edge_gateway_count" {
  description = "Number of edge gateways to provision"
  type        = number
  default     = 5
}

# ========================================
# Monitoring
# ========================================

variable "enable_detailed_monitoring" {
  description = "Enable detailed CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}
