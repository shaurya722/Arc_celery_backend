# ArcGIS Backend API - Complete CURL Command Collection

## Base URL Variable
```bash
BASE_URL="http://127.0.0.1:8000"
```

---

## 🔹 REGULATORY RULES

### 1. Get All Rules (Basic)
```bash
curl -X GET "${BASE_URL}/api/regulatory-rules/rules/" \
  -H "Content-Type: application/json"
```

### 2. Get Rules with Search & Filters
```bash
curl -X GET "${BASE_URL}/api/regulatory-rules/rules/?search=Paint&year=2026&program=Paint&category=HSP&is_active=true&sort=name&page=1&limit=10" \
  -H "Content-Type: application/json"
```

### 3. Get Rules with Sorting (Newest First)
```bash
curl -X GET "${BASE_URL}/api/regulatory-rules/rules/?sort=-created_at&page=1&limit=5" \
  -H "Content-Type: application/json"
```

### 4. Create New Rule
```bash
curl -X POST "${BASE_URL}/api/regulatory-rules/rules/" \
  -H "Content-Type: application/json" \
  -d '{
    "regulatory_rule": 1,
    "census_year": 1,
    "program": "Paint",
    "category": "HSP",
    "rule_type": "Site Requirements",
    "min_population": 5000,
    "max_population": 250000,
    "site_per_population": 40000,
    "base_required_sites": 1,
    "is_active": true
  }'
```

### 5. Get Rule by ID
```bash
curl -X GET "${BASE_URL}/api/regulatory-rules/rules/1/" \
  -H "Content-Type: application/json"
```

### 6. Update Rule
```bash
curl -X PUT "${BASE_URL}/api/regulatory-rules/rules/1/" \
  -H "Content-Type: application/json" \
  -d '{
    "program": "Paint",
    "category": "HSP",
    "rule_type": "Site Requirements",
    "min_population": 5000,
    "max_population": 250000,
    "site_per_population": 40000,
    "base_required_sites": 1,
    "is_active": true
  }'
```

### 7. Delete Rule
```bash
curl -X DELETE "${BASE_URL}/api/regulatory-rules/rules/1/"
```

---

## 🔹 COMMUNITY CENSUS DATA

### 8. Get Community Census Data (Basic)
```bash
curl -X GET "${BASE_URL}/api/community/community-census-data/" \
  -H "Content-Type: application/json"
```

### 9. Get Community Census Data with Filters
```bash
curl -X GET "${BASE_URL}/api/community/community-census-data/?search=Bayview&year=2026&tier=Tier 1&region=Region A&is_active=true&min_population=10000&max_population=50000&sort=population&page=1&limit=20" \
  -H "Content-Type: application/json"
```

### 10. Create Community Census Data
```bash
curl -X POST "${BASE_URL}/api/community/community-census-data/" \
  -H "Content-Type: application/json" \
  -d '{
    "community": 1,
    "census_year": 1,
    "population": 50000,
    "tier": "Tier 1",
    "region": "Region A",
    "zone": "Zone 1",
    "province": "Province X",
    "is_active": true
  }'
```

### 11. Get Community Census Data by ID
```bash
curl -X GET "${BASE_URL}/api/community/community-census-data/1/" \
  -H "Content-Type: application/json"
```

### 12. Update Community Census Data
```bash
curl -X PUT "${BASE_URL}/api/community/community-census-data/1/" \
  -H "Content-Type: application/json" \
  -d '{
    "population": 55000,
    "tier": "Tier 1",
    "region": "Region A",
    "is_active": true
  }'
```

### 13. Delete Community Census Data
```bash
curl -X DELETE "${BASE_URL}/api/community/community-census-data/1/"
```

### 14. Get Communities (Nested Format)
```bash
curl -X GET "${BASE_URL}/api/community/communities/?search=Bayview&year=2026&tier=Tier 1&page=1&limit=10" \
  -H "Content-Type: application/json"
```

### 15. Get Community by ID (Nested)
```bash
curl -X GET "${BASE_URL}/api/community/communities/1/" \
  -H "Content-Type: application/json"
```

### 16. Get Census Years
```bash
curl -X GET "${BASE_URL}/api/community/census-years/?sort=-year&page=1&limit=10" \
  -H "Content-Type: application/json"
```

### 17. Create Census Year
```bash
curl -X POST "${BASE_URL}/api/community/census-years/" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2026,
    "description": "2026 Census Year",
    "is_active": true
  }'
```

### 18. Get Census Year by ID
```bash
curl -X GET "${BASE_URL}/api/community/census-years/1/" \
  -H "Content-Type: application/json"
```

### 19. Update Census Year
```bash
curl -X PUT "${BASE_URL}/api/community/census-years/1/" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2026,
    "description": "Updated 2026 Census Year",
    "is_active": true
  }'
```

### 20. Delete Census Year
```bash
curl -X DELETE "${BASE_URL}/api/community/census-years/1/"
```

---

## 🔹 SITES

### 21. Get Sites (Basic)
```bash
curl -X GET "${BASE_URL}/api/sites/" \
  -H "Content-Type: application/json"
```

### 22. Get Sites with Filters
```bash
curl -X GET "${BASE_URL}/api/sites/?search=Paint&year=2026&site_type=Paint Shop&operator_type=Private&community=1&region=Region A&is_active=true&sort=site_name&page=1&limit=15" \
  -H "Content-Type: application/json"
```

### 23. Create Site
```bash
curl -X POST "${BASE_URL}/api/sites/" \
  -H "Content-Type: application/json" \
  -d '{
    "site": 1,
    "census_year": 1,
    "site_type": "Paint Shop",
    "operator_type": "Private",
    "community": 1,
    "region": "Region A",
    "is_active": true
  }'
```

### 24. Get Site by ID
```bash
curl -X GET "${BASE_URL}/api/sites/1/" \
  -H "Content-Type: application/json"
```

### 25. Update Site
```bash
curl -X PUT "${BASE_URL}/api/sites/1/" \
  -H "Content-Type: application/json" \
  -d '{
    "site_type": "Paint Shop",
    "operator_type": "Private",
    "is_active": true
  }'
```

### 26. Delete Site
```bash
curl -X DELETE "${BASE_URL}/api/sites/1/"
```

---

## 🔹 COMPLIANCE CALCULATIONS

### 27. Get Compliance Calculations
```bash
curl -X GET "${BASE_URL}/api/compliance/?program=Paint&community=1&census_year=1&ordering=-created_at&page_size=20" \
  -H "Content-Type: application/json"
```

### 28. Trigger Compliance Calculation (Async)
```bash
curl -X POST "${BASE_URL}/api/compliance/" \
  -H "Content-Type: application/json" \
  -d '{
    "community": 1,
    "program": "Paint",
    "census_year": 1
  }'
```

### 29. Get Compliance Calculation by ID
```bash
curl -X GET "${BASE_URL}/api/compliance/1/" \
  -H "Content-Type: application/json"
```

### 30. Delete Compliance Calculation
```bash
curl -X DELETE "${BASE_URL}/api/compliance/1/"
```

---

## 🔹 TEST CHECK

### 31. Get Test Communities
```bash
curl -X GET "${BASE_URL}/api/test-check/communities/" \
  -H "Content-Type: application/json"
```

### 32. Get Test Census Years
```bash
curl -X GET "${BASE_URL}/api/test-check/census-years/" \
  -H "Content-Type: application/json"
```

### 33. Get Test Sites
```bash
curl -X GET "${BASE_URL}/api/test-check/sites/" \
  -H "Content-Type: application/json"
```

---

## 🔹 API DOCUMENTATION

### 34. Get OpenAPI Schema
```bash
curl -X GET "${BASE_URL}/api/schema/" \
  -H "Accept: application/json"
```

### 35. Open Swagger UI (Browser)
```bash
curl -X GET "${BASE_URL}/api/schema/swagger-ui/"
```

### 36. Open ReDoc (Browser)
```bash
curl -X GET "${BASE_URL}/api/schema/redoc/"
```

---

## 🔧 QUICK TEST SCRIPTS

### Test All Regulatory Rules Endpoints
```bash
#!/bin/bash
BASE_URL="http://127.0.0.1:8000"

echo "Testing Regulatory Rules API..."
echo "1. Get All Rules:"
curl -s -X GET "${BASE_URL}/api/regulatory-rules/rules/?limit=2" -H "Content-Type: application/json" | python3 -m json.tool | head -20

echo -e "\n2. Get Rules with Search:"
curl -s -X GET "${BASE_URL}/api/regulatory-rules/rules/?search=Paint&limit=1" -H "Content-Type: application/json" | python3 -m json.tool
```

### Test Community Data Endpoints
```bash
#!/bin/bash
BASE_URL="http://127.0.0.1:8000"

echo "Testing Community Census Data API..."
echo "1. Get Community Census Data:"
curl -s -X GET "${BASE_URL}/api/community/community-census-data/?limit=3" -H "Content-Type: application/json" | python3 -m json.tool
```

### Test Compliance Calculation
```bash
#!/bin/bash
BASE_URL="http://127.0.0.1:8000"

echo "Testing Compliance Calculation..."
echo "1. Trigger Compliance Calculation:"
curl -s -X POST "${BASE_URL}/api/compliance/" \
  -H "Content-Type: application/json" \
  -d '{"community": 1, "program": "Paint", "census_year": 1}' | python3 -m json.tool
```

---

## 📊 USAGE EXAMPLES

### Change Base URL for Production
```bash
# For production
BASE_URL="https://your-production-domain.com"

# For staging
BASE_URL="https://staging.your-domain.com"
```

### Common Query Patterns
```bash
# Pagination
?page=2&limit=50

# Search and filter
?search=keyword&year=2026&is_active=true

# Sorting
?sort=name
?sort=-created_at

# Multiple filters
?program=Paint&category=HSP&min_population=10000
```

### Save Response to File
```bash
curl -X GET "${BASE_URL}/api/regulatory-rules/rules/" \
  -H "Content-Type: application/json" \
  -o rules_response.json
```

### Pretty Print JSON Response
```bash
curl -X GET "${BASE_URL}/api/regulatory-rules/rules/?limit=1" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

---

## 🚀 QUICK START

1. **Set your base URL:**
   ```bash
   BASE_URL="http://127.0.0.1:8000"
   ```

2. **Test basic connectivity:**
   ```bash
   curl -X GET "${BASE_URL}/api/regulatory-rules/rules/?limit=1" -H "Content-Type: application/json"
   ```

3. **Test with your data:**
   - Update IDs in the commands
   - Modify search terms and filters
   - Adjust pagination parameters

**Total Commands: 36+ examples covering all endpoints!** 🎉
