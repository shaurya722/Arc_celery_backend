# ArcGIS Backend System - Client Documentation

**Project Overview for Non-Technical Stakeholders**

---

## Executive Summary

The ArcGIS Backend System is a comprehensive data management platform designed to track and manage environmental collection sites across communities. The system helps ensure regulatory compliance by monitoring collection sites for various programs (Paint, Lighting, Solvents, Pesticides) and automatically calculating whether communities meet their required site quotas.

**Key Capabilities:**
- Manage collection sites and community data across multiple years
- Track regulatory compliance automatically
- Monitor site performance and program participation
- Generate compliance reports and identify shortfalls
- Handle site reallocation between communities
- Automated background processing for data updates

---

## What This System Does

### 1. **Community & Site Management**

The system tracks communities and their collection sites over time. Think of it as a digital registry that:

- **Stores Community Information**: Population, geographic region, tier classification, and other demographic data
- **Manages Collection Sites**: Physical locations where residents can drop off materials (paint, light bulbs, solvents, etc.)
- **Tracks Changes Over Time**: Data is organized by census years, allowing you to see how communities and sites evolve

**Real-World Example:**
> A community called "Vancouver Downtown" has a population of 50,000 people. The system tracks how many collection sites they have for paint recycling, where those sites are located, and whether they meet the regulatory requirements for their population size.

---

### 2. **Regulatory Compliance Tracking**

The system automatically calculates whether each community has enough collection sites based on government regulations.

**How It Works:**
1. **Regulatory Rules**: The system stores rules that define how many sites are required based on:
   - Community population size
   - Program type (Paint, Lighting, Solvents, Pesticides)
   - Census year
   
2. **Automatic Calculations**: The system compares:
   - **Required Sites**: How many sites the community should have (based on rules)
   - **Actual Sites**: How many active sites the community currently has
   
3. **Compliance Status**: The system identifies:
   - **Compliant**: Community has exactly the right number of sites
   - **Shortfall**: Community needs more sites
   - **Excess**: Community has more sites than required

**Real-World Example:**
> Based on regulations, a community with 100,000 people needs 5 paint collection sites. The system checks and finds they only have 3 active sites. It automatically flags this as a "shortfall of 2 sites" and calculates a compliance rate of 60%.

---

### 3. **Year-Based Data Tracking (Census Years)**

All data in the system is organized by census years, which allows historical tracking and year-over-year comparisons.

**What This Means:**
- Each community, site, and regulatory rule can have different data for different years
- When a new census year is created, the system automatically copies forward the latest data
- You can compare how a community's compliance changed from 2023 to 2024

**Benefits:**
- Track historical trends
- Plan for future years
- Maintain data accuracy as populations and regulations change

---

## Core Components Explained

### **Communities**

Communities are the geographic areas being monitored (cities, towns, regions).

**Information Tracked:**
- Community name (e.g., "Toronto Central")
- Population size
- Geographic classification (region, zone, province)
- Tier level (classification category)
- Active/inactive status for each year

### **Collection Sites**

Physical locations where residents can drop off recyclable materials.

**Information Tracked:**
- Site name and address
- Which community it serves
- Site type (Collection Site or Event)
- Operator type (Municipal, Retailer, Private Depot, etc.)
- Programs offered (Paint, Lighting, Solvents, Pesticides, Fertilizers)
- Geographic coordinates (latitude/longitude)
- Active/inactive status
- Start and end dates for the site and each program

**Site Types:**
1. **Collection Sites**: Permanent locations (e.g., retail stores, municipal depots)
2. **Events**: Temporary collection events that require approval

### **Regulatory Rules**

Government regulations that define compliance requirements.

**Information Tracked:**
- Program type (Paint, Lighting, etc.)
- Population ranges (e.g., 1,000-5,000 people)
- Required number of sites or calculation formula
- Rule type (Site Requirements, Reallocation, Events, Offsets)
- Active period (start and end dates)

### **Compliance Calculations**

Automated reports showing whether communities meet their requirements.

**Information Provided:**
- Required sites (based on regulations)
- Actual sites (currently active)
- Shortfall (how many more sites are needed)
- Excess (how many extra sites exist)
- Compliance rate (percentage)
- Calculation date

---

## Key Features & Workflows

### **1. Automatic Expiry Management**

The system runs background tasks every hour to automatically deactivate expired items:

- **Sites**: If a site's end date has passed, it's marked as inactive
- **Programs**: If a program's end date has passed at a site, it's deactivated
- **Regulatory Rules**: If a rule expires, it's marked as inactive
- **Communities**: If a community's end date passes, it's deactivated

**Why This Matters:**
- Ensures compliance calculations always use current, active data
- Prevents outdated sites from being counted
- Maintains data accuracy without manual intervention

### **2. Site Reallocation**

Sites can be reassigned from one community to another while maintaining a complete audit trail.

**Use Cases:**
- Community A has excess sites, Community B has a shortfall
- Sites can be reallocated to balance compliance
- The system tracks the full history of reallocations

**Restrictions:**
- Municipal, First Nation/Indigenous, and Regional District sites cannot be reallocated
- Event sites cannot be reallocated
- All reallocations are tracked with timestamps and reasons

### **3. Adjacent Community Management**

The system tracks which communities are geographically adjacent, enabling:
- Identification of reallocation opportunities
- Understanding of regional site distribution
- Strategic planning for new sites

### **4. Automated Compliance Recalculation**

Whenever data changes, the system automatically recalculates compliance:

**Triggers:**
- A site is added, removed, or modified
- A regulatory rule changes
- A program expires
- A community's data is updated
- A new census year is created

**Process:**
- Background tasks run the calculations asynchronously
- Results are stored in the database
- Reports are immediately available via the API

---

## Data Flow & System Architecture

### **How Data Moves Through the System**

```
1. DATA ENTRY
   ↓
   Communities, Sites, and Rules are entered into the system
   ↓
2. ORGANIZATION BY YEAR
   ↓
   Data is linked to specific census years
   ↓
3. AUTOMATIC PROCESSING
   ↓
   Background tasks monitor for expired items
   ↓
4. COMPLIANCE CALCULATION
   ↓
   System calculates required vs. actual sites
   ↓
5. REPORTING
   ↓
   Results available via API for dashboards/reports
```

### **Background Processing (Celery Tasks)**

The system uses automated background workers that run continuously:

**Task 1: Expiry Checker** (Runs every hour)
- Scans all sites, programs, rules, and communities
- Deactivates anything past its end date
- Triggers compliance recalculation for affected communities
- Logs all changes for audit purposes

**Task 2: Compliance Calculator** (Runs on-demand or scheduled)
- Calculates compliance for all communities
- Identifies shortfalls and excesses
- Updates compliance records in the database
- Can be triggered manually or automatically

---

## API Endpoints (How External Systems Connect)

The system provides web APIs that allow other applications (like dashboards or mobile apps) to access data:

### **Community APIs**
- List all communities with filtering and search
- Get detailed information about a specific community
- View year-specific community data
- Create or update community information

### **Site APIs**
- List all collection sites with filtering
- Get detailed site information including programs offered
- Create, update, or delete sites
- Import sites from CSV files
- Export site data

### **Regulatory Rules APIs**
- List all regulatory rules with filtering
- Get specific rule details
- Create or update rules
- Filter by program, year, category

### **Compliance APIs**
- View compliance calculations for all communities
- Filter by program, year, or compliance status
- Trigger manual recalculation
- Get summary statistics (total shortfalls, excesses, compliance rates)

### **Census Year APIs**
- List all census years
- Create new census years (automatically copies forward data)
- View all data for a specific year

---

## Compliance Calculation Logic

### **How Required Sites Are Calculated**

The system uses a two-tier approach:

**Primary Method: Regulatory Rules**
- Looks for active regulatory rules matching:
  - Program type
  - Community population
  - Census year
  - Category (HSP or EEE)
- Uses the rule's formula to calculate required sites

**Fallback Method: Standard Formulas**
If no regulatory rule exists, the system uses built-in formulas:

**Paint Program:**
- 1,000-5,000 people: 1 site
- 5,000-500,000 people: 1 site per 40,000 people
- Over 500,000 people: 13 sites + 1 per 150,000 additional people

**Lighting Program:**
- 1,000-500,000 people: 1 site per 15,000 people
- Over 500,000 people: 34 sites + 1 per 50,000 additional people

**Solvents/Pesticides Programs:**
- 1,000-10,000 people: 1 site
- 10,000-500,000 people: 1 site per 250,000 people
- Over 500,000 people: 2 sites + 1 per 300,000 additional people

### **How Actual Sites Are Counted**

The system counts sites that meet ALL these criteria:
- Site is active (not expired)
- Site belongs to the community (or has been reallocated to it)
- Site offers the specific program being checked
- The program at the site is active (not expired)
- Site is not an unapproved Event

---

## Data Import/Export Capabilities

### **CSV Import**
The system can import data from spreadsheet files:
- Community census data
- Site information
- Regulatory rules

**Features:**
- Validates data before importing
- Provides detailed error messages
- Supports bulk updates
- Maintains data integrity

### **Data Export**
Data can be exported for reporting and analysis:
- Site lists with all details
- Compliance reports
- Community data
- Historical data by year

---

## User Roles & Access

### **Admin Users**
- Full access to all data
- Can create, update, and delete records
- Can trigger manual compliance calculations
- Access to background task monitoring

### **API Access**
- External systems can read data via API
- Filtered access based on API keys
- Rate limiting to prevent overload

---

## Monitoring & Logging

### **System Monitoring**
The system tracks:
- Background task execution
- Compliance calculation results
- Data changes and updates
- Expired items that were deactivated

### **Audit Trail**
Complete history is maintained for:
- Site reallocations (who, when, why)
- Compliance calculations (when calculated, by whom)
- Data modifications (timestamps, user)

### **Logs**
Detailed logs capture:
- Expiry task results
- Compliance calculation outcomes
- Errors and warnings
- System performance metrics

---

## Benefits & Value Proposition

### **For Administrators**
- **Automated Compliance**: No manual tracking of site requirements
- **Real-Time Updates**: Compliance status always current
- **Historical Tracking**: See trends over multiple years
- **Audit Trail**: Complete record of all changes

### **For Regulators**
- **Transparency**: Clear view of compliance across all communities
- **Reporting**: Easy access to compliance data
- **Trend Analysis**: Identify patterns and problem areas
- **Data Accuracy**: Automated calculations reduce errors

### **For Communities**
- **Clear Requirements**: Know exactly how many sites are needed
- **Gap Identification**: See shortfalls and plan accordingly
- **Resource Optimization**: Identify excess sites that could be reallocated
- **Planning Tools**: Use historical data for future planning

---

## Technical Infrastructure

### **Database**
- PostgreSQL (production) or SQLite (development)
- Stores all communities, sites, rules, and compliance data
- Optimized for fast queries and reporting

### **Background Processing**
- Redis: Message broker for background tasks
- Celery: Task queue system for automated processing
- Multiple workers for parallel processing

### **API Framework**
- Django REST Framework: Modern, secure API
- Automatic documentation (Swagger/OpenAPI)
- Pagination, filtering, and search built-in

### **Deployment**
- Can run on local servers or cloud platforms
- Scalable architecture for growing data
- Monitoring tools for system health

---

## Data Security & Integrity

### **Data Validation**
- All inputs are validated before saving
- Prevents invalid or inconsistent data
- Clear error messages for corrections

### **Data Integrity**
- Relationships between data are enforced
- Cannot delete communities with active sites
- Maintains referential integrity

### **Timezone Handling**
- All dates/times stored in UTC
- Displayed in local timezone (Asia/Kolkata)
- Prevents timezone-related errors

---

## Common Use Cases

### **Use Case 1: Adding a New Community**
1. Create community with basic information
2. Add census data for current year (population, region, etc.)
3. System automatically calculates compliance requirements
4. Add collection sites to the community
5. System recalculates compliance showing actual vs. required

### **Use Case 2: Annual Data Update**
1. Create new census year
2. System automatically copies forward all active data
3. Update population figures for communities
4. Update regulatory rules if regulations changed
5. System recalculates compliance for new year

### **Use Case 3: Site Reallocation**
1. Identify community with excess sites
2. Identify adjacent community with shortfall
3. Create reallocation record moving site between communities
4. System recalculates compliance for both communities
5. Audit trail maintained for the reallocation

### **Use Case 4: Compliance Reporting**
1. Access compliance API with filters (year, program, status)
2. System returns current compliance data
3. Filter for communities with shortfalls
4. Export data for reporting
5. Use summary statistics for executive reports

---

## Future Enhancements & Scalability

The system is designed to grow with your needs:

### **Potential Additions**
- Mobile app for site inspections
- Public-facing site locator
- Advanced analytics and forecasting
- Integration with GIS mapping systems
- Automated email notifications for compliance issues
- Multi-language support

### **Scalability**
- Can handle thousands of communities and sites
- Background processing scales with additional workers
- Database can be upgraded for larger datasets
- API can handle high traffic with load balancing

---

## Support & Maintenance

### **Regular Maintenance**
- Background tasks run automatically
- Database backups (recommended daily)
- Log rotation to manage disk space
- Software updates for security patches

### **Monitoring**
- Celery Flower dashboard for task monitoring
- Django admin interface for data management
- API documentation for developers
- System logs for troubleshooting

---

## Glossary of Terms

**Census Year**: A specific year for which data is collected and tracked

**Collection Site**: A physical location where residents can drop off recyclable materials

**Compliance Rate**: Percentage showing how well a community meets site requirements (actual/required × 100)

**Event Site**: A temporary collection event (requires approval)

**Excess**: Number of sites beyond what's required

**HSP**: Household Special Products (Paint, Solvents, Pesticides)

**EEE**: Electrical and Electronic Equipment (Lighting)

**Reallocation**: Moving a site from one community to another

**Shortfall**: Number of additional sites needed to meet requirements

**Site Census Data**: Year-specific information about a site

**Regulatory Rule**: Government regulation defining site requirements

---

## Contact & Technical Details

**System Name**: Arc Backend  
**Technology Stack**: Django, PostgreSQL, Redis, Celery  
**API Documentation**: Available at `/api/schema/swagger-ui/`  
**Admin Interface**: Available at `/admin/`  
**Task Monitoring**: Available at Celery Flower (port 5555)

**API Base URL**: `http://[server-address]:8000/api/`

**Main API Endpoints**:
- Communities: `/api/community/`
- Sites: `/api/sites/`
- Regulatory Rules: `/api/regulatory-rules/`
- Compliance: `/api/compliance/`

---

## Summary

The ArcGIS Backend System is a comprehensive solution for managing environmental collection sites and ensuring regulatory compliance. It automates complex calculations, maintains historical data, and provides real-time insights into compliance status across all communities.

**Key Strengths**:
- Automated compliance tracking
- Year-over-year data management
- Comprehensive audit trails
- Flexible API for integration
- Scalable architecture
- Background processing for efficiency

The system reduces manual work, improves data accuracy, and provides the insights needed for effective environmental program management.
