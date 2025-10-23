variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "zipo-backend"
}

variable "stage" {
  type    = string
  default = "prod"
}

variable "memory_mb" {
  type    = number
  default = 512
}

variable "timeout_s" {
  type    = number
  default = 30
}

variable "SUPABASE_URL" {
  type = string
}

variable "SUPABASE_ANON_KEY" {
  type      = string
  sensitive = true
}

variable "SUPABASE_SERVICE_ROLE_KEY" {
  type      = string
  default   = ""
  sensitive = true
}

variable "SUPABASE_BUCKET" {
  type = string
}

variable "SUPABASE_JWT_SECRET" {
  type      = string
  sensitive = true
}

variable "ALLOWED_ORIGINS" {
  description = "Comma-separated list of allowed CORS origins"
  type        = string
  default     = ""
}

