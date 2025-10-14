# IAM Module - IRSA (IAM Roles for Service Accounts) for EKS

# IAM Role for Service Account (IRSA)
resource "aws_iam_role" "this" {
  name               = var.role_name
  assume_role_policy = var.create_irsa_role ? data.aws_iam_policy_document.irsa_assume_role[0].json : var.assume_role_policy
  description        = var.role_description
  max_session_duration = var.max_session_duration

  tags = var.tags
}

# IRSA Assume Role Policy
data "aws_iam_policy_document" "irsa_assume_role" {
  count = var.create_irsa_role ? 1 : 0

  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:sub"
      values   = [for sa in var.service_accounts : "system:serviceaccount:${sa.namespace}:${sa.name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# Attach AWS managed policies
resource "aws_iam_role_policy_attachment" "managed_policies" {
  for_each = toset(var.managed_policy_arns)

  role       = aws_iam_role.this.name
  policy_arn = each.value
}

# Create and attach inline policies
resource "aws_iam_role_policy" "inline_policies" {
  for_each = var.inline_policies

  name   = each.key
  role   = aws_iam_role.this.id
  policy = each.value
}

# Create custom IAM policy
resource "aws_iam_policy" "custom" {
  count = var.create_custom_policy ? 1 : 0

  name        = "${var.role_name}-policy"
  description = var.custom_policy_description
  policy      = var.custom_policy
  tags        = var.tags
}

# Attach custom policy
resource "aws_iam_role_policy_attachment" "custom" {
  count = var.create_custom_policy ? 1 : 0

  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.custom[0].arn
}
