# ECS Fargate Deployment with ALB and IP Whitelisting
# This is a separate deployment option from Lightsail
# Deploy with: terraform apply -target=module.ecs (or use deploy-ecs.sh)

# Get default VPC
data "aws_vpc" "default" {
  default = true
}

# Get default subnets
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "migration_advisor" {
  name = "${var.app_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# CloudWatch Log Group for ECS tasks
resource "aws_cloudwatch_log_group" "ecs_tasks" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 7

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# IAM Role for ECS Task Execution (ECR pull, CloudWatch logs)
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.app_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Task (Bedrock, S3, Cognito access)
resource "aws_iam_role" "ecs_task" {
  name = "${var.app_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# IAM Policy for ECS Task - Bedrock access
resource "aws_iam_role_policy" "ecs_task_bedrock" {
  name = "${var.app_name}-bedrock-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy for ECS Task - S3 access (scoped to artifacts bucket)
resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${var.app_name}-s3-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.migration_advisor.arn,
          "${aws_s3_bucket.migration_advisor.arn}/*"
        ]
      }
    ]
  })
}

# IAM Policy for ECS Task - Cognito access
resource "aws_iam_role_policy" "ecs_task_cognito" {
  name = "${var.app_name}-cognito-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:GetUser",
          "cognito-idp:InitiateAuth"
        ]
        Resource = aws_cognito_user_pool.migration_advisor.arn
      }
    ]
  })
}

# Security Group for ALB (allow inbound from user's IP only, or CloudFront if enabled)
resource "aws_security_group" "alb" {
  name        = "${var.app_name}-alb-sg"
  description = "Security group for ALB - IP whitelisted or CloudFront only"
  vpc_id      = data.aws_vpc.default.id

  # HTTP from whitelisted IP (only if CloudFront is disabled or cloudfront_only_access is false)
  dynamic "ingress" {
    for_each = (!var.enable_cloudfront || !var.cloudfront_only_access) ? [1] : []
    content {
      description = "HTTP from whitelisted IP"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = [var.my_ip_address]
    }
  }

  # HTTPS from whitelisted IP (only if CloudFront is disabled or cloudfront_only_access is false)
  dynamic "ingress" {
    for_each = (!var.enable_cloudfront || !var.cloudfront_only_access) ? [1] : []
    content {
      description = "HTTPS from whitelisted IP"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = [var.my_ip_address]
    }
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name       = "${var.app_name}-alb-sg"
    Deployment = "ECS-Fargate"
  })
}

# Security Group for ECS Tasks (allow inbound from ALB only)
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.app_name}-ecs-tasks-sg"
  description = "Security group for ECS tasks - allow from ALB only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Streamlit from ALB"
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name       = "${var.app_name}-ecs-tasks-sg"
    Deployment = "ECS-Fargate"
  })
}

# Application Load Balancer
resource "aws_lb" "migration_advisor" {
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  enable_deletion_protection = false
  enable_http2              = true

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# ALB Target Group
resource "aws_lb_target_group" "migration_advisor" {
  name        = "${var.app_name}-tg"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    path                = "/_stcore/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# ALB Listener (HTTP) - redirect to HTTPS if certificate exists, otherwise forward
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.migration_advisor.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = var.certificate_arn != "" ? "redirect" : "forward"

    # Redirect to HTTPS if certificate exists
    dynamic "redirect" {
      for_each = var.certificate_arn != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    # Forward to target group if no certificate
    target_group_arn = var.certificate_arn == "" ? aws_lb_target_group.migration_advisor.arn : null
  }

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# ALB Listener (HTTPS) - only created if certificate_arn is provided
resource "aws_lb_listener" "https" {
  count             = var.certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.migration_advisor.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.migration_advisor.arn
  }

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# ECS Task Definition
resource "aws_ecs_task_definition" "migration_advisor" {
  family                   = var.app_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = var.app_name
      image     = "${aws_ecr_repository.migration_advisor.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8501
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "COGNITO_USER_POOL_ID"
          value = aws_cognito_user_pool.migration_advisor.id
        },
        {
          name  = "COGNITO_CLIENT_ID"
          value = aws_cognito_user_pool_client.migration_advisor.id
        },
        {
          name  = "COGNITO_CLIENT_SECRET"
          value = aws_cognito_user_pool_client.migration_advisor.client_secret
        },
        {
          name  = "S3_BUCKET"
          value = aws_s3_bucket.migration_advisor.id
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_tasks.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8501/_stcore/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# ECS Service
resource "aws_ecs_service" "migration_advisor" {
  name            = var.app_name
  cluster         = aws_ecs_cluster.migration_advisor.id
  task_definition = aws_ecs_task_definition.migration_advisor.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.migration_advisor.arn
    container_name   = var.app_name
    container_port   = 8501
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener.https
  ]

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate"
  })
}

# Outputs for ECS deployment
output "alb_dns_name" {
  description = "ALB DNS name for accessing the application"
  value       = aws_lb.migration_advisor.dns_name
}

output "alb_url" {
  description = "Full URL to access the application"
  value       = var.certificate_arn != "" ? "https://${var.domain_name != "" ? var.domain_name : aws_lb.migration_advisor.dns_name}" : "http://${aws_lb.migration_advisor.dns_name}"
}

output "alb_https_url" {
  description = "HTTPS URL (only available if certificate is configured)"
  value       = var.certificate_arn != "" ? "https://${var.domain_name != "" ? var.domain_name : aws_lb.migration_advisor.dns_name}" : "HTTPS not configured - provide certificate_arn variable"
}

output "ecs_cluster_name" {
  description = "ECS Cluster name"
  value       = aws_ecs_cluster.migration_advisor.name
}

output "ecs_service_name" {
  description = "ECS Service name"
  value       = aws_ecs_service.migration_advisor.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group for ECS tasks"
  value       = aws_cloudwatch_log_group.ecs_tasks.name
}

# Route53 DNS Record (optional - only if domain_name is provided)
data "aws_route53_zone" "main" {
  count = var.domain_name != "" ? 1 : 0
  name  = var.domain_name
}

resource "aws_route53_record" "app" {
  count   = var.domain_name != "" ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.migration_advisor.dns_name
    zone_id                = aws_lb.migration_advisor.zone_id
    evaluate_target_health = true
  }
}

output "route53_record" {
  description = "Route53 DNS record (if configured)"
  value       = var.domain_name != "" ? "DNS record created for ${var.domain_name}" : "No custom domain configured"
}
