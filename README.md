# Arc Backend

A Django REST API backend for managing ArcGis project data, including sites, communities, and regulatory rules. Features automated background tasks for expiry handling using Celery and Redis.

## Features

- **CRUD Operations**: Full REST API for Sites, Communities, and Regulatory Rules
- **Automated Expiry**: Celery tasks to deactivate expired records and programs
- **Admin Interface**: Django admin for data management
- **API Documentation**: Auto-generated docs with drf-spectacular
- **Monitoring**: Celery Flower for task monitoring

## Prerequisites

- Python 3.12+
- Redis (for Celery broker and result backend)
- PostgreSQL or SQLite (default is SQLite for development)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd arc_backend
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment** (optional):
   - Copy `.env.example` to `.env` and configure if needed
   - Default uses SQLite

5. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Populate Dummy Data**

Run management commands to populate test data:

```bash
# Populate sites
python manage.py populate_sites_data

# Populate regulatory rules (if available)
python manage.py populate_regulatory_rules

# Populate compliance calculations
python manage.py populate_compliance_data --count=100
```

7. **Create superuser** (for admin access):
   ```bash
   python manage.py createsuperuser
   ```

## Running the Application

### 1. Start Django Server
```bash
python manage.py runserver
```
Access at: http://127.0.0.1:8000

### 2. Start Redis
Ensure Redis is running:
```bash
redis-server
```

### 3. Start Celery Worker
For better load balancing, run multiple worker instances with different hostnames:
```bash
celery -A arc_backend worker --loglevel=info --hostname=worker1@%h --concurrency=2 &
celery -A arc_backend worker --loglevel=info --hostname=worker2@%h --concurrency=2 &
```
This distributes tasks across workers. Increase concurrency or add more workers as needed.

### 4. Start Celery Beat (Scheduler)
```bash
celery -A arc_backend beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 5. (Optional) Start Flower for Monitoring
```bash
celery -A arc_backend flower
```
Access at: http://0.0.0.0:5555

## Testing Parallel Processing

To test parallel task pulling with multiple workers:

1. Start 3 workers as above.
2. Run multiple tasks from Django shell:
   ```bash
   python manage.py shell
   from regulatory_rules.tasks import check_expiry
   for i in range(3): check_expiry.delay()
   ```
3. Check Flower Tasks tab: Tasks should be processed simultaneously by different workers.

## API Endpoints

- **Sites**: `/api/sites/`
- **Communities**: `/api/community/`
- **Regulatory Rules**: `/api/regulatory-rules/`
- **Compliance Calculations**: `/api/compliance/`
- **API Docs**: `/api/schema/` (OpenAPI) or `/api/schema/swagger-ui/` (Swagger UI)

## Compliance Calculation

The compliance system calculates required vs actual collection sites for each community and program.

### Calculation Logic

1. **Primary**: Uses `RegulatoryRule` model filtered by:
   - Program (Paint, Lighting, Solvents, Pesticides)
   - Year (from community.year)
   - Category (HSP, EEE)
   - Population range (min_population, max_population)

2. **Fallback**: If no RegulatoryRule exists, uses standard formulas:
   - **Paint**: 1 site for 1K-5K pop, ceil(pop/40K) for 5K-500K, 13+ceil((pop-500K)/150K) for >500K
   - **Lighting**: ceil(pop/15K) for 1K-500K, 34+ceil((pop-500K)/50K) for >500K
   - **Solvents/Pesticides**: 1 site for 1K-10K, ceil(pop/250K) for 10K-500K, 2+ceil((pop-500K)/300K) for >500K

### API Usage

**List compliance calculations:**
```bash
GET /api/compliance/?program=Paint&community=<uuid>
```

**Trigger calculation for a community:**
```bash
POST /api/compliance/
{
  "community": "<uuid>",
  "program": "Paint"  // optional, calculates all programs if omitted
}
```

**Get specific calculation:**
```bash
GET /api/compliance/<id>/
```

### Celery Task

Run compliance calculations for all communities:
```python
from complaince.tasks import calculate_all_compliance
calculate_all_compliance.delay()
```

Or for a specific community:
```python
from complaince.tasks import calculate_community_compliance
calculate_community_compliance.delay(community_id, program='Paint')
```

## Admin Interface

Access Django admin at: `/admin/`

- Manage Sites, Communities, Regulatory Rules
- Configure Celery periodic tasks

## Testing

Run tests:
```bash
python manage.py test
```

## Project Structure

```
arc_backend/
├── arc_backend/          # Main Django project
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── sites/                # Sites app
├── community/            # Community app
├── regulatory_rules/     # Regulatory Rules app
├── requirements.txt
├── manage.py
└── README.md
```

## Configuration

- **Database**: Configure in `settings.py` (default: SQLite)
- **Celery**: Broker and result backend configured for Redis
- **Time Zone**: Set to 'Asia/Kolkata' (IST)
- **Email**: Configure for notifications if needed

## Troubleshooting

- **Redis Connection Issues**: Ensure Redis is running on default port 6379
- **Migration Errors**: Run `python manage.py migrate --fake-initial` if needed
- **Celery Clock Drift**: Restart Celery services if times are out of sync

## Contributing

1. Create feature branch
2. Make changes
3. Run tests
4. Submit pull request

## License

[Add license information]
