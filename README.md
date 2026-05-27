# FinOpsKit for AWS

**Analizador de costos y optimizador de recursos para Amazon Web Services**

Desarrollado por Alan Stefanov

---

## 📋 Índice

1. [¿Qué hace esta aplicación?](#-qué-hace-esta-aplicación)
2. [Requisitos](#-requisitos)
3. [Instalación rápida](#-instalación-rápida)
4. [Configuración de credenciales AWS](#-configuración-de-credenciales-aws)
5. [Permisos necesarios de IAM](#-permisos-necesarios-de-iam)
6. [Estructura del proyecto](#-estructura-del-proyecto)
7. [Las 5 secciones de la aplicación](#-las-5-secciones-de-la-aplicación)
   - [📊 Dashboard — Panel de costos](#-dashboard--panel-de-costos)
   - [🧹 Optimization — Escáner de limpieza](#-optimization--escáner-de-limpieza)
   - [⚙️ Policies — Políticas de optimización](#️-policies--políticas-de-optimización)
   - [💾 Backup — Respaldos RDS a S3](#-backup--respaldos-rds-a-s3)
   - [📜 History — Historial de acciones](#-history--historial-de-acciones)
8. [¿Por qué optimizar?](#-por-qué-optimizar)
9. [Cómo ejecutar una limpieza](#-cómo-ejecutar-una-limpieza)
10. [Cómo usar los respaldos a S3](#-cómo-usar-los-respaldos-a-s3)
11. [Atajos de teclado](#-atajos-de-teclado)
12. [Solución de problemas](#-solución-de-problemas)

---

## 🎯 ¿Qué hace esta aplicación?

Esta herramienta de terminal (TUI) se conecta a su cuenta de AWS y le permite:

- **Visualizar costos** mensuales por servicio AWS en un dashboard interactivo.
- **Detectar recursos desperdiciados** como volúmenes EBS sin usar, IPs elásticas sin asignar, snapshots antiguos, versiones Lambda viejas, grupos de seguridad sin referencia, etc.
- **Generar políticas dinámicas** de optimización ordenadas por ahorro estimado, y ejecutarlas en modo dry-run o aplicar los cambios directamente.
- **Exportar snapshots de RDS a S3** para tener respaldos seguros y económicos fuera de la base de datos.
- **Llevar un historial** de todas las acciones de optimización realizadas.

Todo desde la terminal, sin necesidad de entrar a la consola web de AWS.

---

## 📦 Requisitos

- Python 3.10 o superior
- pip3
- Una cuenta de AWS con permisos de lectura/escritura en los servicios a analizar
- Opcional: `alacritty`, `kitty`, `gnome-terminal` para lanzar la interfaz

---

## 🚀 Instalación rápida

```bash
# 1. Clonar o copiar el proyecto
cd finops-kit-aws

# 2. Ejecutar el instalador
chmod +x install.sh
./install.sh

# 3. Configurar credenciales (ver sección siguiente)
# 4. Lanzar la aplicación
./run.sh
#   o directamente: finops-kit
```

O manualmente:

```bash
pip3 install textual boto3
python3 main.py
```

---

## 🔐 Configuración de credenciales AWS

La aplicación acepta credenciales de **tres formas** (en orden de prioridad):

### 1. Archivo `.env` (recomendado)

Copie el archivo de ejemplo y complete sus claves:

```bash
cp .env.example .env
nano .env
```

```
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
S3_BACKUP_BUCKET=mi-bucket-de-respaldos
```

> ⚠️ `.env` está en `.gitignore` — no se subirá a GitHub.

### 2. Carpeta local `.aws/`

Cree una carpeta `.aws/` dentro del proyecto con los archivos `credentials` y `config`:

```
.aws/
├── credentials
└── config
```

**`.aws/credentials`:**
```ini
[default]
aws_access_key_id = AKIAXXXXXXXXXXX
aws_secret_access_key = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**`.aws/config`:**
```ini
[default]
region = us-east-1
```

### 3. Variables de entorno del sistema

```bash
export AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXX
export AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export AWS_DEFAULT_REGION=us-east-1
```

---

## 🛡️ Permisos necesarios de IAM

La aplicación necesita los siguientes permisos. Puede crear una política IAM con esta configuración:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CostExplorer",
      "Effect": "Allow",
      "Action": "ce:GetCostAndUsage",
      "Resource": "*"
    },
    {
      "Sid": "EC2Read",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DescribeAddresses",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeKeyPairs",
        "ec2:DescribeInstances",
        "ec2:DescribeNatGateways"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2Write",
      "Effect": "Allow",
      "Action": [
        "ec2:DeleteVolume",
        "ec2:DeleteSnapshot",
        "ec2:ReleaseAddress",
        "ec2:DeleteSecurityGroup",
        "ec2:DeleteKeyPair",
        "ec2:DeleteNatGateway"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECR",
      "Effect": "Allow",
      "Action": [
        "ecr:DescribeRepositories",
        "ecr:DescribeImages",
        "ecr:BatchDeleteImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDS",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBSnapshots",
        "rds:CreateDBSnapshot",
        "rds:StartExportTask"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Lambda",
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:ListVersionsByFunction",
        "lambda:DeleteFunction"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DeleteLogGroup"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAM",
      "Effect": "Allow",
      "Action": [
        "iam:ListUsers",
        "iam:ListRoles",
        "iam:GetUser"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudFormation",
      "Effect": "Allow",
      "Action": [
        "cloudformation:ListStacks",
        "cloudformation:DeleteStack"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DynamoDB",
      "Effect": "Allow",
      "Action": [
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        "dynamodb:DeleteTable"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3",
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "*"
    },
    {
      "Sid": "STS",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    },
    {
      "Sid": "KMS",
      "Effect": "Allow",
      "Action": "kms:ListAliases",
      "Resource": "*"
    }
  ]
}
```

> **💡 Consejo de seguridad:** Para operaciones de solo lectura (dry-run), basta con los permisos `Describe*` y `List*`. Los permisos de escritura (`Delete*`, `Release*`, `Create*`) solo se necesitan si va a **aplicar** las políticas de limpieza.

---

## 📁 Estructura del proyecto

```
finops-kit-aws/
├── main.py                          # Punto de entrada de la aplicación
├── .env                             # Variables de entorno (NO subir a GitHub)
├── .env.example                     # Ejemplo de variables de entorno
├── .gitignore
├── install.sh                       # Instalador automático
├── optimization_history.json        # Historial de acciones (se genera solo)
│
├── screens/                         # Pantallas de la interfaz TUI
│   ├── splash.py                    #   Pantalla de bienvenida
│   ├── dashboard.py                 #   Dashboard de costos
│   ├── optimization.py              #   Escáner de optimización
│   ├── policies.py                  #   Políticas dinámicas de limpieza
│   ├── backup.py                    #   Respaldos RDS → S3
│   └── history.py                   #   Historial de acciones
│
├── services/                        # Lógica de negocio (AWS API)
│   ├── aws_session.py               #   Sesión AWS (credentials, STS)
│   ├── cost_explorer.py             #   AWS Cost Explorer API
│   ├── cleanup.py                   #   Escáner de 10 categorías de recursos
│   ├── policies.py                  #   Motor de políticas dinámicas (13 reglas)
│   ├── backup_s3.py                 #   Exportación de snapshots RDS a S3
│   └── history.py                   #   Persistencia JSON del historial
│
└── .aws/                            # Credenciales legacy (opcional)
    ├── credentials
    └── config
```

---

## 🖥️ Las 5 secciones de la aplicación

### 📊 Dashboard — Panel de costos

```
┌────────────────────────────────────────────────────────────────┐
│  AWS Cost Explorer - Dashboard                                  │
├────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │ Month 01 │ │ Month 02 │ │ Month 03 │                       │
│  │ $128.45  │ │ $131.20  │ │ $129.87  │                       │
│  └──────────┘ └──────────┘ └──────────┘                       │
│                                                                │
│  Service              │ 2026-03 │ 2026-04 │ 2026-05 │ Total   │
│  ─────────────────────────────────────────────────────────      │
│  EC2 - Compute        │ $48.20  │ $50.10  │ $51.05  │ $149.35 │
│  EC2 - Other          │ $34.00  │ $33.50  │ $34.80  │ $102.30 │
│  Amazon Registrar     │ $31.00  │ $31.00  │ $31.00  │ $93.00  │
│  Amazon S3            │ $12.40  │ $11.80  │ $12.10  │ $36.30  │
│  ...                  │ ...     │ ...     │ ...     │ ...     │
└────────────────────────────────────────────────────────────────┘
```

**¿Qué hace?** Se conecta a AWS Cost Explorer y muestra:

- **El costo total mensual** de los últimos 3 meses.
- **Desglose por servicio**, ordenado del más caro al más barato.
- Cada fila muestra el costo de cada servicio mes a mes y su total acumulado.

**¿Por qué?** Para identificar rápidamente qué servicios consumen más presupuesto y priorizar las acciones de optimización.

**¿Cómo usarlo?** Al abrir la aplicación, el dashboard se carga automáticamente (espera ~5 segundos mientras se ve la pantalla de bienvenida). Presione `d` en cualquier momento para volver a esta pestaña o `r` para refrescar.

---

### 🧹 Optimization — Escáner de limpieza

```
┌────────────────────────────────────────────────────────────────┐
│  Cost Optimization Scanner                                      │
├──────────────────┬─────────────────────────────────────────────┤
│  Services        │  Unattached EBS Volumes (1)                 │
│                  │                                             │
│  🌐 Elastic IPs  │  Volume ID    │ Size │ Type    │ Cost/Month │
│  💾 EBS Volumes  │  vol-abc123  │  30  │ gp3    │   $2.40    │
│  📸 EBS Snapshots│                                             │
│  🗄 RDS Instances│                                             │
│  ⚖ Load Balancers│                                             │
│  ⚡ Lambda Ver.   │                                             │
│  🌍 CloudFront   │                                             │
│  📊 DynamoDB     │                                             │
│  🔴 ElastiCache  │                                             │
│  🌐 NAT Gateways │                                             │
└──────────────────┴─────────────────────────────────────────────┘
```

**¿Qué hace?** Escanea 10 categorías de recursos AWS en busca de oportunidades de limpieza:

| Categoría | Qué detecta | Por qué |
|---|---|---|
| 🌐 Elastic IPs | IPs sin asignar a ninguna instancia | Cuestan $3.60/mes cada una sin usar |
| 💾 EBS Volumes | Volúmenes en estado "available" (sin attached) | Ocupan espacio y cuestan ~$0.08/GB/mes |
| 📸 EBS Snapshots | Snapshots con más de 90 días | Ocupan espacio en S3 innecesariamente |
| 🗄 RDS Instances | Instancias RDS en estado "available" | Quizás ya no son necesarias |
| ⚖ Load Balancers | ALB/NLB/CLB sin targets saludables | Siguen facturando aunque no sirvan tráfico |
| ⚡ Lambda Versions | Versiones viejas (>90 días) de funciones Lambda | Acumulan espacio y desorden |
| 🌍 CloudFront | Distribuciones CloudFront deshabilitadas | Ya no se usan pero siguen en la cuenta |
| 📊 DynamoDB | Tablas con 0 ítems | Ocupan capacidad provisionada sin datos |
| 🔴 ElastiCache | Clústeres disponibles | Quizás ya no se necesitan |
| 🌐 NAT Gateways | NAT Gateways en estado "available" | Cuestan $32.40/mes + procesamiento de datos |

**¿Cómo usarlo?**
1. Presione `r` para escanear (o cambie a la pestaña y espere).
2. Seleccione una categoría en el árbol de la izquierda.
3. Seleccione una fila con las teclas ⬆/⬇.
4. Presione `l` o `Enter` para registrar la acción en el historial (automáticamente asocia su nombre de usuario IAM).

**¿Por qué se auto-selecciona la categoría con más elementos?** Para que siempre vea primero lo que más impacto puede tener.

---

### ⚙️ Policies — Políticas de optimización

```
┌────────────────────────────────────────────────────────────────┐
│  Dynamic Optimization Policies                                  │
├───────────────────────┬────────────────────────────────────────┤
│  Policies (savings)   │  ECR Images                            │
│                       │  Estimated savings: $29.84/month       │
│  🗑️ ECR Images (1169) │                                        │
│     $29.84/mo         │  Repo   │ Digest │ Tags  │ Pushed     │
│  📋 CloudWatch (190)  │  myapp  │ abc123 │ latest│ 2024-01-15 │
│  💾 EBS Vols (1)      │  myapp  │ def456 │ untag │ 2023-11-20 │
│     $2.40/mo          │  ...    │ ...    │ ...   │ ...        │
│  📸 EBS Snaps (2)     │                                        │
│  ⚡ Lambda Vers. (59) │                                        │
│  🔒 Security Gr. (38) │                                        │
│  🔑 Key Pairs (18)    │                                        │
│  👤 IAM Users (7)     │                                        │
│  📦 CloudForm. (22)   │                                        │
│  📊 DynamoDB (7)      │                                        │
│  🗄️ RDS Instances (11)│                                        │
│                       │ ┌──────────┐ ┌──────────┐              │
│                       │ │ 🔍Dry-run│ │ 🚀 Apply │              │
│                       │ └──────────┘ └──────────┘              │
└───────────────────────┴────────────────────────────────────────┘
```

**¿Qué hace?** A diferencia del escáner de optimización (que solo muestra lo que encuentra), las **políticas** son reglas ejecutables que pueden:

1. **Escanean dinámicamente** todos los servicios de AWS.
2. **Ordenan los resultados por ahorro estimado** (mayor impacto primero).
3. **Permiten previsualizar** los recursos encontrados en modo **Dry-run** (seguro, sin modificar nada).
4. **Aplicar la limpieza** directamente desde la interfaz con un solo clic.

**Políticas disponibles (13 reglas):**

| # | Política | Icono | ¿Qué hace? | Ahorro típico |
|---|---|---|---|---|
| 1 | **ECR Images** | 🗑️ | Elimina imágenes Docker sin los tags `_latest`, `_qa`, `_dev`, `_prod` | ~$0.10/GB/mes |
| 2 | **CloudWatch Logs** | 📋 | Elimina grupos de logs con más de 90 días | Libera espacio |
| 3 | **EBS Volumes** | 💾 | Elimina volúmenes EBS sin attached | ~$0.08/GB/mes |
| 4 | **EBS Snapshots** | 📸 | Elimina snapshots con más de 90 días | Libera espacio |
| 5 | **Lambda Versions** | ⚡ | Elimina versiones de función con más de 90 días | Libera espacio |
| 6 | **Security Groups** | 🔒 | Elimina grupos de seguridad sin ENI asociado | Reduce desorden |
| 7 | **Key Pairs** | 🔑 | Elimina pares de claves EC2 no asociados a instancias | Reduce desorden |
| 8 | **IAM Users** | 👤 | Detecta usuarios sin login en >90 días | Seguridad |
| 9 | **CloudFormation** | 📦 | Elimina stacks en estado DELETE_FAILED o ROLLBACK_COMPLETE | Reduce desorden |
| 10 | **Elastic IPs** | 🌐 | Libera IPs elásticas sin asignar | $3.60/mes cada una |
| 11 | **NAT Gateways** | 🌐 | Elimina NAT Gateways inactivos | $32.40/mes cada uno |
| 12 | **DynamoDB Tables** | 📊 | Elimina tablas DynamoDB con 0 ítems | Reduce capacidad |
| 13 | **RDS Instances** | 🗄️ | Lista instancias RDS en ejecución para revisión | Variable |

**¿Cómo se ordenan?** Las políticas se ordenan automáticamente de mayor a menor ahorro mensual estimado. Así siempre ve primero lo que más dinero puede ahorrarle.

**¿Cómo ejecutar una política?**
1. Presione `r` para escanear todos los servicios.
2. Seleccione una política del árbol de la izquierda.
3. Revise los recursos en la tabla de detalles.
4. **Dry-run** (recomendado primero): presione el botón "🔍 Dry-run" para ver qué se eliminaría sin hacer cambios.
5. **Apply**: si está seguro, presione "🚀 Apply" y confirme en el diálogo.

> ⚠️ **Modo Dry-run por defecto:** La aplicación siempre arranca en modo seguro. Nunca modificará recursos sin su confirmación explícita.

---

### 💾 Backup — Respaldos RDS a S3

```
┌────────────────────────────────────────────────────────────────┐
│  RDS Backup to S3                                               │
├──────────────────────┬─────────────────────────────────────────┤
│  RDS Instances       │  Ready. Select an instance to backup.   │
│                      │                                         │
│  Instance  │ Engine  │  ┌─────────────────────────────────┐    │
│  mydb      │ postgres│  │ [Log de operaciones en vivo]    │    │
│  mydb2     │ mysql   │  │ Exporting snapshot...            │    │
│  mydb3     │ mariadb │  │ Export task started: mydb-...   │    │
│                      │  │ Done ✓                           │    │
│                      │  └─────────────────────────────────┘    │
│                      │                                         │
│                      │  ┌────────────┐ ┌──────────────────┐    │
│                      │  │ 🔄 Refresh │ │ 📤 Export to S3  │    │
│                      │  └────────────┘ └──────────────────┘    │
└──────────────────────┴─────────────────────────────────────────┘
```

**¿Qué hace?** Toma el snapshot más reciente de una instancia RDS (automático o manual) y lo exporta a un bucket S3 en formato Parquet. Esto permite:

- Tener respaldos fuera de la base de datos.
- Analizar los datos con Athena, Redshift, o Glue.
- Conservar respaldos históricos a bajo costo (S3 Glaciares/Deep Archive).
- No depende de la retención automática de snapshots de RDS.

**¿Cómo usarlo?**
1. Vaya a la pestaña Backup (presione `b`).
2. Seleccione una instancia RDS de la tabla.
3. Presione "📤 Export Snapshot to S3" (o `b` en el teclado).
4. La aplicación buscará el snapshot más reciente y comenzará la exportación.
5. Vea el progreso en el panel de log en vivo.

**Requisitos:**
- Un bucket S3 existente (configure `S3_BACKUP_BUCKET` en `.env`).
- Permisos IAM para `rds:StartExportTask` y `s3:PutObject`.
- Un rol IAM con permisos de escritura a S3 (la aplicación intentará detectarlo automáticamente).

---

### 📜 History — Historial de acciones

```
┌────────────────────────────────────────────────────────────────┐
│  Optimization History Log                                       │
├────────────────────────────────────────────────────────────────┤
│  Total actions: 42 | Users: alan-stefanov(38), bot-ci(4)       │
│                                                                │
│  Date/Time           │ Category    │ Resource    │ User        │
│  ────────────────────────────────────────────────────────────── │
│  2026-05-27 10:30:15 │ Elastic IPs │ eip-123     │ alan-dev    │
│  2026-05-27 10:28:00 │ EBS Volumes │ vol-456     │ alan-dev    │
│  2026-05-26 09:15:00 │ policy:ecr  │ bulk_1169   │ alan-dev    │
│  ...                 │ ...         │ ...         │ ...         │
└────────────────────────────────────────────────────────────────┘
```

**¿Qué hace?** Registra cada acción de optimización que se realiza:
- **Fecha y hora** exacta.
- **Categoría** del recurso (Elastic IPs, EBS, política ejecutada, etc.).
- **Recurso específico** (ID del volumen, snapshot, etc.).
- **Descripción** de la acción.
- **Usuario IAM** que ejecutó la acción (obtenido automáticamente del ARN de AWS).
- **Ahorro estimado** (cuando aplica).

Los datos se guardan en `optimization_history.json` y persisten entre sesiones.

---

## 💡 ¿Por qué optimizar?

| Recurso | Costo si no se optimiza |
|---|---|
| 1 Elastic IP sin asignar | $3.60/mes → $43.20/año |
| 1 volumen EBS de 100 GB sin attached | $8.00/mes → $96.00/año |
| 1 NAT Gateway inactivo | $32.40/mes → $388.80/año |
| 1,000 imágenes ECR viejas | ~$30.00/mes → ~$360.00/año |
| 1 RDS sin usar (clase mediana) | ~$50-200/mes → ~$600-2400/año |

En una cuenta AWS típica, **entre el 20% y 35% del gasto mensual** corresponde a recursos no utilizados o infrautilizados. Esta aplicación le ayuda a identificar y eliminar sistemáticamente ese desperdicio.

---

## 🛠️ Cómo ejecutar una limpieza

### Flujo recomendado (seguro):

```
1. Abrir la aplicación
   └→ El Dashboard se carga automáticamente (5s)

2. Ir a Optimization (o presionar O)
   └→ Presionar R para escanear recursos
   └→ Revisar cada categoría en el árbol
   └→ Seleccionar ítems y presionar L para
       registrar en el historial

3. Ir a Policies (o presionar P)
   └→ Presionar R para escanear políticas
   └→ Las políticas se ordenan por ahorro
   └→ "Dry-run" para vista previa
   └→ "Apply" para ejecutar (con confirmación)

4. Ir a History (o presionar H)
   └→ Verificar todas las acciones registradas
```

---

## ☁️ Cómo usar los respaldos a S3

### Configuración inicial:

```bash
# 1. Crear un bucket S3
aws s3 mb s3://mi-empresa-rds-backups --region us-east-1

# 2. Configurar el bucket en .env
echo 'S3_BACKUP_BUCKET=mi-empresa-rds-backups' >> .env

# 3. Asegurarse de tener el rol IAM de exportación
#    (la aplicación buscará automáticamente un rol
#     con "export" en el nombre)
```

### Exportación manual de snapshot:

Dentro de la pestaña Backup (`b`):
1. Seleccione una instancia RDS.
2. Presione "📤 Export Snapshot to S3".
3. La aplicación toma el último snapshot disponible y lanza la exportación.
4. El progreso se muestra en vivo en el panel de log.

> La exportación a S3 es asíncrona. El snapshot se exporta en segundo plano.
> Puede monitorear el progreso desde la consola AWS RDS → Export tasks.

---

## ⌨️ Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `q` | Salir de la aplicación |
| `d` | Ir al Dashboard |
| `o` | Ir a Optimization |
| `p` | Ir a Policies |
| `b` | Ir a Backup |
| `h` | Ir a History |
| `r` | Refrescar datos de la pestaña actual |
| `l` | (Optimization) Registrar acción seleccionada |
| `Enter` | (Optimization) Misma acción que `l` |
| `⬆/⬇` | Navegar entre filas de tablas |
| `Tab` | Navegar entre elementos interactivos |
| `Esc` | Cerrar diálogos modales |

---

## 🔧 Solución de problemas

### La terminal no arranca o se cierra inmediatamente

El `run.sh` incluido detecta automáticamente su terminal por defecto
(`x-terminal-emulator` en Debian/Ubuntu, o Alacritty, Kitty,
GNOME Terminal, Konsole, xterm...).

```bash
chmod +x run.sh
./run.sh
```

### Error "No module named textual"

```bash
pip3 install textual
```

### Error "No credentials found"

Verifique que:
1. El archivo `.env` existe y tiene credenciales válidas.
2. O la carpeta `.aws/` tiene los archivos `credentials` y `config`.
3. Las credenciales tienen los permisos necesarios (ver sección de IAM).

### Error de permisos AWS

Si ve errores como `AccessDenied` o `UnauthorizedOperation`, revise que la política IAM tenga todos los permisos listados en la [sección de permisos](#-permisos-necesarios-de-iam).

### La aplicación se ve mal en la terminal

Esta aplicación requiere una terminal que soporte:
- True color (24-bit color)
- Unicode (emojis)
- Tamaño mínimo de 80×24 caracteres

Terminales recomendadas: alacritty, kitty, gnome-terminal, Windows Terminal, iTerm2.

---

## 📄 Licencia MIT

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

**Desarrollado por [Alan Stefanov](mailto:alan.emanuel.stefanov@gmail.com)**
