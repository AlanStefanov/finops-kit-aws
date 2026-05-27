# FinOpsKit for AWS

**Cost analyzer and resource optimizer for Amazon Web Services**

Developed by Alan Stefanov

---

## What is FinOpsKit?

A terminal-based (TUI) application that connects to your AWS account and helps you:

- **Visualize monthly costs** per service in an interactive dashboard.
- **Detect wasted resources** like unattached EBS volumes, unassociated Elastic IPs, old snapshots, stale Lambda versions, unused security groups, and more.
- **Generate dynamic optimization policies** sorted by estimated savings, with dry-run and apply modes.
- **Export RDS snapshots to S3** for secure, low-cost backups.
- **Keep a history log** of all optimization actions performed.

Everything runs from your terminal — no need to open the AWS Management Console.

---

## Requirements

- Python 3.10+
- pip3
- AWS account with read/write permissions on the scanned services
- Optional: `alacritty`, `kitty`, or `gnome-terminal` for windowed launch

---

## Quick Install

```bash
# 1. Clone the project
git clone https://github.com/ALAN-STEFANOV/finops-kit-aws.git
cd finops-kit-aws

# 2. Run the installer
chmod +x install.sh
./install.sh

# 3. Configure AWS credentials (see below)
# 4. Launch the app
./run.sh
#   or directly: finops-kit
```

Or manually:

```bash
pip3 install textual boto3
python3 main.py
```

---

## AWS Credentials Setup

The app accepts credentials in three ways (priority order):

### 1. `.env` file (recommended)

```bash
cp .env.example .env
```

Edit `.env` with your real keys:

```
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAYOURACCESSKEY
AWS_SECRET_ACCESS_KEY=yoursecretkey
S3_BACKUP_BUCKET=my-backup-bucket
```

### 2. Local `.aws/` folder

```
.aws/
├── credentials   # [default] aws_access_key_id = ... / aws_secret_access_key = ...
└── config        # [default] region = us-east-1
```

### 3. System environment variables

```bash
export AWS_ACCESS_KEY_ID=AKIAYOURACCESSKEY
export AWS_SECRET_ACCESS_KEY=yoursecretkey
export AWS_DEFAULT_REGION=us-east-1
```

---

## Required IAM Permissions

Create an IAM policy with these actions:

**Read-only (for dry-run / scanning):**

- `ce:GetCostAndUsage`
- `ec2:Describe*`
- `ecr:DescribeRepositories`, `ecr:DescribeImages`
- `rds:DescribeDBInstances`, `rds:DescribeDBSnapshots`
- `lambda:ListFunctions`, `lambda:ListVersionsByFunction`
- `logs:DescribeLogGroups`
- `iam:ListUsers`, `iam:ListRoles`
- `cloudformation:ListStacks`
- `dynamodb:ListTables`, `dynamodb:DescribeTable`
- `s3:ListAllMyBuckets`
- `sts:GetCallerIdentity`
- `kms:ListAliases`

**Write (for apply / cleanup):**

- `ec2:DeleteVolume`, `ec2:DeleteSnapshot`, `ec2:ReleaseAddress`, `ec2:DeleteSecurityGroup`, `ec2:DeleteKeyPair`, `ec2:DeleteNatGateway`
- `ecr:BatchDeleteImage`
- `rds:CreateDBSnapshot`, `rds:StartExportTask`
- `lambda:DeleteFunction`
- `logs:DeleteLogGroup`
- `cloudformation:DeleteStack`
- `dynamodb:DeleteTable`
- `s3:PutObject`, `s3:GetObject`

---

## App Sections

### 📊 Dashboard
Connected to AWS Cost Explorer. Shows monthly totals (last 3 months) and a breakdown per service sorted by highest cost. Helps quickly identify which services consume most of your budget.

### 🧹 Optimization Scanner
Scans 10 AWS resource categories for cleanup opportunities: Elastic IPs, EBS volumes, EBS snapshots, RDS instances, Load Balancers, Lambda versions, CloudFront, DynamoDB, ElastiCache, and NAT Gateways. Auto-selects the category with the most items. Press `l` or `Enter` on a row to log the action with your IAM username.

### ⚙️ Dynamic Policies
13 executable rules that scan AWS services and are **sorted by estimated monthly savings**. You can:
- **Dry-run** (safe preview, no changes made)
- **Apply** (requires confirmation dialog)

Policies include: ECR image cleanup, CloudWatch Logs retention, EBS volume/snapshot cleanup, Lambda version cleanup, Security Group cleanup, Key Pair cleanup, IAM user audit, CloudFormation stack cleanup, Elastic IP release, NAT Gateway deletion, DynamoDB table cleanup, and RDS instance review.

### 💾 RDS Backup to S3
Exports the latest snapshot of a selected RDS instance to an S3 bucket in Parquet format. Enables long-term, low-cost backups for analysis with Athena, Redshift, or Glue. Configure `S3_BACKUP_BUCKET` in `.env`.

### 📜 History
Persistent JSON log (`optimization_history.json`) of every optimization action with timestamp, category, resource ID, description, IAM user, and estimated savings.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `d` | Dashboard |
| `o` | Optimization |
| `p` | Policies |
| `b` | Backup |
| `h` | History |
| `r` | Refresh current tab |
| `l` / `Enter` | Log selected action (Optimization) |
| `⬆/⬇` | Navigate table rows |
| `Tab` | Cycle interactive widgets |
| `Esc` | Close modal dialogs |

---

## Why Optimize?

| Resource | Cost if unchecked |
|---|---|
| 1 unassociated Elastic IP | $3.60/mo → $43.20/yr |
| 1 unattached 100 GB EBS volume | $8.00/mo → $96.00/yr |
| 1 idle NAT Gateway | $32.40/mo → $388.80/yr |
| 1,000 stale ECR images | ~$30.00/mo → ~$360.00/yr |
| 1 unused medium RDS instance | ~$50-200/mo → ~$600-2400/yr |

Typically **20-35% of monthly AWS spend** goes to unused or underutilized resources. FinOpsKit helps identify and eliminate this waste systematically.

---

## Troubleshooting

### Terminal closes immediately or won't start

Use the included `run.sh` which auto-detects your default terminal
(`x-terminal-emulator` on Debian/Ubuntu, or Alacritty, Kitty,
GNOME Terminal, Konsole, xterm...):

```bash
chmod +x run.sh
./run.sh
```

---

## MIT License

```
MIT License

Copyright (c) 2026 Alan Stefanov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

**Developed by [Alan Stefanov](mailto:alan.emanuel.stefanov@gmail.com)**
